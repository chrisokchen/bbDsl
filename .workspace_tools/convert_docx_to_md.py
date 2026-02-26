import sys
from pathlib import Path
import mammoth
from markdownify import markdownify as md

if len(sys.argv) < 2:
    print("Usage: convert_docx_to_md.py <input.docx> [output.md]")
    sys.exit(1)

in_path = Path(sys.argv[1])
if not in_path.exists():
    print(f"Input file not found: {in_path}")
    sys.exit(2)

out_path = Path(sys.argv[2]) if len(sys.argv) >=3 else in_path.with_suffix('.md')

with in_path.open('rb') as docx_file:
    result = mammoth.convert_to_html(docx_file)
    html = result.value  # The generated HTML

# Convert HTML to Markdown
markdown = md(html, heading_style="ATX")

out_path.write_text(markdown, encoding='utf-8')
print(f"Converted '{in_path}' -> '{out_path}'")
