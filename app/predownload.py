"""
Build-time helper: pre-download model weights so they are baked into the
Docker image instead of fetched on first request.

Reads the space-separated model keys from the PREDOWNLOAD_MODELS env var
(set via the Dockerfile build arg). On a small instance we bake in only the
recommended ESM-1b by default; ProtT5 and ESM++ are large and download
lazily on first use. Unknown keys are skipped with a warning so a typo never
fails the build.
"""

import os
import sys

from .backends import predownload
from .models import get_spec


def main() -> int:
    keys = os.environ.get("PREDOWNLOAD_MODELS", "").split()
    if not keys:
        print("PREDOWNLOAD_MODELS is empty; skipping pre-download.")
        return 0
    for key in keys:
        try:
            spec = get_spec(key)
        except ValueError as e:
            print(f"  ! {e}")
            continue
        print(f"Pre-downloading {spec.name} ({spec.params})...")
        try:
            predownload(spec)
            print(f"  done: {spec.name}")
        except Exception as e:  # never fail the build on a download hiccup
            print(f"  ! could not pre-download {spec.name}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
