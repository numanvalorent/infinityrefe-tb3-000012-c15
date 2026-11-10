"""Independent high-precision matrix exponential; never imports the Oracle."""
from __future__ import annotations

import json
import random
from decimal import Decimal, localcontext
from pathlib import Path


def generate(seed: int, app_root: Path) -> None:
    rng = random.Random(seed)
    ratios = [0, .05, .5, .95, 1 - 1e-11, 1, 1 + 1e-11, 1.05, 2, 5, 10, 100, 1000, .1, 1, 3]
    cases = []
    for index, ratio in enumerate(ratios):
        mass = rng.uniform(.3, 3)
        # Keep exact critical examples exactly representable in binary too.
        omega = 1.0 if ratio == 1 else rng.uniform(.2, 3.5)
        if ratio == 1:
            mass = 1.0
        damping = min(999.0, omega * ratio)
        position, velocity = rng.uniform(-2.5, 2.5), rng.uniform(-2.5, 2.5)
        # The documented domain includes the zero-energy equilibrium.
        if index == 15:
            position = velocity = 0.0
        cases.append({"id": f"case-{index:02d}", "m": mass, "k": mass * omega**2,
                      "c": 2 * mass * damping, "x0": position,
                      "v0": velocity, "times": [0, 1e-7, .03, .8, 5, 50]})
    path = app_root / "data" / "input.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps({"cases": cases}, sort_keys=True, separators=(",", ":")) + "\n").encode())


def multiply(left, right):
    return [sum(left[2*r+j] * right[2*j+c] for j in range(2)) for r in range(2) for c in range(2)]


def propagate(case: dict, time: float) -> dict:
    with localcontext() as context:
        context.prec = 100
        m, c, k, x0, v0, t = [Decimal(str(value)) for value in (case["m"], case["c"], case["k"], case["x0"], case["v0"], time)]
        # The first-order state system is y' = [[0,1],[-k/m,-c/m]] y.
        matrix = [Decimal(0), t, -k*t/m, -c*t/m]
        squarings = 0
        while max(abs(value) for value in matrix) > Decimal("0.125"):
            matrix = [value / 2 for value in matrix]
            squarings += 1
        identity = [Decimal(1), Decimal(0), Decimal(0), Decimal(1)]
        total, term = identity[:], identity[:]
        for order in range(1, 160):
            term = [value / order for value in multiply(term, matrix)]
            total = [a+b for a, b in zip(total, term)]
            if max(abs(value) for value in term) < Decimal("1e-90"):
                break
        else:
            raise ArithmeticError("matrix exponential did not converge")
        for _ in range(squarings):
            total = multiply(total, total)
        x, v = total[0]*x0 + total[1]*v0, total[2]*x0 + total[3]*v0
        return {"x": float(x), "v": float(v), "energy": float((m*v*v+k*x*x)/2)}


def expected(app_root: Path) -> dict:
    data = json.loads((app_root / "data" / "input.json").read_text())
    return {"results": [{"id": case["id"], "states": [propagate(case, t) for t in case["times"]]} for case in data["cases"]]}
