import json
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

root = Path.cwd()
data = json.load(open(root / "data" / "news.json", encoding="utf-8"))

wb = load_workbook(root / "FrontierAtlas_Output.xlsx")
ws = wb["News"]

headers = [
    "Article ID",
    "Publisher",
    "Article Title",
    "Article URL",
    "Published At",
    "Summary",
    "Full Text",
    "Content Status",
    "Record Type"
]

ws.delete_rows(1, ws.max_row)
ws.append(headers)

for item in data:
    ws.append([
        item.get("id", ""),
        item.get("source", ""),
        item.get("title", ""),
        item.get("url", ""),
        item.get("published_at", ""),
        item.get("summary", ""),
        item.get("full_text", ""),
        item.get("content_status", ""),
        item.get("record_type", "")
    ])

ws.freeze_panes = "A2"
ws.auto_filter.ref = ws.dimensions
ws.row_dimensions[1].height = 32

widths = [24, 22, 48, 65, 27, 55, 80, 20, 16]

for index, width in enumerate(widths, 1):
    ws.column_dimensions[get_column_letter(index)].width = width

for cell in ws[1]:
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="292344")
    cell.alignment = Alignment(
        horizontal="center",
        vertical="center",
        wrap_text=True
    )

for row in ws.iter_rows(min_row=2):
    for cell in row:
        cell.alignment = Alignment(
            vertical="top",
            wrap_text=True
        )

    url_cell = row[3]
    if url_cell.value:
        url_cell.hyperlink = str(url_cell.value)
        url_cell.style = "Hyperlink"

wb.save(root / "FrontierAtlas_Output.xlsx")
print("News tab corrected successfully.")
print("Records:", len(data))
print("Columns:", len(headers))
