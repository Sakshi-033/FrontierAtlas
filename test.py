
from src.schemas import Product
from datetime import datetime, timezone

product = Product(
    source={
        "name": "Product Hunt",
        "url": "https://www.producthunt.com/"
    },
    content={
        "productName": "ChatGPT",
        "startupName": "OpenAI",
        "pricingModel": "FREEMIUM"
    },
    collectedAt=datetime.now(timezone.utc)
)

print(product.model_dump(mode="json"))
