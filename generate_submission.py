import json
import zipfile
from pathlib import Path
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, PageBreak
)

ROOT = Path.cwd()
DATA = ROOT / "data"
OUTPUT = ROOT

FILES = {
    "Startups": "startups.json",
    "Products": "products.json",
    "Research Papers": "research_papers.json",
    "News": "news.json",
    "Jobs": "jobs.json",
    "Entity Mapping Log": "entity_mapping_log.json",
}


def load_json(filename):
    path = DATA / filename
    if not path.exists():
        print(f"[WARNING] Missing: {path}")
        return []

    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for key in ("records", "items", "data", "mappings", "logs"):
                if isinstance(data.get(key), list):
                    return data[key]
            return [data]

        return []

    except Exception as error:
        print(f"[ERROR] Could not read {filename}: {error}")
        return []


def cell_value(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def make_workbook():
    workbook = Workbook()
    workbook.remove(workbook.active)

    counts = {}

    for sheet_name, filename in FILES.items():
        records = load_json(filename)
        counts[sheet_name] = len(records)

        sheet = workbook.create_sheet(sheet_name)

        headers = []
        for record in records:
            if isinstance(record, dict):
                for key in record:
                    if key not in headers:
                        headers.append(key)

        if not headers:
            headers = ["Status"]
            sheet.append(headers)
            sheet.append(["No records available"])
        else:
            sheet.append(headers)

            for record in records:
                if not isinstance(record, dict):
                    record = {"value": record}

                sheet.append([
                    cell_value(record.get(header))
                    for header in headers
                ])

        # Formatting
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        sheet.row_dimensions[1].height = 30

        for cell in sheet[1]:
            cell.font = Font(
                bold=True, color="FFFFFF", size=11
            )
            cell.fill = PatternFill(
                "solid", fgColor="25213B"
            )
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True
            )

        for column in sheet.columns:
            letter = get_column_letter(column[0].column)
            max_width = 12

            for cell in column:
                cell.alignment = Alignment(
                    vertical="top", wrap_text=True
                )
                max_width = max(
                    max_width,
                    min(len(str(cell.value or "")), 45)
                )

            sheet.column_dimensions[letter].width = min(
                max_width + 2, 45
            )

    path = OUTPUT / "FrontierAtlas_Output.xlsx"
    workbook.save(path)

    print("\nWORKBOOK CREATED:", path)
    for name, count in counts.items():
        print(f"{name}: {count} records")

    return counts


def make_architecture_pdf(counts):
    path = OUTPUT / "Architecture.pdf"

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="MainTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#292344"),
        fontSize=21,
        leading=26,
        spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        name="Section",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#514477"),
        spaceBefore=9,
        spaceAfter=5
    ))
    styles.add(ParagraphStyle(
        name="SmallBody",
        parent=styles["BodyText"],
        fontSize=8.5,
        leading=12,
        spaceAfter=5
    ))

    story = []

    story.append(Paragraph(
        "FRONTIERATLAS",
        styles["MainTitle"]
    ))
    story.append(Paragraph(
        "System Architecture and Engineering Report",
        styles["Heading2"]
    ))
    story.append(Paragraph(
        "Prepared: " + datetime.now().strftime("%d %B %Y"),
        styles["SmallBody"]
    ))

    story.append(Paragraph("1. System Overview", styles["Section"]))
    story.append(Paragraph(
        "FrontierAtlas is an asynchronous data acquisition and "
        "entity-processing pipeline for AI startups, products, "
        "research papers, news, and job opportunities. The system "
        "collects source records, validates and stores structured "
        "data, extracts entities through an LLM fallback chain, "
        "and resolves names against a canonical seed list.",
        styles["SmallBody"]
    ))

    story.append(Paragraph("2. Architecture and Data Flow", styles["Section"]))
    architecture = [
        ["Layer", "Responsibility"],
        ["Collectors", "Startup, product, arXiv, news and job ingestion"],
        ["HTTP client", "Async requests, bounded concurrency, timeouts and retries"],
        ["Validation", "Pydantic schemas, URL checks, deduplication and date handling"],
        ["LLM orchestration", "Gemini, Groq and DeepSeek provider fallback; JSON extraction"],
        ["Entity resolution", "Canonical seed matching, aliases and mapping log"],
        ["Storage", "JSON datasets and generated spreadsheet output"],
    ]

    table = Table(architecture, colWidths=[38 * mm, 130 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#292344")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F2F0F7")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

    story.append(Paragraph("3. LLM Reliability and Payload Handling", styles["Section"]))
    story.append(Paragraph(
        "The configured provider order is Gemini Flash, Groq, then "
        "DeepSeek. Provider failures allow the orchestrator to attempt "
        "the next configured provider. HTTP 429 and server errors use "
        "bounded retries and backoff. HTTP 413 triggers recursive "
        "payload splitting. Text chunking uses configurable maximum "
        "length and overlap. Successful extraction responses are "
        "validated as JSON before records are accepted.",
        styles["SmallBody"]
    ))
    story.append(Paragraph(
        "Observed test evidence: Gemini returned HTTP 429 during a "
        "live extraction run, after which Groq successfully processed "
        "records. The extraction run produced 75 entities from 12 "
        "successful source records; 3 source records failed due to "
        "provider timeouts or rate limits. A controlled 413 test and "
        "a successful DeepSeek live test remain outstanding.",
        styles["SmallBody"]
    ))

    story.append(Paragraph("4. Data Quality and Freshness", styles["Section"]))
    story.append(Paragraph(
        "The data audit checks record counts, identity duplicates, "
        "and URL validity. News and job ingestion applies a recent-data "
        "filter. Research paper records include extracted GitHub links "
        "and available repository star counts. Freshness should be "
        "evaluated using source publication timestamps, with missing "
        "or ambiguous timestamps recorded rather than silently treated "
        "as verified.",
        styles["SmallBody"]
    ))

    story.append(Paragraph("5. Scale Strategy: 500k+ Records", styles["Section"]))
    story.append(Paragraph(
        "The current implementation demonstrates bounded asynchronous "
        "crawling and concurrent HTTP requests. It has not been "
        "benchmarked at 500,000 records. To scale, partition source "
        "work into paginated batches and place tasks on a durable "
        "queue. Multiple stateless workers can process batches with "
        "per-domain concurrency limits and rate-limit token buckets. "
        "Use idempotent upserts keyed by canonical identity and source "
        "ID, persist checkpoints, and retry failed batches without "
        "reprocessing completed work.",
        styles["SmallBody"]
    ))
    story.append(Paragraph(
        "A production deployment could store raw responses in object "
        "storage, validated entities and relationships in PostgreSQL, "
        "and optional search indexes in a dedicated search engine. "
        "Metrics should track throughput, latency, retries, error "
        "rates, freshness lag, queue depth and duplicate rates. "
        "Horizontal workers and partitioned ingestion provide the "
        "scaling path; this is a design recommendation, not a measured "
        "500k-record benchmark.",
        styles["SmallBody"]
    ))

    story.append(Paragraph("6. Current Verified Dataset", styles["Section"]))

    summary_rows = [["Dataset", "Records"]]
    for name, count in counts.items():
        summary_rows.append([name, str(count)])

    summary_rows.append(["Total core records", str(
        counts.get("Startups", 0)
        + counts.get("Products", 0)
        + counts.get("Research Papers", 0)
        + counts.get("News", 0)
        + counts.get("Jobs", 0)
    )])

    summary = Table(summary_rows, colWidths=[90 * mm, 40 * mm])
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#292344")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F2F0F7")]),
    ]))
    story.append(summary)

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Additional audit evidence: 1,895 startups, 1,717 products, "
        "and 1,500 research papers were previously audited with zero "
        "duplicate identities and zero invalid URLs. Of the research "
        "papers, 216 had GitHub links and 210 had star counts. A live "
        "crawler test fetched 25 of 25 selected URLs successfully at "
        "concurrency 10. Cloudflare and JavaScript-rendering challenges "
        "were not encountered in that sample.",
        styles["SmallBody"]
    ))

    story.append(Paragraph("7. Known Limitations", styles["Section"]))
    story.append(Paragraph(
        "GitHub star metrics are available for only 210 of 1,500 "
        "research papers. The LLM run had 3 failed source records. "
        "The 25-URL crawl is a functional sample, not a large-scale "
        "performance benchmark. Browser rendering and anti-bot "
        "fallback require a compliant browser or rendering service "
        "and have not been demonstrated in the current test.",
        styles["SmallBody"]
    ))

    doc.build(story)
    print("ARCHITECTURE PDF CREATED:", path)


def make_readme(counts):
    total = sum(counts.get(k, 0) for k in [
        "Startups", "Products", "Research Papers", "News", "Jobs"
    ])

    extraction = load_json("extraction_log.json")
    if extraction and isinstance(extraction[0], dict):
        extraction_info = extraction[0]
    else:
        extraction_info = {}

    text = f"""# FrontierAtlas

AI ecosystem data acquisition, extraction and entity-resolution pipeline.

## Project overview

FrontierAtlas collects and processes structured information about AI startups,
products, research papers, AI news and AI job opportunities.

## Project structure

```text
assignment/
├── src/
│   ├── collectors/
│   ├── llm/
│   ├── storage/
│   └── utils/
├── data/
├── audit_data.py
├── generate_submission.py
├── FrontierAtlas_Output.xlsx
├── Architecture.pdf
└── README.md
```

## Setup

Python 3.10 or later is recommended.

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
```

Install dependencies:

```powershell
pip install aiohttp beautifulsoup4 feedparser python-dotenv python-dateutil pydantic openpyxl reportlab
```

Create a `.env` file in the project root. Add your own API keys:

```text
GITHUB_TOKEN=your_github_token
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
DEEPSEEK_API_KEY=your_deepseek_key
```

Never commit `.env` or share API keys.

## Running the project

Run the data audit:

```powershell
python audit_data.py
```

Run the asynchronous sample crawler:

```powershell
python -m src.collectors.scale_crawler --limit 25 --concurrency 10
```

Run LLM extraction:

```powershell
python -m src.llm.run_extraction
```

Generate final submission files:

```powershell
python generate_submission.py
```

## Current dataset snapshot

| Dataset | Records |
|---|---:|
| Startups | {counts.get('Startups', 0)} |
| Products | {counts.get('Products', 0)} |
| Research Papers | {counts.get('Research Papers', 0)} |
| News | {counts.get('News', 0)} |
| Jobs | {counts.get('Jobs', 0)} |
| **Core total** | **{total}** |

The final workbook contains six sheets: Startups, Products, Research Papers,
News, Jobs and Entity Mapping Log.

## Verified test evidence

- Startup, product and research-paper audit reported zero duplicate identities.
- The audit reported zero invalid URLs in those three datasets.
- Research-paper GitHub links: 216.
- Research-paper GitHub star counts: 210.
- A sample async crawl fetched 25 of 25 URLs at concurrency 10.
- One LLM extraction run produced 75 entities from 12 successful records;
  3 of 15 source records failed due to provider rate limits or timeouts.
- Gemini rate limiting was observed, followed by fallback to Groq.

## Reliability and scalability

The HTTP client implements bounded concurrency, request timeouts, retry handling,
exponential backoff and Retry-After support. The LLM orchestrator supports a
Gemini, Groq and DeepSeek provider chain, JSON validation, text chunking and
HTTP 413 splitting.

The 500k+ record target is addressed through a proposed distributed architecture:
paginated batch ingestion, durable task queues, stateless workers, per-domain
rate limits, idempotent upserts, checkpoints and scalable storage. A 500k-record
benchmark has not been run.

## Known limitations

- GitHub star counts are available for 210 of 1,500 research papers.
- Three source records failed in the recorded LLM extraction run.
- HTTP 413 splitting is implemented but still requires a controlled test.
- DeepSeek live fallback has not yet been demonstrated.
- Cloudflare and JavaScript rendering were not encountered in the 25-URL crawl
  sample; browser-rendering fallback remains a production extension.

## Final files

- `FrontierAtlas_Output.xlsx`: Google Sheets-ready workbook.
- `Architecture.pdf`: architecture and engineering report.
- `README.md`: project setup and execution guide.
"""
    path = OUTPUT / "README.md"
    path.write_text(text, encoding="utf-8")
    print("README CREATED:", path)


def make_requirements():
    requirements = """aiohttp
beautifulsoup4
feedparser
python-dotenv
python-dateutil
pydantic
openpyxl
reportlab
"""
    (OUTPUT / "requirements.txt").write_text(
        requirements, encoding="utf-8"
    )


def make_zip():
    zip_path = OUTPUT / "FrontierAtlas_Submission.zip"

    excluded_dirs = {
        ".venv", "__pycache__", ".git", ".idea", ".pytest_cache"
    }
    excluded_files = {
        ".env", "FrontierAtlas_Submission.zip"
    }

    include_outputs = {
        "FrontierAtlas_Output.xlsx",
        "Architecture.pdf",
        "README.md",
        "requirements.txt"
    }

    with zipfile.ZipFile(
        zip_path, "w", zipfile.ZIP_DEFLATED
    ) as archive:

        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue

            relative = path.relative_to(ROOT)
            parts = set(relative.parts)

            if parts & excluded_dirs:
                continue

            if path.name in excluded_files:
                continue

            if path.suffix in (".pyc", ".pyo"):
                continue

            if path.parts[0] in ("src", "data"):
                archive.write(path, relative)
            elif path.parent == ROOT and (
                path.suffix == ".py"
                or path.name in include_outputs
            ):
                archive.write(path, relative)

    print("SUBMISSION ZIP CREATED:", zip_path)


if __name__ == "__main__":
    print("Generating FrontierAtlas submission files...\n")

    counts = make_workbook()
    make_architecture_pdf(counts)
    make_readme(counts)
    make_requirements()
    make_zip()

    print("\n========== SUBMISSION PACKAGE ==========")
    print("FrontierAtlas_Output.xlsx")
    print("Architecture.pdf")
    print("README.md")
    print("requirements.txt")
    print("FrontierAtlas_Submission.zip")
    print("\nUpload FrontierAtlas_Output.xlsx to Google Sheets.")
