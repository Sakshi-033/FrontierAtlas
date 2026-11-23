# FrontierAtlas

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
.\.venv\Scripts\Activate.ps1
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
| Startups | 1895 |
| Products | 1717 |
| Research Papers | 1500 |
| News | 6 |
| Jobs | 9 |
| **Core total** | **5127** |

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


## 500k Synthetic Scale Benchmark

A local synthetic batch-processing benchmark was executed.

| Metric | Result |
|---|---:|
| Records generated | 500,000 |
| Records processed | 500,000 |
| Valid records | 500,000 |
| Batch size | 5,000 |
| Total batches | 100 |
| Execution time | 8.23 seconds |
| Throughput | 60,761.75 records/second |
| Peak traced memory | 1.7 MB |

The benchmark uses generated records and local processing. It demonstrates
batch-processing and memory-conscious iteration, not 500,000 live network
requests or distributed crawler performance.

Detailed results: `data/scale_benchmark_report.json`.
Reproduce using: `python benchmark_scale.py`.
