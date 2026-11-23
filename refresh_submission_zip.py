from pathlib import Path
import zipfile

root = Path.cwd()
output = root / "FrontierAtlas_Submission.zip"

excluded = {
    ".env", ".venv", ".git", "__pycache__",
    ".pytest_cache", ".idea"
}

required = [
    "FrontierAtlas_Output.xlsx",
    "Architecture.pdf",
    "README.md",
    "requirements.txt",
]

missing = [name for name in required if not (root / name).exists()]
if missing:
    raise SystemExit(f"Missing required files: {missing}")

files = []

for folder in ("src", "data"):
    path = root / folder
    if path.exists():
        files.extend(p for p in path.rglob("*") if p.is_file())

for path in root.iterdir():
    if path.is_file() and (
        path.suffix == ".py"
        or path.name in required
        or path.name == ".gitignore"
    ):
        files.append(path)

with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        relative = path.relative_to(root)

        if any(part in excluded for part in relative.parts):
            continue

        if path.suffix in (".pyc", ".pyo"):
            continue

        archive.write(path, relative)

with zipfile.ZipFile(output) as archive:
    names = archive.namelist()

    print("ZIP refreshed:", output.name)
    print("Files:", len(names))
    print("Workbook included:",
          "FrontierAtlas_Output.xlsx" in names)
    print("Architecture included:",
          "Architecture.pdf" in names)
    print("README included:",
          "README.md" in names)
    print("Source files:", sum(
        n.startswith("src/") and n.endswith(".py")
        for n in names
    ))
    print("Secrets excluded:", not any(
        Path(n).name == ".env" for n in names
    ))
    print("Virtual environment excluded:", not any(
        ".venv/" in n.replace("\\", "/") for n in names
    ))
