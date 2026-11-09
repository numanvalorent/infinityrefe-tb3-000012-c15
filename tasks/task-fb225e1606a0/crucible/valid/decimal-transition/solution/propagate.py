"""Correct alternate: high-precision first-order transition, distinct from closed-form Oracle."""
from decimal import Decimal, localcontext
import json,sys
from pathlib import Path

def multiply(left, right):
    return [sum(left[2*r+j] * right[2*j+c] for j in range(2)) for r in range(2) for c in range(2)]


def propagate(case: dict, time: float) -> dict:
    with localcontext() as context:
        context.prec = 70
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
            if max(abs(value) for value in term) < Decimal("1e-60"):
                break
        else:
            raise ArithmeticError("matrix exponential did not converge")
        for _ in range(squarings):
            total = multiply(total, total)
        x, v = total[0]*x0 + total[1]*v0, total[2]*x0 + total[3]*v0
        return {"x": float(x), "v": float(v), "energy": float((m*v*v+k*x*x)/2)}


data=json.loads(Path(sys.argv[1]).read_text())
result={"results":[{"id":case["id"],"states":[propagate(case,t) for t in case["times"]]} for case in data["cases"]]}
Path(sys.argv[2]).write_text(json.dumps(result,allow_nan=False)+"\n")
