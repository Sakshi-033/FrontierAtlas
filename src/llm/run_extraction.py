import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone

from src.llm.orchestrator import LLMOrchestrator

DATA_DIR = Path("data")


def load_records(filename):
    path = DATA_DIR / filename
    if not path.exists():
        return []

    with open(path, encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("records", data.get("items", []))
    return []


def get_text(record):
    fields = [
        "title", "name", "description", "content",
        "full_text", "summary", "text", "company",
        "job_title", "source"
    ]

    return "\n".join(
        f"{field}: {record[field]}"
        for field in fields
        if isinstance(record.get(field), str) and record[field].strip()
    )


async def main():
    news = load_records("news.json")
    jobs = load_records("jobs.json")
    records = [("NEWS", x) for x in news] + [("JOB", x) for x in jobs]

    print(f"Records to process: {len(records)}")

    engine = LLMOrchestrator(
        max_retries=3,
        max_chars=6000,
        overlap=300,
        timeout=90
    )

    extracted = []
    logs = []

    for index, (kind, record) in enumerate(records, 1):
        text = get_text(record)

        if not text:
            logs.append({
                "record": index,
                "type": kind,
                "status": "SKIPPED",
                "reason": "No usable text"
            })
            continue

        print(f"\n[{index}/{len(records)}] {kind}")

        success = False
        error_message = ""

        for attempt in range(2):
            try:
                result = await engine.extract(text)
                entities = result.get("records", [])

                for entity in entities:
                    if isinstance(entity, dict):
                        item = dict(entity)
                        item["source_type"] = kind
                        item["source_title"] = (
                            record.get("title")
                            or record.get("name")
                            or record.get("job_title")
                            or ""
                        )
                        extracted.append(item)

                logs.append({
                    "record": index,
                    "type": kind,
                    "status": "SUCCESS",
                    "entities_found": len(entities),
                    "attempt": attempt + 1
                })

                print(f"Success: {len(entities)} entities")
                success = True
                break

            except Exception as error:
                error_message = str(error)
                print(f"Attempt {attempt + 1} failed: {error_message}")
                await asyncio.sleep(10 * (attempt + 1))

        if not success:
            logs.append({
                "record": index,
                "type": kind,
                "status": "FAILED",
                "error": error_message
            })

        await asyncio.sleep(5)

    DATA_DIR.mkdir(exist_ok=True)

    with open(DATA_DIR / "extracted_entities.json", "w", encoding="utf-8") as file:
        json.dump(extracted, file, indent=2, ensure_ascii=False)

    with open(DATA_DIR / "extraction_log.json", "w", encoding="utf-8") as file:
        json.dump({
            "run_at": datetime.now(timezone.utc).isoformat(),
            "total_input_records": len(records),
            "total_entities": len(extracted),
            "successful": sum(x["status"] == "SUCCESS" for x in logs),
            "failed": sum(x["status"] == "FAILED" for x in logs),
            "records": logs
        }, file, indent=2, ensure_ascii=False)

    print("\n========== FINAL EXTRACTION REPORT ==========")
    print("Input records:", len(records))
    print("Entities extracted:", len(extracted))
    print("Successful:", sum(x["status"] == "SUCCESS" for x in logs))
    print("Failed:", sum(x["status"] == "FAILED" for x in logs))
    print("Saved data/extracted_entities.json")
    print("Saved data/extraction_log.json")


if __name__ == "__main__":
    asyncio.run(main())
