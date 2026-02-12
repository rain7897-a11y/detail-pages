# auto_build_products.py
# 목적:
#  - *.html(코드전용) 스캔
#  - 제품명(name), 규격(spec) 자동 추출(휴리스틱)
#  - products_meta.csv 생성/갱신
#  - products.json 생성
#
# 사용:
#   python auto_build_products.py
# 옵션:
#   python auto_build_products.py --keep-manual   (기존 CSV 값 우선 유지)
#   python auto_build_products.py --force         (기존 CSV 값도 자동값으로 덮어쓰기)

import argparse
import csv
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
META_CSV = ROOT / "products_meta.csv"
OUT_JSON = ROOT / "products.json"

EXCLUDE = {"index.html", "list.html"}

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def extract_title(soup: BeautifulSoup) -> str:
    t = soup.title.get_text(" ", strip=True) if soup.title else ""
    return norm_space(t)

def extract_h1(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if not h1:
        return ""
    return norm_space(h1.get_text(" ", strip=True))

def extract_name(soup: BeautifulSoup) -> str:
    """
    제품명 우선순위:
      1) h1
      2) title (불필요 접미어 일부 제거)
    """
    h1 = extract_h1(soup)
    if h1:
        return h1

    title = extract_title(soup)
    # title 정리(예: "제품 상세페이지 목록" 같은 건 제외)
    junk = {"제품 상세페이지 목록", "제품 목록"}
    if title in junk:
        return ""
    # 흔한 접미어/접두어 제거
    title = re.sub(r"\s*상세페이지\s*$", "", title)
    title = re.sub(r"^\(\d+\)\s*", "", title)  # (31) 같은 번호 제거
    return norm_space(title)

def text_around_keyword(full_text: str, keyword: str, window: int = 80) -> list[str]:
    """
    본문 텍스트에서 keyword 주변의 문맥을 추출
    """
    hits = []
    for m in re.finditer(re.escape(keyword), full_text, flags=re.IGNORECASE):
        s = max(0, m.start() - window)
        e = min(len(full_text), m.end() + window)
        ctx = norm_space(full_text[s:e])
        hits.append(ctx)
    return hits

def extract_spec_from_tables(soup: BeautifulSoup) -> str:
    """
    테이블/정의리스트에서 '규격/사이즈/치수' 같은 라벨의 값을 찾는 휴리스틱
    """
    labels = ["규격", "사이즈", "치수", "SIZE", "SPEC", "규  격", "규 격"]

    # 1) <tr><th>규격</th><td>...</td>
    for tr in soup.find_all("tr"):
        th = tr.find(["th", "td"])
        tds = tr.find_all(["td", "th"])
        if not tds:
            continue
        row_text = norm_space(tr.get_text(" ", strip=True))
        for lab in labels:
            if lab.lower() in row_text.lower():
                # 같은 행에서 라벨 다음 값을 추정
                # 가장 단순하게: 마지막 셀 텍스트 사용
                val = norm_space(tds[-1].get_text(" ", strip=True))
                # 라벨 자체만 들어간 경우 제외
                if val and val.lower() != lab.lower():
                    return val

    # 2) <dl><dt>규격</dt><dd>...</dd>
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        for dt in dts:
            dt_text = norm_space(dt.get_text(" ", strip=True))
            for lab in labels:
                if lab.lower() == dt_text.lower():
                    dd = dt.find_next_sibling("dd")
                    if dd:
                        val = norm_space(dd.get_text(" ", strip=True))
                        if val:
                            return val

    return ""

def extract_spec_from_text(soup: BeautifulSoup) -> str:
    """
    본문 텍스트에서 '규격:' '사이즈:' 패턴을 잡아 spec 추정
    """
    full = norm_space(soup.get_text("\n", strip=True))
    # 너무 길면 뒤에서 오탐 많아져서 길이 제한
    if len(full) > 20000:
        full = full[:20000]

    patterns = [
        r"(규격|사이즈|치수)\s*[:\-]\s*([^\n]{2,80})",
        r"(SIZE|SPEC)\s*[:\-]\s*([^\n]{2,80})",
    ]
    for pat in patterns:
        m = re.search(pat, full, flags=re.IGNORECASE)
        if m:
            val = norm_space(m.group(2))
            # 너무 일반적인 문구 제거
            if val and val not in {"참고", "상세", "확인"}:
                return val

    # 키워드 주변 문맥에서 "규격 32cm / 높이 18cm" 같은 조각 추출 시도
    for kw in ["규격", "사이즈", "치수", "SIZE", "SPEC"]:
        ctxs = text_around_keyword(full, kw, window=60)
        for ctx in ctxs[:3]:
            # 키워드 뒤의 숫자/단위가 포함된 부분을 뽑아보기
            m2 = re.search(rf"{kw}\s*(?:[:\-]|\s)\s*([0-9a-zA-Z가-힣×xX\*\.\-/\s]{{3,80}})", ctx, flags=re.IGNORECASE)
            if m2:
                val = norm_space(m2.group(1))
                # 단위/숫자 존재 확인(오탐 방지)
                if re.search(r"\d", val):
                    return val

    return ""

def extract_spec(soup: BeautifulSoup) -> str:
    """
    규격 추출 우선순위:
      1) 테이블/정의리스트 기반
      2) 텍스트 패턴 기반
    """
    v = extract_spec_from_tables(soup)
    if v:
        return v
    v = extract_spec_from_text(soup)
    return v

def load_existing_meta(path: Path) -> dict[int, dict[str, str]]:
    """
    existing meta: {code: {name, spec}}
    """
    meta = {}
    if not path.exists():
        return meta
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            if not row:
                continue
            code_raw = (row.get("code") or "").strip()
            if not code_raw.isdigit():
                continue
            code = int(code_raw)
            meta[code] = {
                "name": (row.get("name") or "").strip(),
                "spec": (row.get("spec") or "").strip(),
            }
    return meta

def write_meta_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code", "name", "spec"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-manual", action="store_true", help="기존 products_meta.csv 값이 있으면 우선 유지")
    ap.add_argument("--force", action="store_true", help="기존 값도 자동값으로 덮어쓰기")
    args = ap.parse_args()

    if args.keep_manual and args.force:
        raise SystemExit("옵션 충돌: --keep-manual 과 --force 는 동시에 사용할 수 없습니다.")

    existing = load_existing_meta(META_CSV)

    items = []
    html_files = []
    for p in ROOT.glob("*.html"):
        if p.name.lower() in EXCLUDE:
            continue
        m = re.fullmatch(r"(\d{3,})\.html", p.name)
        if not m:
            continue
        html_files.append(p)

    html_files.sort(key=lambda x: int(x.stem))

    auto_count_name = 0
    auto_count_spec = 0

    for p in html_files:
        code = int(p.stem)
        soup = BeautifulSoup(read_text(p), "html.parser")

        title = extract_title(soup)
        auto_name = extract_name(soup)
        auto_spec = extract_spec(soup)

        # 기존값
        old_name = existing.get(code, {}).get("name", "")
        old_spec = existing.get(code, {}).get("spec", "")

        # name 결정
        if args.force:
            name = auto_name or old_name or title or str(code)
        elif args.keep_manual:
            name = old_name or auto_name or title or str(code)
        else:
            # 기본: 기존값 있으면 유지, 없으면 자동
            name = old_name or auto_name or title or str(code)

        # spec 결정
        if args.force:
            spec = auto_spec or old_spec
        elif args.keep_manual:
            spec = old_spec or auto_spec
        else:
            spec = old_spec or auto_spec

        if not old_name and auto_name:
            auto_count_name += 1
        if not old_spec and auto_spec:
            auto_count_spec += 1

        items.append({
            "code": code,
            "file": f"{code}.html",
            "title": title,
            "name": name,
            "spec": spec,
        })

    # products_meta.csv 생성
    meta_rows = [{"code": it["code"], "name": it["name"], "spec": it["spec"]} for it in items]
    write_meta_csv(META_CSV, meta_rows)

    # products.json 생성
    OUT_JSON.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK: scanned {len(items)} pages")
    print(f"OK: wrote {META_CSV.name}")
    print(f"OK: wrote {OUT_JSON.name}")
    print(f"Auto filled (new): name={auto_count_name}, spec={auto_count_spec}")
    print("Tip: spec 자동추출이 약하면 products_meta.csv에서 해당 행만 수동 보완하시면 됩니다.")

if __name__ == "__main__":
    main()
