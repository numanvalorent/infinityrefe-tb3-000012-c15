"""Closed-form Oracle; the verifier instead exponentiates a matrix in Decimal."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def state(case: dict, t: float) -> dict:
    """Solve m*x'' + c*x' + k*x = 0 with x(0)=x0 and x'(0)=v0, using Python's standard library.

    Critical damping avoids division by zero. Stiff overdamping uses stable
    roots so an ultimately finite state never overflows.
    Output energy is nonnegative and agrees with the reported position and
    velocity; it is computed directly rather than independently approximated.
    """
    m, k, c = case["m"], case["k"], case["c"]
    x0, v0 = case["x0"], case["v0"]
    a, w2 = c / (2 * m), k / m
    discriminant = a * a - w2
    if discriminant > 0:
        b = math.sqrt(discriminant)
        slow = math.exp((-w2 / (a + b)) * t)
        fast = math.exp(-(a + b) * t)
        p = (slow + fast) / 2
        q = slow * (-math.expm1(-2 * b * t)) / (2 * b)
    else:
        b = math.sqrt(-discriminant)
        z = b * t
        decay = math.exp(-a * t)
        p = decay * math.cos(z)
        # sin(z)/z is stable near zero; its continuous value at zero is one.
        q = decay * t * (math.sin(z) / z if z else 1)
    x = x0 * p + (v0 + a * x0) * q
    v = v0 * p - (a * v0 + w2 * x0) * q
    result = {"x": x, "v": v, "energy": (m * v * v + k * x * x) / 2}
    assert all(math.isfinite(value) for value in result.values()), "Every number must be finite"
    assert result["energy"] >= 0
    return result


def solve(data: dict) -> dict:
    """Preserve case/time order and IDs for exactly 16 cases, each with six times.

    Read a replacement input file using the same schema and documented ranges;
    retain run.sh, propagate.py and output.json, without changing the input file.
    The same program produces the shipped output and re-runs on fresh systems.
    """
    assert len(data["cases"]) == 16
    assert all(len(case["times"]) == 6 for case in data["cases"])
    return {"results": [{"id": case["id"], "states": [state(case, t) for t in case["times"]]} for case in data["cases"]]}


def expected(app_root: Path) -> dict:
    """Author-side measurement adapter; no independent verifier code is imported."""
    return solve(json.loads((app_root / "data/input.json").read_text()))


if __name__ == "__main__":
    Path(sys.argv[2]).write_text(json.dumps(solve(json.loads(Path(sys.argv[1]).read_text())), allow_nan=False) + "\n", encoding="utf-8")
