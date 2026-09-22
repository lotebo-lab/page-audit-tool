"""Short check: dataset_schema.json fields vs. what the code actually writes.

Compares three sets of field names:
  1. declared  -- .actor/dataset_schema.json `fields.properties`
  2. code_row  -- a call to `src.page_checks.check_page`, the function
                  `src/main.py` uses to build every dataset row
  3. run_row   -- a real dataset item written by a local end-to-end run
                  (path given as the first argument)

Usage:
    ../../.venv/bin/python tests/compare_dataset_fields.py <run-dir>
"""

from __future__ import annotations

import glob
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.page_checks import check_page  # noqa: E402

run_dir = sys.argv[1] if len(sys.argv) > 1 else None

declared = set(
    json.loads((ROOT / ".actor" / "dataset_schema.json").read_text())["fields"][
        "properties"
    ]
)
code_row = set(
    check_page(
        "https://example.com",
        200,
        "<html><head><title>t</title></head><body><h1>h</h1></body></html>",
    )
)

run_fields: set[str] = set()
if run_dir:
    items = sorted(glob.glob(str(pathlib.Path(run_dir) / "storage" / "datasets" / "default" / "*.json")))
    if items:
        run_fields = set(json.loads(pathlib.Path(items[0]).read_text()))

print("dataset_schema.json fields :", sorted(declared))
print("check_page() row fields    :", sorted(code_row))
if run_dir:
    print("actual dataset item fields :", sorted(run_fields))

ok = declared == code_row
print("schema == check_page():", ok)
if run_dir:
    ok = ok and declared == run_fields and code_row == run_fields
    print("schema == actual dataset item:", declared == run_fields)
    print("check_page() == actual dataset item:", code_row == run_fields)

print("RESULT:", "MATCH" if ok else "MISMATCH")
sys.exit(0 if ok else 1)
