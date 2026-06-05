"""Phase-0 capability spike / regression probe (SPEC.md §5 step 2, §6).

Calls each SPEC §3 endpoint for our real symbols and records what actually comes
back (shape, granularity, working provider). This is the "check what OpenBB
already provides" step. Re-run it after every OpenBB upgrade as a regression
check.

Usage:
    python -m obb_layer.probe
"""

from __future__ import annotations

from obb_layer.client import get_obb
from obb_layer.symbols import WATCHLIST


def main() -> None:
    obb = get_obb()
    print("OpenBB loaded. Watchlist:", ", ".join(WATCHLIST))
    # TODO (Phase 0): probe each §3 endpoint, print data shape + provider used.
    # Kept as a stub in the scaffold so the import graph is verifiable now.


if __name__ == "__main__":
    main()
