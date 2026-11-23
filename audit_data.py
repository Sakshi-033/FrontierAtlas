
import json
from pathlib import Path
from urllib.parse import urlparse


FILES = {
    "Startups": "data/startups.json",
    "Products": "data/products.json",
    "Research Papers": "data/research_papers.json"
}


def valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


for name, filepath in FILES.items():

    path = Path(filepath)

    print(f"\n========== {name.upper()} ==========")

    if not path.exists():
        print("FILE MISSING")
        continue

    with path.open(encoding="utf-8") as file:
        records = json.load(file)

    print("Total records:", len(records))

    if name == "Startups":
        names = [
            r.get("content", {}).get("entityName", "").strip().lower()
            for r in records
        ]
        urls = [
            r.get("source", {}).get("url", "")
            for r in records
        ]

    elif name == "Products":
        names = [
            r.get("content", {}).get("productName", "").strip().lower()
            for r in records
        ]
        urls = [
            r.get("source", {}).get("url", "")
            for r in records
        ]

    else:
        names = [
            r.get("paper_url", "").strip().lower()
            for r in records
        ]
        urls = [
            r.get("paper_url", "")
            for r in records
        ]

    names = [n for n in names if n]

    print("Unique identities:", len(set(names)))
    print("Duplicate identities:", len(names) - len(set(names)))
    print("Valid URLs:", sum(valid_url(u) for u in urls))
    print("Invalid URLs:", sum(not valid_url(u) for u in urls))

    if name == "Research Papers":
        print(
            "GitHub links:",
            sum(bool(r.get("github_url")) for r in records)
        )
        print(
            "GitHub star counts:",
            sum(r.get("github_stars") is not None for r in records)
        )

print("\n========== AUDIT COMPLETE ==========")
