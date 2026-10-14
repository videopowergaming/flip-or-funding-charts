#!/usr/bin/env python3
"""Flip-Or Funding Charts — chart/data build script (scaffold).

Reads project data from data/ and writes chart output to charts/.
Fill in the data source and chart logic as the project takes shape.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text())


def main() -> None:
    print(f"{CONFIG[\x27project\x27]} v{CONFIG[\x27version\x27]} — scaffold ready.")
    print("TODO: load data from data/, build charts into charts/.")


if __name__ == "__main__":
    main()
