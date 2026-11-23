
from src.schemas import Product
from datetime import datetime, timezone

product = Product(
    source={
        "name": "Example Source",
        "url": "https://example.com"
    },
    content={
        "startupName": "Example AI",
        "pricingModel": "FREEMIUM"
    },
    collectedAt=datetime.now(timezone.utc)
)

print(product.model_dump(mode="json"))
