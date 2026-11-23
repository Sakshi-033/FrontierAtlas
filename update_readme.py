from pathlib import Path

readme = Path("README.md")
text = readme.read_text(encoding="utf-8")

section = """

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
"""

if "## 500k Synthetic Scale Benchmark" not in text:
    readme.write_text(text + section, encoding="utf-8")

print("README updated with benchmark evidence.")
