
import json
import zipfile
from pathlib import Path
from openpyxl import load_workbook

ROOT = Path.cwd()
DATA = ROOT / "data"

def read_json(name):
    path = DATA / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("records", "items", "data", "mappings", "logs"):
            if isinstance(data.get(key), list):
                return data[key]
    return []

print("\n========== FRONTIERATLAS FINAL AUDIT ==========\n")

# 1. Dataset counts
datasets = {
    "Startups": "startups.json",
    "Products": "products.json",
    "Research Papers": "research_papers.json",
    "News": "news.json",
    "Jobs": "jobs.json",
    "Entity Mapping": "entity_mapping_log.json",
}

for label, filename in datasets.items():
    records = read_json(filename)
    print(f"{label}: {len(records)}")

# 2. GitHub metrics
papers = read_json("research_papers.json")
github_links = sum(
    bool(p.get("github_url") or p.get("githubUrl"))
    for p in papers if isinstance(p, dict)
)
github_stars = sum(
    (p.get("github_stars") is not None
     or p.get("githubStars") is not None)
    for p in papers if isinstance(p, dict)
)
print("\n--- RESEARCH METRICS ---")
print("Papers:", len(papers))
print("GitHub links:", github_links)
print("GitHub star metrics:", github_stars)

# 3. LLM extraction
log_path = DATA / "extraction_log.json"
if log_path.exists():
    with open(log_path, encoding="utf-8") as f:
        log = json.load(f)
    print("\n--- LLM EXTRACTION ---")
    print("Input:", log.get("input_records", "check log"))
    print("Extracted:", log.get("total_entities", "check log"))
    print("Successful:", log.get("successful", "check log"))
    print("Failed:", log.get("failed", "check log"))

# 4. Crawl report
crawl_path = DATA / "crawl_report.json"
if crawl_path.exists():
    with open(crawl_path, encoding="utf-8") as f:
        crawl = json.load(f)
    print("\n--- CRAWLER ---")
    print("URLs selected:", crawl.get("urls_selected"))
    print("Results:", crawl.get("results_count"))
    print("Concurrency:", crawl.get("concurrency"))
    print("Browser fallback:", crawl.get("browser_fallback_urls"))

# 5. Workbook
xlsx = ROOT / "FrontierAtlas_Output.xlsx"
print("\n--- WORKBOOK ---")
if xlsx.exists():
    wb = load_workbook(xlsx, read_only=True)
    print("Sheets:", wb.sheetnames)
    for ws in wb.worksheets:
        print(f"{ws.title}: {ws.max_row - 1} data rows")
else:
    print("WORKBOOK MISSING")

# 6. Submission ZIP
zip_path = ROOT / "FrontierAtlas_Submission.zip"
print("\n--- ZIP PACKAGE ---")
if zip_path.exists():
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        print("Files:", len(names))
        print("Contains .env:", any(
            Path(n).name == ".env" for n in names
        ))
        print("Contains .venv:", any(
            ".venv/" in n.replace("\\", "/") for n in names
        ))
        print("Contains source code:", any(
            n.startswith("src/") and n.endswith(".py")
            for n in names
        ))
        print("Contains architecture:", any(
            Path(n).name == "Architecture.pdf" for n in names
        ))
        print("Contains README:", any(
            Path(n).name == "README.md" for n in names
        ))
else:
    print("ZIP MISSING")

print("\n========== AUDIT FINISHED ==========")
