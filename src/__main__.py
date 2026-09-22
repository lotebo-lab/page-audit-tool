"""Module entry point so `python -m src` (used by `apify run`) works."""

from __future__ import annotations

import asyncio

from .main import main

asyncio.run(main())
