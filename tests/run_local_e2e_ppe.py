"""Same end-to-end run as `run_local_e2e.py`, but with pay-per-event turned on.

The cloud run wzcOeT667zwOgw7dr audited 3 pages, logged 9 issues and wrote zero
dataset rows. The plain local run writes its rows, so the difference had to be
the pricing model: on the platform the Actor runs pay-per-event, locally it does
not. This script sets the two environment variables the SDK reads for local
pay-per-event development so the offline run takes the same code path as the
cloud run.

Usage:
    python tests/run_local_e2e_ppe.py <site-dir> <run-dir> [port]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PRICING_INFO = {
    "pricingModel": "PAY_PER_EVENT",
    "pricingPerEvent": {
        "actorChargeEvents": {
            "page-audited": {"eventTitle": "Page audited", "eventPriceUsd": 0.05},
            "site-report": {"eventTitle": "Site report", "eventPriceUsd": 0.25},
        }
    },
}

os.environ["ACTOR_TEST_PAY_PER_EVENT"] = "1"
os.environ["APIFY_ACTOR_PRICING_INFO"] = json.dumps(PRICING_INFO)
os.environ.setdefault("ACTOR_MAX_TOTAL_CHARGE_USD", "5")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_local_e2e import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
