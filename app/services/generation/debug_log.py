"""Demo-friendly generation lifecycle logging (print + pprint)."""

from pprint import pprint
from typing import Any


def gen_log(stage: str, **data: Any) -> None:
    """Print a labeled generation step; extra kwargs are pretty-printed."""
    print("\n" + "=" * 72)
    print(f"[GENERATION] {stage}")
    print("=" * 72)
    if data:
        pprint(data, width=100, sort_dicts=False)
