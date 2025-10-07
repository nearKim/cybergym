#!/usr/bin/env python3

import shutil
import sys
from pathlib import Path

# TODO: Get these from settings
TARGET_DIRS = ["cybergym_tmp", "logs", "server_poc"]


def main() -> int:
    dirs = [Path(d) for d in TARGET_DIRS]

    if "--yes" not in sys.argv and "-y" not in sys.argv:
        print("About to remove the following directories:")
        for d in dirs:
            print(f"  - {d}")
        resp = input("Proceed? (y/N): ").strip().lower()
        if resp not in ("y", "yes"):
            print("Cancelled.")
            return 1

    for d in dirs:
        if d.exists():
            try:
                shutil.rmtree(d)
                print(f"Removed: {d}")
            except Exception as err:
                print(f"Failed to remove {d}: {err}")
        else:
            print(f"Not found: {d}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
