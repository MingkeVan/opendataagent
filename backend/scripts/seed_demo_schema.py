from __future__ import annotations

import argparse
import json

from app.services.demo_data_service import seed_demo_schema


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()
    payload = seed_demo_schema(reset=not args.no_reset)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
