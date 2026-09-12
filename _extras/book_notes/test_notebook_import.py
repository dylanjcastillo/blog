import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import build_book_notes as build
import import_notebook as importer


class NotebookImportTests(unittest.TestCase):
    def test_pairs_each_highlight_with_its_own_reference(self):
        html = '''<div id="annotation-scroller"><h3>Example</h3>
        <span>Last accessed on<span>Sunday, July 12, 2026</span></span>
        <input name="secret" value="do-not-export"><div id="kp-notebook-annotations">
        <div><span id="annotationHighlightHeader">Location: 5</span>Unavailable</div>
        <div><span id="highlight">First &amp; second</span>
        <span id="annotationHighlightHeader">Location: 20</span></div>
        <div><span id="annotationHighlightHeader">Location: 40</span>
        <span id="highlight">Third</span></div></div></div>'''
        result = importer.extract(html)
        self.assertEqual(result["unavailable_highlights"], 1)
        self.assertEqual(result["last_accessed"], "2026-07-12")
        self.assertEqual(result["highlights"], [
            {"text":"First & second", "reference":"Location: 20"},
            {"text":"Third", "reference":"Location: 40"}])
        self.assertNotIn("do-not-export", json.dumps(result))

    def test_rejects_login_or_unloaded_page(self):
        with self.assertRaises(ValueError):
            importer.extract('<html><h1>Sign in</h1></html>')

    def test_merge_matches_title_and_preserves_previous_captures(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            notebooks = output / "_notebooks"
            (output / "example.qmd").write_text('---\ntitle: "Example"\nsubtitle: "Author"\n---\n')
            book = {"title":"Example: A Subtitle", "author":"Author", "highlights":[
                {"text":"One", "reference":"Location: 1"}]}
            with patch.object(importer, "OUTPUT_DIR", output), patch.object(importer, "NOTEBOOKS_DIR", notebooks):
                book["last_accessed"] = "Sunday, July 12, 2026"
                book["asin"] = "B012345678"
                book["cover_url"] = "https://m.media-amazon.com/images/I/example.jpg"
                importer.import_books([book])
                del book["last_accessed"]
                del book["cover_url"]
                book["highlights"] = [{"text":"Two", "reference":"Location: 2"}]
                importer.import_books([book])
                book["last_accessed"] = "2024-01-01"
                importer.import_books([book])
            data = json.loads((notebooks / "example.json").read_text())
            self.assertEqual(data["title"], "Example")
            self.assertEqual({x["text"] for x in data["highlights"]}, {"One", "Two"})
            self.assertEqual(len(data["highlights"]), 2)
            self.assertEqual(data["last_accessed"], "2026-07-12")
            self.assertEqual(data["asin"], "B012345678")
            self.assertEqual(data["cover_url"], "https://m.media-amazon.com/images/I/example.jpg")

    def test_book_metadata_rejects_invalid_urls_and_identifiers(self):
        for book in ({"asin":"invalid"}, {"cover_url":"javascript:alert(1)"},
                     {"cover_url":"https://media-amazon.com.evil.test/cover.jpg"}):
            with self.assertRaises(ValueError):
                importer.book_metadata(book)
        self.assertIsNone(importer.book_metadata({"asin":"B098765432"},
                          {"asin":"B012345678", "cover_url":"https://m.media-amazon.com/old.jpg"})["cover_url"])

    def test_render_passes_cover_and_amazon_link_to_header(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "example.json").write_text(json.dumps({"highlights":[],
                "asin":"B012345678", "cover_url":"https://m.media-amazon.com/images/I/example.jpg"}))
            with patch.object(build, "NOTEBOOKS_DIR", path):
                page = build.render_book("Example", "Author", [], "My take.")
            self.assertIn('book-cover: "https://m.media-amazon.com/images/I/example.jpg"', page)
            self.assertIn('amazon-url: "https://www.amazon.com/dp/B012345678"', page)
            self.assertNotIn('![Cover', page)
            self.assertIn('## Notes\n\nMy take.', page)

    def test_invalid_access_date_rejected(self):
        with self.assertRaises(ValueError):
            importer.normalize_access_date("Sunday, February 30, 2026")

    def test_render_uses_latest_reading_activity(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            notebook = path / "example.json"
            clipping = build.Clipping("Example", "Highlight", None, 1, None,
                                      datetime(2024, 1, 1), "Passage")
            with patch.object(build, "NOTEBOOKS_DIR", path):
                notebook.write_text(json.dumps({"highlights":[], "last_accessed":"2026-07-12"}))
                self.assertIn("date: 2026-07-12\n", build.render_book("Example", "Author", [clipping], ""))
                self.assertIn("date: 2026-07-12\n", build.render_book("Example", "Author", [], ""))
                notebook.write_text(json.dumps({"highlights":[], "last_accessed":"2023-01-01"}))
                self.assertIn("date: 2024-01-01\n", build.render_book("Example", "Author", [clipping], ""))

    def test_render_keeps_take_and_deduplicates_different_locations(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "example.json").write_text(json.dumps({"highlights":[
                {"text":"First Second", "reference":"Location: 99"},
                {"text":"New highlight", "reference":"Location: 100"}]}))
            clipping = build.Clipping("Example", "Highlight", "2", 10, None,
                                      datetime(2024, 1, 1), "1. First 2. Second")
            with patch.object(build, "NOTEBOOKS_DIR", path):
                page = build.render_book("Example", "Author", [clipping], "My own take.")
                cloud_only = build.render_book("Example", "Author", [], "")
            self.assertIn("highlights: 2", page)
            self.assertIn("My own take.", page)
            self.assertIn("Page 2, location 10", page)
            self.assertNotIn("Location: 99", page)
            self.assertIn("Location: 100", page)
            self.assertIn("date: 2024-01-01\n", page)
            self.assertIn("date: 1970-01-01\n", cloud_only)
            self.assertNotIn("device’s clippings", cloud_only)


if __name__ == "__main__":
    unittest.main()
