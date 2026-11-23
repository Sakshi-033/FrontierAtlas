
import json
import re
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher


SEED_STARTUPS = [
    "OpenAI", "Anthropic", "Google", "Google DeepMind",
    "Microsoft", "Meta", "NVIDIA", "Amazon", "Apple",
    "Mistral AI", "Cohere", "Hugging Face", "Stability AI",
    "Perplexity AI", "Inflection AI", "xAI", "Scale AI",
    "Databricks", "Snowflake", "Palantir", "Runway",
    "ElevenLabs", "Character AI", "Adept AI", "AI21 Labs",
    "DeepMind", "DeepSeek", "Midjourney", "Synthesia",
    "Reka AI", "Together AI", "Groq", "Wiz",
    "Harvey AI", "Glean", "Writer", "Pinecone",
    "Weights & Biases", "LangChain", "Anyscale",
    "Modal", "Replicate", "Baseten", "SambaNova",
    "Scale AI", "H2O.ai", "Vercel", "Cursor",
    "Thinking Machines Lab", "Perplexity"
]


ALIASES = {
    "openai": "OpenAI",
    "open ai": "OpenAI",
    "anthropic": "Anthropic",
    "google deepmind": "Google DeepMind",
    "deepmind": "Google DeepMind",
    "google": "Google",
    "meta platforms": "Meta",
    "facebook": "Meta",
    "nvidia corporation": "NVIDIA",
    "huggingface": "Hugging Face",
    "hugging face": "Hugging Face",
    "mistral": "Mistral AI",
    "mistral ai": "Mistral AI",
    "stability": "Stability AI",
    "x.ai": "xAI",
    "x ai": "xAI",
    "deep seek": "DeepSeek",
    "character.ai": "Character AI",
    "ai21": "AI21 Labs",
    "weights and biases": "Weights & Biases",
    "weights biases": "Weights & Biases",
    "h2o": "H2O.ai",
    "h2o ai": "H2O.ai",
}


def normalize_name(name):
    """Normalize a name for deterministic comparison."""
    if not name:
        return ""

    value = unicodedata.normalize("NFKD", str(name))
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


class EntityResolver:
    def __init__(self, mapping_path="data/entity_mapping_log.json"):
        self.mapping_path = Path(mapping_path)
        self.mapping_path.parent.mkdir(
            parents=True, exist_ok=True
        )

        self.canonical = {
            normalize_name(name): name
            for name in SEED_STARTUPS
        }

        self.mapping_log = self.load_log()

    def load_log(self):
        if not self.mapping_path.exists():
            return []

        try:
            with self.mapping_path.open(
                "r", encoding="utf-8"
            ) as file:
                data = json.load(file)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def resolve(self, name, entity_type="STARTUP"):
        original = str(name or "").strip()

        if not original:
            return {
                "original_name": original,
                "canonical_name": None,
                "match_type": "INVALID",
                "confidence": 0.0,
            }

        normalized = normalize_name(original)

        if entity_type.upper() != "STARTUP":
            return {
                "original_name": original,
                "canonical_name": original,
                "match_type": "UNRESOLVED_TYPE",
                "confidence": 0.0,
            }

        alias_target = ALIASES.get(normalized)

        if alias_target:
            return self.record(
                original, alias_target, "ALIAS", 1.0
            )

        if normalized in self.canonical:
            return self.record(
                original,
                self.canonical[normalized],
                "EXACT",
                1.0,
            )

        # Only accept very strong fuzzy matches.
        matches = [
            (
                SequenceMatcher(
                    None, normalized, candidate
                ).ratio(),
                canonical_name,
            )
            for candidate, canonical_name
            in self.canonical.items()
        ]

        if matches:
            score, candidate = max(matches)

            if score >= 0.94:
                return self.record(
                    original,
                    candidate,
                    "FUZZY",
                    round(score, 3),
                )

        # Never force an uncertain name into an unrelated entity.
        return self.record(
            original,
            original,
            "NEW_ENTITY",
            0.0,
        )

    def record(self, original, canonical, match_type, confidence):
        result = {
            "original_name": original,
            "canonical_name": canonical,
            "match_type": match_type,
            "confidence": confidence,
        }

        self.mapping_log.append(result)
        return result

    def save_log(self):
        temp_path = self.mapping_path.with_suffix(".tmp")

        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(
                self.mapping_log,
                file,
                indent=2,
                ensure_ascii=False,
            )

        temp_path.replace(self.mapping_path)

    def resolve_records(self, records):
        resolved = []

        for record in records:
            content = record.get("content", record)

            if not isinstance(content, dict):
                continue

            name = (
                content.get("entityName")
                or content.get("entity_name")
                or content.get("startupName")
                or content.get("company")
            )

            entity_type = (
                record.get("recordType")
                or record.get("entity_type")
                or "STARTUP"
            )

            result = self.resolve(name, entity_type)

            updated = dict(record)
            updated["canonicalName"] = result["canonical_name"]
            updated["entityMatchType"] = result["match_type"]
            updated["entityMatchConfidence"] = result["confidence"]

            resolved.append(updated)

        self.save_log()
        return resolved


if __name__ == "__main__":
    resolver = EntityResolver()

    examples = [
        "Open AI",
        "Anthropic",
        "Google DeepMind",
        "HuggingFace",
        "Deep Seek",
        "New Example AI Startup",
    ]

    for name in examples:
        print(name, "->", resolver.resolve(name))

    resolver.save_log()
    print("\nMapping log saved:", resolver.mapping_path)
