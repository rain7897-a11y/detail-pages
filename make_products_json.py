import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
META_CSV = ROOT / "products_meta.csv"
OUT_JSON = ROOT / "products.json"

def extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    t = re.sub(r"\s+", " ", m.group(1)).strip()
    return t

def load_meta_csv(path: Path) -> dict:
    """
    returns: { code(int): {name:str, spec:str} }
    """
    meta = {}
    if not path.exists():
        return meta

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row:
                continue
            code_raw = (row.get("code") or "").strip()
            if not code_raw.isdigit():
                continue
            code = int(code_raw)
            name = (row.get("name") or "").strip()
            spec = (row.get("spec") or "").strip()
            meta[code] = {"name": name, "spec": spec}
    return meta

def main():
    meta = load_meta_csv(META_CSV)

    items = []
    for p in ROOT.glob("*.html"):
        low = p.name.lower()
        if low in ("index.html", "list.html"):
            continue

        m = re.fullmatch(r"(\d{3,})\.html", p.name)
        if not m:
            continue

        code = int(m.group(1))
        html = p.read_text(encoding="utf-8", errors="ignore")
        title = extract_title(html)

        name = meta.get(code, {}).get("name", "")
        spec = meta.get(code, {}).get("spec", "")

        items.append({
            "code": code,
            "file": p.name,   # "3436976.html"
            "title": title,   # html <title> (있으면 저장)
            "name": name,     # CSV에서 입력
            "spec": spec      # CSV에서 입력
        })

    items.sort(key=lambda x: x["code"])

    OUT_JSON.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: wrote {OUT_JSON} ({len(items)} items)")
    if META_CSV.exists():
        print(f"Meta used: {META_CSV}")
    else:
        print("Meta not found: products_meta.csv (name/spec will be blank)")

if __name__ == "__main__":
    main()
