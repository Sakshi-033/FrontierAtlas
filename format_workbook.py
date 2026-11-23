import json
import re
import zipfile
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

ROOT = Path.cwd()
DATA = ROOT / "data"

SHEETS = {
    "Startups": "startups.json",
    "Products": "products.json",
    "Research Papers": "research_papers.json",
    "News": "news.json",
    "Jobs": "jobs.json",
    "Entity Mapping Log": "entity_mapping_log.json",
}


def load_records(filename):
    path = DATA / filename

    if not path.exists():
        print("Missing:", filename)
        return []

    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("records", "items", "data", "mappings", "logs"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]

    return []


def flatten(record, prefix=""):
    result = {}

    if not isinstance(record, dict):
        return {prefix or "Value": record}

    for key, value in record.items():
        path = f"{prefix}_{key}" if prefix else str(key)

        if isinstance(value, dict):
            result.update(flatten(value, path))

        elif isinstance(value, list):
            if all(not isinstance(x, (dict, list)) for x in value):
                result[path] = "; ".join(str(x) for x in value)
            else:
                result[path] = json.dumps(
                    value, ensure_ascii=False
                )

        else:
            result[path] = value

    return result


def friendly_name(key):
    key = key.replace("_", " ")
    key = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
    key = re.sub(r"([A-Z])([A-Z][a-z])", r"\1 \2", key)
    return key.strip().title()


def format_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def build_workbook():
    wb = Workbook()
    wb.remove(wb.active)

    summary = []

    for sheet_name, filename in SHEETS.items():
        records = load_records(filename)
        flattened = [
            flatten(record) if isinstance(record, dict)
            else {"Value": record}
            for record in records
        ]

        headers = []
        for record in flattened:
            for key in record:
                if key not in headers:
                    headers.append(key)

        ws = wb.create_sheet(sheet_name)

        if not headers:
            headers = ["Status"]
            ws.append(headers)
            ws.append(["No records available"])
        else:
            display_headers = [friendly_name(h) for h in headers]
            ws.append(display_headers)

            for record in flattened:
                ws.append([
                    format_value(record.get(header))
                    for header in headers
                ])

        # Professional formatting
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        ws.row_dimensions[1].height = 32

        for cell in ws[1]:
            cell.font = Font(
                bold=True, color="FFFFFF", size=10
            )
            cell.fill = PatternFill(
                "solid", fgColor="292344"
            )
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True
            )

        for column in ws.columns:
            letter = get_column_letter(column[0].column)
            max_width = 12

            for cell in column:
                cell.alignment = Alignment(
                    vertical="top", wrap_text=True
                )
                max_width = max(
                    max_width,
                    min(len(str(cell.value or "")), 42)
                )

                if (
                    isinstance(cell.value, str)
                    and cell.value.startswith(("https://", "http://"))
                ):
                    cell.hyperlink = cell.value
                    cell.style = "Hyperlink"

            ws.column_dimensions[letter].width = min(
                max_width + 2, 44
            )

        summary.append((sheet_name, len(records)))
        print(f"{sheet_name}: {len(records)} records, {len(headers)} columns")

    output = ROOT / "FrontierAtlas_Output.xlsx"
    wb.save(output)

    print("\nUpdated workbook:", output)
    return summary


def rebuild_zip():
    output = ROOT / "FrontierAtlas_Submission.zip"

    excluded_dirs = {
        ".venv", "__pycache__", ".git",
        ".idea", ".pytest_cache"
    }
    excluded_files = {
        ".env", output.name
    }

    with zipfile.ZipFile(
        output, "w", zipfile.ZIP_DEFLATED
    ) as archive:

        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue

            relative = path.relative_to(ROOT)

            if set(relative.parts) & excluded_dirs:
                continue

            if path.name in excluded_files:
                continue

            if path.suffix in (".pyc", ".pyo"):
                continue

            if (
                relative.parts[0] in ("src", "data")
                or (
                    len(relative.parts) == 1
                    and (
                        path.suffix == ".py"
                        or path.name in {
                            "FrontierAtlas_Output.xlsx",
                            "Architecture.pdf",
                            "README.md",
                            "requirements.txt"
                        }
                    )
                )
            ):
                archive.write(path, relative)

    print("Updated ZIP:", output)


if __name__ == "__main__":
    print("Formatting FrontierAtlas workbook...\n")
    build_workbook()
    rebuild_zip()
    print("\nFORMATTING COMPLETE")
