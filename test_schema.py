from src.schemas import Startup
from datetime import datetime, timezone

startup = Startup(
    source={
        "name": "Example Source",
        "url": "https://example.com"
    },
    content={
        "entityName": "Example AI",
        "data": {
            "employeeCount": 100
        }
    },
    collectedAt=datetime.now(timezone.utc)
)

print(startup.model_dump(mode="json"))