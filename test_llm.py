
from src.llm.orchestrator import LLMOrchestrator, TextChunker

# Test 1: Chunking
chunker = TextChunker(max_chars=1000, overlap=100)
sample_text = "Artificial intelligence research. " * 200

chunks = chunker.split(sample_text)

print("TEST 1: TEXT CHUNKING")
print("Original characters:", len(sample_text))
print("Chunks generated:", len(chunks))
print("Largest chunk:", max(map(len, chunks)))

assert len(chunks) > 1
assert all(len(chunk) <= 1000 for chunk in chunks)

# Test 2: Provider configuration
engine = LLMOrchestrator()

print("\nTEST 2: PROVIDER CONFIGURATION")
available = engine.available_providers()

if available:
    print("Available:", [p["name"] for p in available])
else:
    print("No LLM credentials configured yet.")

# Test 3: JSON validation
print("\nTEST 3: JSON PARSING")

result = engine.parse_json(
    '{"records": [{"entity_name": "Example AI"}]}'
)

assert len(result["records"]) == 1
print("JSON parsing: SUCCESS")

print("\nALL OFFLINE TESTS PASSED")
