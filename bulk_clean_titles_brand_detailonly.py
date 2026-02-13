import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXCLUDE = {"index.html", "list.html"}

def clean_title_only_brand_and_detail(s: str) -> str:
    s = s or ""

    # 1) [ ... ] 브랜드 표기 제거 (앞뒤 공백까지 정리)
    #    예: "[씨디씨] " 또는 " [CDC]" 등
    s = re.sub(r"\s*\[[^\]]+\]\s*", " ", s)

    # 2) '상세페이지' 단어만 제거 (따옴표는 그대로 둠)
    s = re.sub(r"\s*상세페이지\s*", " ", s, flags=re.I)

    # 공백 정리(내용은 유지)
    s = re.sub(r"[ \t]+", " ", s).strip()

    return s

def replace_title(html: str, new_title: str) -> tuple[str, bool]:
    m = re.search(r"<title\b[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    if not m:
        return html, False
    old = m.group(1)
    # 내용만 교체 (태그 유지)
    html2 = re.sub(r"(<title\b[^>]*>).*?(</title>)",
                   r"\1" + new_title + r"\2",
                   html, count=1, flags=re.I | re.S)
    return html2, (html2 != html)

def replace_first_h1(html: str, new_h1: str) -> tuple[str, bool]:
    if not re.search(r"<h1\b", html, flags=re.I):
        return html, False
    html2 = re.sub(r"(<h1\b[^>]*>).*?(</h1>)",
                   r"\1" + new_h1 + r"\2",
                   html, count=1, flags=re.I | re.S)
    return html2, (html2 != html)

def main():
    files = sorted(
        [p for p in ROOT.glob("*.html")
         if p.name.lower() not in EXCLUDE and re.fullmatch(r"\d{3,}\.html", p.name)],
        key=lambda p: int(p.stem)
    )

    changed = 0
    for p in files:
        html = p.read_text(encoding="utf-8", errors="ignore")

        mt = re.search(r"<title\b[^>]*>(.*?)</title>", html, flags=re.I | re.S)
        if not mt:
            continue

        old_title = re.sub(r"\s+", " ", mt.group(1)).strip()
        new_title = clean_title_only_brand_and_detail(old_title)

        html2, ok1 = replace_title(html, new_title)
        html3, ok2 = replace_first_h1(html2, new_title)

        if html3 != html:
            p.write_text(html3, encoding="utf-8")
            changed += 1

    print(f"Done. Updated: {changed} files / Total scanned: {len(files)}")

if __name__ == "__main__":
    main()
