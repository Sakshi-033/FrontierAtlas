import json
import time
import tracemalloc
from pathlib import Path
from datetime import datetime, timezone

TOTAL_RECORDS = 500_000
BATCH_SIZE = 5_000


def generate_records(total):
    """Generate synthetic records without loading all records into memory."""
    for i in range(total):
        yield {
            "id": i,
            "name": f"AI Entity {i}",
            "url": f"https://example.com/entity/{i}",
            "type": "STARTUP" if i % 2 == 0 else "PRODUCT"
        }


def process_batch(batch):
    """Simulate lightweight validation and processing."""
    valid = 0

    for record in batch:
        if (
            record["id"] >= 0
            and record["name"]
            and record["url"].startswith("https://")
        ):
            valid += 1

    return valid


def run_benchmark():
    print("FRONTIERATLAS SCALE BENCHMARK")
    print("=" * 45)
    print("Records:", f"{TOTAL_RECORDS:,}")
    print("Batch size:", f"{BATCH_SIZE:,}")

    tracemalloc.start()
    start = time.perf_counter()

    generator = generate_records(TOTAL_RECORDS)

    processed = 0
    valid = 0
    batches = 0

    while True:
        batch = []

        try:
            for _ in range(BATCH_SIZE):
                batch.append(next(generator))
        except StopIteration:
            pass

        if not batch:
            break

        valid += process_batch(batch)
        processed += len(batch)
        batches += 1

        if batches % 20 == 0:
            print(f"Processed: {processed:,}/{TOTAL_RECORDS:,}")

    elapsed = time.perf_counter() - start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    report = {
        "benchmark_type": "synthetic_local_batch_processing",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "records_generated": TOTAL_RECORDS,
        "records_processed": processed,
        "valid_records": valid,
        "batch_size": BATCH_SIZE,
        "batches": batches,
        "elapsed_seconds": round(elapsed, 3),
        "records_per_second": round(processed / elapsed, 2),
        "peak_traced_memory_mb": round(peak / (1024 * 1024), 2),
        "note": (
            "Synthetic local processing benchmark. "
            "Not a live network crawling benchmark."
        )
    }

    Path("data").mkdir(exist_ok=True)

    with open(
        "data/scale_benchmark_report.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(report, f, indent=2)

    print("\nBENCHMARK RESULT")
    print("=" * 45)
    print("Processed:", f"{processed:,}")
    print("Valid:", f"{valid:,}")
    print("Batches:", batches)
    print("Time:", elapsed, "seconds")
    print("Throughput:", report["records_per_second"], "records/sec")
    print("Peak memory:", report["peak_traced_memory_mb"], "MB")
    print("Saved: data/scale_benchmark_report.json")


if __name__ == "__main__":
    run_benchmark()
