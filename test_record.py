from src.schemas import Source, DataRecord
from datetime import datetime, timezone

record = DataRecord(
    recordType="STARTUP",
    source=Source(
        name="Example Source",
        url="https://example.com"
    ),
    content={
        "entityName": "Example AI",
        "description": "AI technology company"
    },
    collectedAt=datetime.now(timezone.utc)
)

print(record.model_dump(mode="json", by_alias=True))