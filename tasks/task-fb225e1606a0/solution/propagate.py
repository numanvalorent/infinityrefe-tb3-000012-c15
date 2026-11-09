"""Closed-form Oracle; the verifier instead exponentiates a matrix in Decimal."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def state(case: dict, t: float) -> dict:
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
    elif discriminant < 0:
        b = math.sqrt(-discriminant)
        z = b * t
        decay = math.exp(-a * t)
        p = decay * math.cos(z)
        q = decay * t * (1 - z*z/6 + z**4/120 - z**6/5040 if abs(z) < 1e-3 else math.sin(z) / z)
    else:
        p = math.exp(-a * t)
        q = t * p
    x = x0 * p + (v0 + a * x0) * q
    v = v0 * p - (a * v0 + w2 * x0) * q
    return {"x": x, "v": v, "energy": (m * v * v + k * x * x) / 2}


def solve(data: dict) -> dict:
    return {"results": [{"id": case["id"], "states": [state(case, t) for t in case["times"]]} for case in data["cases"]]}


if __name__ == "__main__":
    Path(sys.argv[2]).write_text(json.dumps(solve(json.loads(Path(sys.argv[1]).read_text())), allow_nan=False) + "\n", encoding="utf-8")
