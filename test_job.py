
from src.schemas import Job
from datetime import datetime, timezone

job = Job(
    content={
        "company": "Google",
        "date": datetime.now(timezone.utc),
        "is_remote": True,
        "role_family": "AI Engineer"
    }
)

print(job.model_dump(mode="json"))
