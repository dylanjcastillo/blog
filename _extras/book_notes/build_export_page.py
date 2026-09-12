"""Refresh the setup page's bookmarklet after editing export_notebooks.js."""
import re
from html import escape
from pathlib import Path
from urllib.parse import quote

folder = Path(__file__).resolve().parent
source = (folder / "export_notebooks.js").read_text()
href = escape("javascript:" + quote(source, safe=""), quote=True)
page = folder / "export_notebooks.html"
html = re.sub(r'(?<=class="bookmark" href=")[^"]+', lambda _: href, page.read_text())
page.write_text(html)
