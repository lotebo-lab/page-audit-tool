"""Checks the .actor JSON files parse and agree with the code that runs.

pytest is not installed in the lab sandbox and `pip install` has no network
there, so this file is a runner of its own, in plain Python. Run it from the
Actor directory:

    ../../.venv/bin/python tests/test_schemas.py

What it verifies:

1. actor.json, dataset_schema.json and output_schema.json are valid JSON (and
   so is input_schema.json, which the Apify CLI also checks);
2. actor.json points at the dataset schema through `storages.dataset` and at
   the output schema through `output`, and both files exist;
3. the pay-per-event block has exactly two events, `page-audited` at
   US$ 0.05 and `site-report` at US$ 0.25, the same two names the charging
   code in src/main.py uses;
4. every field named in a dataset_schema view exists in a dataset row that
   src/main.py actually pushes. The rows are built here by calling the same
   functions main.py calls (`page_checks.check_page` for a normal page and for
   a request that returned nothing, `summary_row.build_summary_row` for the run
   summary);
5. src/main.py writes the summary row on every successful run, outside any
   `if rows:` gate, and writing it charges nothing.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ACTOR_DIR = ROOT / ".actor"
sys.path.insert(0, str(ROOT))

from src.page_checks import check_page  # noqa: E402
from src.summary_row import (  # noqa: E402
    DEFECT_CATEGORIES,
    PAGE_ROW_TYPE,
    ROW_TYPE_FIELD,
    SUMMARY_ONLY_FIELDS,
    SUMMARY_ROW_TYPE,
    build_dataset_rows,
    build_summary_row,
)

FAILURES: list[str] = []
PASSED = 0

SAMPLE_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <title>How to audit a website for broken links</title>
    <meta name="description" content="A short description of the page.">
    <link rel="canonical" href="https://example.com/page">
  </head>
  <body>
    <h1>Audit a website</h1>
    <h2>Why</h2>
    <img src="/a.png">
    <form><input type="text" name="orphan"></form>
  </body>
</html>
"""

EXPECTED_EVENTS = {
    "page-audited": 0.05,
    "site-report": 0.25,
}


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED
    if condition:
        PASSED += 1
        print("ok   " + name)
    else:
        FAILURES.append(name)
        print("FAIL " + name + ((" :: " + detail) if detail else ""))


# --------------------------------------------------------------- 1. valid JSON
loaded: dict[str, dict] = {}
for filename in (
    "actor.json",
    "dataset_schema.json",
    "output_schema.json",
    "input_schema.json",
):
    path = ACTOR_DIR / filename
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        check("valid_json_" + filename, isinstance(parsed, dict), type(parsed).__name__)
        loaded[filename] = parsed if isinstance(parsed, dict) else {}
    except Exception as exc:  # noqa: BLE001 - the message is the report
        loaded[filename] = {}
        check("valid_json_" + filename, False, repr(exc))

actor = loaded["actor.json"]
dataset = loaded["dataset_schema.json"]
output = loaded["output_schema.json"]
inp = loaded["input_schema.json"]

check("actor_name", actor.get("name") == "page-audit-tool", repr(actor.get("name")))
check("actor_version", bool(actor.get("version")), repr(actor.get("version")))
check(
    "actor_specification_1",
    actor.get("actorSpecification") == 1,
    repr(actor.get("actorSpecification")),
)

# ------------------------------------------------- 2. the schemas are referenced
storages = actor.get("storages") or {}
check(
    "storages_dataset_reference",
    storages.get("dataset") == "./dataset_schema.json",
    repr(storages.get("dataset")),
)
check(
    "output_schema_reference",
    actor.get("output") == "./output_schema.json",
    repr(actor.get("output")),
)
check("input_schema_reference", actor.get("input") == "./input_schema.json", repr(actor.get("input")))
for reference in (storages.get("dataset"), actor.get("output"), actor.get("input")):
    if isinstance(reference, str):
        target = (ACTOR_DIR / reference).resolve()
        check("referenced_file_exists_" + reference, target.is_file(), str(target))

check(
    "output_schema_version_1",
    output.get("actorOutputSchemaVersion") == 1,
    repr(output.get("actorOutputSchemaVersion")),
)
check(
    "output_schema_has_properties",
    isinstance(output.get("properties"), dict) and bool(output["properties"]),
    repr(list(output.get("properties", {}))),
)
for prop_name, prop in (output.get("properties") or {}).items():
    check(
        "output_property_has_template_" + prop_name,
        bool(isinstance(prop, dict) and prop.get("template")),
        repr(prop),
    )

# ------------------------------------------------------ 3. the charged events
events = (actor.get("pay_per_event") or {}).get("actorChargeEvents") or {}
check(
    "charge_events_are_exactly_two",
    set(events) == set(EXPECTED_EVENTS),
    repr(sorted(events)),
)
for event_name, price in EXPECTED_EVENTS.items():
    spec = events.get(event_name) or {}
    check(
        "charge_event_price_%s_is_%s" % (event_name, price),
        spec.get("eventPriceUsd") == price,
        repr(spec.get("eventPriceUsd")),
    )
    check(
        "charge_event_has_title_" + event_name,
        bool(spec.get("eventTitle")) and bool(spec.get("eventDescription")),
        repr(spec),
    )

# The names in the code must be the names the Store prices.
main_source = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
check(
    "main_py_uses_page_audited_event",
    'PAGE_EVENT = "page-audited"' in main_source,
    "constant not found in src/main.py",
)
check(
    "main_py_uses_site_report_event",
    'REPORT_EVENT = "site-report"' in main_source,
    "constant not found in src/main.py",
)
check(
    "main_py_pushes_check_page_rows",
    "row = check_page(url, status, html)" in main_source
    and "await Actor.push_data(dataset_rows)" in main_source,
    "src/main.py no longer pushes check_page rows; this test's model is stale",
)

# ------------------- 5. the summary row is written always, and charges nothing
check(
    "main_py_always_writes_the_summary_row",
    "dataset_rows = build_dataset_rows(rows, summary)" in main_source
    and "await Actor.push_data(dataset_rows)" in main_source,
    "src/main.py does not build the dataset rows through build_dataset_rows",
)
check(
    "summary_row_is_pushed_outside_any_row_gate",
    "if rows:\n            await Actor.push_data" not in main_source
    and "        dataset_rows = build_dataset_rows(rows, summary)" in main_source
    and "        await Actor.push_data(dataset_rows)" in main_source,
    "the push is still gated on there being page rows",
)
after_push = main_source.split("await Actor.push_data(dataset_rows)")[1].split(
    "set_value"
)[0]
check(
    "summary_row_never_charges",
    "charge" not in after_push,
    "something between the push and the SUMMARY record mentions charging: "
    + repr(after_push),
)
summary_source = (ROOT / "src" / "summary_row.py").read_text(encoding="utf-8")
check(
    "summary_row_module_never_imports_apify",
    "import apify" not in summary_source and "from apify" not in summary_source,
    "src/summary_row.py must stay free of the Apify SDK, so it cannot charge",
)

# ------------------------- 4. every view field exists in the row main.py pushes
row_normal = check_page("https://example.com/page", 200, SAMPLE_HTML)
row_no_body = check_page("https://example.com/down", None, None)

# The rows main.py really pushes: page rows carry rowType, and the run always
# ends with the summary row.
CLEAN_REPORT = {
    "startUrl": "https://example.com",
    "pagesCrawled": 12,
    "pagesAudited": 12,
    "pagesSkippedByRobots": 0,
    "pagesWithIssues": 0,
    "totalIssues": 0,
    "durationSeconds": 3.2,
    "chargedEvents": 13,
    "chargeLimitReached": False,
    "chargeFailures": 0,
}
pushed = build_dataset_rows([row_normal, row_no_body], CLEAN_REPORT)
summary_row = pushed[-1]
page_rows = pushed[:-1]

check(
    "every_pushed_row_declares_its_type",
    all(row.get(ROW_TYPE_FIELD) in {PAGE_ROW_TYPE, SUMMARY_ROW_TYPE} for row in pushed),
    repr([row.get(ROW_TYPE_FIELD) for row in pushed]),
)
check(
    "summary_row_is_the_last_row",
    summary_row.get(ROW_TYPE_FIELD) == SUMMARY_ROW_TYPE
    and all(row.get(ROW_TYPE_FIELD) == PAGE_ROW_TYPE for row in page_rows),
    repr([row.get(ROW_TYPE_FIELD) for row in pushed]),
)

row_fields = (set(row_normal) & set(row_no_body)) | {ROW_TYPE_FIELD} | set(summary_row)
check("dataset_row_has_fields", bool(row_fields), repr(sorted(row_fields)))

all_row_fields = {ROW_TYPE_FIELD} | set(row_normal) | set(summary_row)
declared = set((dataset.get("fields") or {}).get("properties") or {})
check(
    "dataset_schema_fields_match_the_rows",
    declared == all_row_fields,
    "declared only: %s / row only: %s"
    % (sorted(declared - all_row_fields), sorted(all_row_fields - declared)),
)
check(
    "summary_row_has_exactly_the_declared_summary_fields",
    set(summary_row)
    == {ROW_TYPE_FIELD} | set(SUMMARY_ONLY_FIELDS) | {k for k, _ in DEFECT_CATEGORIES},
    "row only: %s"
    % sorted(
        set(summary_row)
        - ({ROW_TYPE_FIELD} | set(SUMMARY_ONLY_FIELDS) | {k for k, _ in DEFECT_CATEGORIES})
    ),
)

views = dataset.get("views") or {}
check("dataset_schema_has_views", bool(views), repr(sorted(views)))
for view_name, view in views.items():
    check("view_has_title_" + view_name, bool(view.get("title")), repr(view))
    fields = ((view.get("transformation") or {}).get("fields")) or []
    check("view_lists_fields_" + view_name, bool(fields), repr(view))
    missing = [field for field in fields if field not in row_fields]
    check(
        "view_fields_exist_in_output_" + view_name,
        not missing,
        "not written by src/main.py: " + repr(missing),
    )
    display_props = set(((view.get("display") or {}).get("properties") or {}))
    check(
        "view_display_matches_fields_" + view_name,
        display_props <= set(fields),
        "displayed but not selected: " + repr(sorted(display_props - set(fields))),
    )

# ----------------------------------------- extra: input form matches the code
expected_input = {
    "startUrl": ("string", None),
    "maxPages": ("integer", 25),
    "maxDepth": ("integer", 3),
    "requestDelaySeconds": ("integer", 1),
    "requestTimeoutSeconds": ("integer", 15),
}
props = inp.get("properties") or {}
check("input_schema_version_1", inp.get("schemaVersion") == 1, repr(inp.get("schemaVersion")))
check("input_requires_start_url", inp.get("required") == ["startUrl"], repr(inp.get("required")))
check("input_fields_are_the_five", set(props) == set(expected_input), repr(sorted(props)))
for field, (ftype, default) in expected_input.items():
    spec = props.get(field) or {}
    check("input_type_" + field, spec.get("type") == ftype, repr(spec.get("type")))
    check("input_has_description_" + field, bool(spec.get("description")), repr(spec))
    if default is not None:
        check(
            "input_default_%s_is_%s" % (field, default),
            spec.get("default") == default,
            repr(spec.get("default")),
        )
        check(
            "main_default_%s_is_%s" % (field, default),
            '"%s": %s' % (field, default) in main_source
            or '"%s": %s.0' % (field, default) in main_source,
            "src/main.py DEFAULTS disagree with the input form",
        )

TOTAL = PASSED + len(FAILURES)
if FAILURES:
    print("\nfailed: " + ", ".join(FAILURES))
print("%d/%d passed" % (PASSED, TOTAL))
sys.exit(1 if FAILURES else 0)
