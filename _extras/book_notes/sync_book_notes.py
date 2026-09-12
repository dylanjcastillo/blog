"""Import all data/kindle/kindle-notebooks-*.json exports and rebuild book pages."""
import json

import build_book_notes as build
from import_notebook import import_books


def main():
    exports = []
    for path in build.DATA_DIR.glob("kindle-notebooks-*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or not isinstance(payload.get("books"), list):
            raise ValueError(f"Not a supported notebook export: {path}")
        exports.append((payload.get("exported_at", path.name), path, payload))
    for _, path, payload in sorted(exports, key=lambda item: item[0]):
        imported = import_books(payload["books"])
        print(f"Imported {len(imported)} books from {path.name}.")
        if not payload.get("complete"):
            print("  Export marked partial; imported the supplied book records and retained previous captures.")
    build.main()


if __name__ == "__main__":
    main()
