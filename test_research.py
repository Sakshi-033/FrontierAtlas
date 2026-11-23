from src.schemas import ResearchPaper
from datetime import datetime, timezone

paper = ResearchPaper(
    content={
        "title": "Example Research Paper",
        "authors": ["John Smith", "Jane Doe"],
        "paper_url": "https://arxiv.org/abs/1706.03762",
        "published_date": datetime.now(timezone.utc)
    }
)

print(paper.model_dump(mode="json"))