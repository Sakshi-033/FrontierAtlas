
import json
import re
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher

from src.llm.entity_resolver import EntityResolver, normalize_name


DATA_DIR = Path("data")

STARTUP_INPUT = DATA_DIR / "startups.json"
PRODUCT_INPUT = DATA_DIR / "products.json"

STARTUP_OUTPUT = DATA_DIR / "resolved_startups.json"
PRODUCT_OUTPUT = DATA_DIR / "resolved_products.json"
MAPPING_OUTPUT = DATA_DIR / "entity_mapping_log.json"


# 50 unique canonical startup names
CANONICAL_STARTUPS = [
    "OpenAI", "Anthropic", "Google", "Google DeepMind",
    "Microsoft", "Meta", "NVIDIA", "Amazon", "Apple",
    "Mistral AI", "Cohere", "Hugging Face", "Stability AI",
    "Perplexity AI", "Inflection AI", "xAI", "Scale AI",
    "Databricks", "Snowflake", "Palantir", "Runway",
    "ElevenLabs", "Character AI", "Adept AI", "AI21 Labs",
    "DeepSeek", "Midjourney", "Synthesia", "Reka AI",
    "Together AI", "Groq", "Harvey AI", "Glean", "Writer",
    "Pinecone", "Weights & Biases", "LangChain", "Anyscale",
    "Modal", "Replicate", "Baseten", "SambaNova",
    "H2O.ai", "Vercel", "Cursor", "Thinking Machines Lab",
    "Dataminr", "Scale AI Research", "Black Forest Labs",
    "RunPod"
]

STARTUP_ALIASES = {
    "open ai": "OpenAI",
    "google deepmind": "Google DeepMind",
    "deepmind": "Google DeepMind",
    "facebook": "Meta",
    "meta platforms": "Meta",
    "huggingface": "Hugging Face",
    "hugging face": "Hugging Face",
    "mistral": "Mistral AI",
    "deep seek": "DeepSeek",
    "character.ai": "Character AI",
    "x.ai": "xAI",
    "x ai": "xAI",
    "weights and biases": "Weights & Biases",
    "h2o ai": "H2O.ai",
}

PRODUCT_ALIASES = {
    "chat gpt": "ChatGPT",
    "chatgpt": "ChatGPT",
    "claude ai": "Claude",
    "claude chatbot": "Claude",
    "google bard": "Gemini",
    "bard": "Gemini",
    "gemini ai": "Gemini",
    "dall e": "DALL-E",
    "dalle": "DALL-E",
    "stable diffusion ai": "Stable Diffusion",
    "github copilot": "GitHub Copilot",
    "copilot for github": "GitHub Copilot",
    "mid journey": "Midjourney",
}


def load_records(path):
    if not path.exists():
        print(f"WARNING: {path} not found.")
        return []

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("records", "data", "items", "results"):
            if isinstance(data.get(key), list):
                return data[key]

    raise ValueError(f"Unsupported JSON structure in {path}")


def save_records(path, records):
    temp_path = path.with_suffix(".tmp")

    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2, ensure_ascii=False)

    temp_path.replace(path)


def get_content(record):
    if not isinstance(record, dict):
        return {}

    content = record.get("content")

    return content if isinstance(content, dict) else record


def find_field(record, candidates):
    content = get_content(record)

    for field in candidates:
        value = content.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for field in candidates:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def resolve_startup(name, canonical_names):
    normalized = normalize_name(name)

    if normalized in STARTUP_ALIASES:
        return STARTUP_ALIASES[normalized], "ALIAS", 1.0

    canonical_lookup = {
        normalize_name(item): item
        for item in canonical_names
    }

    if normalized in canonical_lookup:
        return canonical_lookup[normalized], "EXACT", 1.0

    matches = [
        (
            SequenceMatcher(None, normalized, key).ratio(),
            value
        )
        for key, value in canonical_lookup.items()
    ]

    if matches:
        score, candidate = max(matches)

        if score >= 0.94:
            return candidate, "FUZZY", round(score, 3)

    return name, "NEW_ENTITY", 0.0


def resolve_product(name):
    normalized = normalize_name(name)

    if normalized in PRODUCT_ALIASES:
        return PRODUCT_ALIASES[normalized], "ALIAS", 1.0

    # Do not merge unrelated products using fuzzy matching.
    return name.strip(), "EXACT_OR_UNVERIFIED", 0.0


def process_startups(records):
    output = []
    mapping = []

    for record in records:
        updated = dict(record)
        name = find_field(
            record,
            ["entityName", "name", "startupName", "companyName"]
        )

        if not name:
            output.append(updated)
            continue

        canonical, match_type, confidence = resolve_startup(
            name, CANONICAL_STARTUPS
        )

        updated["canonicalName"] = canonical
        updated["entityMatchType"] = match_type
        updated["entityMatchConfidence"] = confidence

        mapping.append({
            "entity_type": "STARTUP",
            "original_name": name,
            "canonical_name": canonical,
            "match_type": match_type,
            "confidence": confidence,
        })

        output.append(updated)

    return output, mapping


def process_products(records):
    output = []
    mapping = []

    for record in records:
        updated = dict(record)

        name = find_field(
            record,
            ["productName", "name", "entityName", "title"]
        )

        if not name:
            output.append(updated)
            continue

        canonical, match_type, confidence = resolve_product(name)

        updated["canonicalProductName"] = canonical
        updated["productMatchType"] = match_type
        updated["productMatchConfidence"] = confidence

        startup_name = find_field(
            record,
            ["startupName", "companyName", "company", "developer"]
        )

        if startup_name:
            company, company_type, company_confidence = resolve_startup(
                startup_name, CANONICAL_STARTUPS
            )

            updated["canonicalStartupName"] = company

            mapping.append({
                "entity_type": "STARTUP",
                "original_name": startup_name,
                "canonical_name": company,
                "match_type": company_type,
                "confidence": company_confidence,
            })

        mapping.append({
            "entity_type": "PRODUCT",
            "original_name": name,
            "canonical_name": canonical,
            "match_type": match_type,
            "confidence": confidence,
        })

        output.append(updated)

    return output, mapping


def main():
    print("=" * 55)
    print("FRONTIERATLAS ENTITY RESOLUTION")
    print("=" * 55)

    startups = load_records(STARTUP_INPUT)
    products = load_records(PRODUCT_INPUT)

    print("Startup records loaded:", len(startups))
    print("Product records loaded:", len(products))
    print("Canonical startup seed count:", len(CANONICAL_STARTUPS))

    if len(set(CANONICAL_STARTUPS)) != 50:
        raise ValueError("Canonical seed list must contain 50 unique names.")

    resolved_startups, startup_mapping = process_startups(startups)
    resolved_products, product_mapping = process_products(products)

    all_mappings = startup_mapping + product_mapping

    save_records(STARTUP_OUTPUT, resolved_startups)
    save_records(PRODUCT_OUTPUT, resolved_products)
    save_records(MAPPING_OUTPUT, all_mappings)

    print("\n========== REPORT ==========")
    print("Startups resolved:", len(resolved_startups))
    print("Products resolved:", len(resolved_products))
    print("Mapping entries:", len(all_mappings))

    print("\nStartup match types:")
    for kind in ("EXACT", "ALIAS", "FUZZY", "NEW_ENTITY"):
        count = sum(
            item["match_type"] == kind
            for item in startup_mapping
        )
        print(f"{kind}: {count}")

    print("\nProduct aliases:")
    print(sum(
        item["match_type"] == "ALIAS"
        for item in product_mapping
    ))

    print("\nFiles generated:")
    print(STARTUP_OUTPUT)
    print(PRODUCT_OUTPUT)
    print(MAPPING_OUTPUT)

    print("\nENTITY RESOLUTION COMPLETE")


if __name__ == "__main__":
    main()
