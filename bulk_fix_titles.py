import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXCLUDE = {"index.html", "list.html"}

def clean_label(s: str) -> str:
    s = (s or "").strip()

    # 앞 번호 제거: (31) / 31 / 31번 / 31. / 31-) 등
    s = re.sub(r"^\s*(\(\s*\d+\s*\)|\d+\s*(번|호)?[.)-]?)\s*", "", s, flags=re.I)

    # 뒤 '상세페이지' 제거
    s = re.sub(r"\s*상세페이지\s*$", "", s, flags=re.I)

    # 공백 정리
    s = re.sub(r"\s+", " ", s).strip()
    return s

def replace_title(html: str, new_title: str) -> tuple[str, bool]:
    # <title>...</title> 교체 (없으면 <head> 안에 삽입)
    m = re.search(r"<title\b[^>]*>.*?</title>", html, flags=re.I | re.S)
    if m:
        html2 = re.sub(r"<title\b[^>]*>.*?</title>",
                       f"<title>{new_title}</title>",
                       html, count=1, flags=re.I | re.S)
        return html2, True

    # head가 있으면 그 안에 삽입
    if re.search(r"<head\b[^>]*>", html, flags=re.I):
        html2 = re.sub(r"(<head\b[^>]*>\s*)",
                       r"\1" + f"<title>{new_title}</title>\n",
                       html, count=1, flags=re.I)
        return html2, True

    return html, False

def replace_h1_if_exists(html: str, new_h1: str) -> tuple[str, bool]:
    # 첫 번째 <h1>만 교체 (없으면 건드리지 않음)
    if re.search(r"<h1\b", html, flags=re.I):
        html2 = re.sub(r"<h1\b[^>]*>.*?</h1>",
                       f"<h1>{new_h1}</h1>",
                       html, count=1, flags=re.I | re.S)
        return html2, True
    return html, False

def main():
    files = sorted(
        [p for p in ROOT.glob("*.html")
         if p.name.lower() not in EXCLUDE and re.fullmatch(r"\d{3,}\.html", p.name)],
        key=lambda p: int(p.stem)
    )

    changed = 0
    for p in files:
        html = p.read_text(encoding="utf-8", errors="ignore")

        # 기존 title 추출
        mt = re.search(r"<title\b[^>]*>(.*?)</title>", html, flags=re.I | re.S)
        old_title = re.sub(r"\s+", " ", (mt.group(1) if mt else "")).strip()

        # 새 제목 결정
        # 1) 기존 title 기반 정리
        # 2) 기존 title이 없거나 정리 후 비면 파일명(코드) 사용
        new_title = clean_label(old_title)
        if not new_title:
            new_title = p.stem  # 코드번호라도 넣어두기

        html2, ok1 = replace_title(html, new_title)
        html3, ok2 = replace_h1_if_exists(html2, new_title)

        if html3 != html:
            p.write_text(html3, encoding="utf-8")
            changed += 1

    print(f"Done. Updated: {changed} files / Total: {len(files)} files")

if __name__ == "__main__":
    main()
