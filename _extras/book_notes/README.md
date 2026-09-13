# Book notes

Personal takes live in `books/_takes/`. Generated book pages combine those takes,
`data/kindle/My Clippings.txt`, and online notebook imports in
`data/kindle/notebooks/`. Place downloaded `kindle-notebooks-*.json` exports in
`data/kindle/` and run this command to import them all and rebuild:

```sh
python3 _extras/book_notes/sync_book_notes.py
```

Raw and extracted source data stay in the Git-ignored `data/` directory. Generated
pages and personal takes remain in `books/`.
Each book presents all imported passages together under one Highlights section.
Only books with at least three combined, deduplicated highlights or a personal
take get a generated page. Excluded books keep their source data and take files,
so a later import or a new take can bring them back into the reading log.

## Export all online notebooks without a subscription

Open `export_notebooks.html` in your browser and drag its **Export Kindle highlights**
button into the bookmarks bar. Visit <https://read.amazon.com/notebook>, sign in,
and click the bookmark. Leave that tab open while it loads each book and downloads
one JSON file. The progress box can stop the export and save what it has collected.
The export also includes each book’s ASIN and cover image URL. Generated book pages
show a small cover beside the title that links to the book on Amazon. Books with an
ASIN but no cover fall back to a “View on Amazon” text link beside the last read date. The shared `title-block.html` partial keeps this header
consistent, including books without covers. Images are loaded
from Amazon; links use amazon.com and contain no affiliate tags. Older exports
already contain ASINs, but need a fresh export to capture the covers.

The script uses the existing page, clicks book links, and scrolls to load all pages.
It makes no third-party requests and exports no credentials. Failed books and
content unavailable as text are reported in the JSON. Only books accessible in the
online notebook are included; Amazon export limits still apply.

This is an on-demand bulk export, not unattended background synchronization. The
exporter depends on Amazon's current page structure and needs a signed-in session.

```sh
python3 _extras/book_notes/sync_book_notes.py
```

The importer keeps existing captures on retries and matches known book titles to
their existing takes. The exporter captures Amazon’s “Last accessed on” date as
`last_accessed`; the importer normalizes it to ISO format and preserves it when
older exports are reimported. “Last read” uses the later of that date and the last
device highlight date. Existing exports without this field need to be rerun with
the updated bookmarklet to recover access dates.
Books without either date use `1970-01-01` as a sorting
placeholder, placing them after dated books in the descending date listing.
Review title matches when importing different editions with substantially different
names. Exact text matches ignore typography and list labels; different passages
are preserved even when their locations coincide across editions.

## Import one saved page

Firefox's **Save Page As → Web Page, complete** preserves the loaded notebook.
Keep this raw HTML outside the repository because it can contain session metadata.

```sh
python3 _extras/book_notes/import_notebook.py /path/to/notebook.html 100m-offers
python3 _extras/book_notes/build_book_notes.py
```

## Checks

```sh
python3 -m unittest discover -s _extras/book_notes -p 'test_*.py'
node --check _extras/book_notes/export_notebooks.js
```

After changing `export_notebooks.js`, regenerate the bookmarklet link in
`export_notebooks.html` with `build_export_page.py`.
