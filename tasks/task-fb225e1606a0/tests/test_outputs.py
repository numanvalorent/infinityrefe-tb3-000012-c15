"""Artifact-only checks; the witness runtime performs fresh program replay."""
import json
import math
import ast
import hashlib
import sys
from pathlib import Path
from witness.reference import expected as mechanical_expected


def test_output_schema_and_physical_energy():
    """Output energy must be nonnegative and agree with the reported position and velocity to this tolerance.

    Enforce ordered finite states and the documented mechanical energy identity.
    """
    output = Path("/app/output.json")
    assert output.is_file() and not output.is_symlink()
    assert output.stat().st_size <= 100_000
    data = json.loads(output.read_text())
    pristine = json.loads(Path("/tests/witness/fixtures/data/input.json").read_text())
    assert set(data) == {"results"} and len(data["results"]) == 16
    for result, case in zip(data["results"], pristine["cases"], strict=True):
        assert set(result) == {"id", "states"} and result["id"] == case["id"]
        assert len(result["states"]) == len(case["times"])
        for state in result["states"]:
            assert set(state) == {"x", "v", "energy"}
            assert all(type(value) in (int, float) and math.isfinite(value) for value in state.values())
            assert state["energy"] >= 0
            computed = (case["m"]*state["v"]**2 + case["k"]*state["x"]**2)/2
            assert abs(state["energy"]-computed) <= max(2e-8, 2e-8*abs(computed))


def test_standard_library_and_declared_artifacts():
    """Use Python's standard library and retain /app/run.sh, /app/propagate.py, /app/output.json.

    Do not change the input file. Its bytes must equal the trusted fixture.
    """
    for name in ("run.sh", "propagate.py", "output.json"):
        path = Path("/app") / name
        assert path.is_file() and not path.is_symlink()
    assert hashlib.sha256(Path("/app/data/input.json").read_bytes()).digest() == hashlib.sha256(Path("/tests/witness/fixtures/data/input.json").read_bytes()).digest()
    tree = ast.parse(Path("/app/propagate.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] in sys.stdlib_module_names for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and (node.module or "").split(".")[0] in sys.stdlib_module_names


def test_independent_equations_initial_conditions_and_finite_numbers():
    """Verify m*x''(t)+c*x'(t)+k*x(t)=0 with x(0)=x0 and x'(0)=v0.

    Exactly 16 cases, each with six times including zero and small times, use
    finite numbers, without NaN, Infinity, strings or booleans. The independent
    matrix exponential checks exact/near critical damping and stiff overdamping.
    The witness separately re-runs run.sh on a replacement input file with the
    same schema and documented ranges. The fixed input file is never changed.
    """
    expected = mechanical_expected(Path("/tests/witness/fixtures"))
    actual = json.loads(Path("/app/output.json").read_text())
    assert len(expected["results"]) == len(actual["results"]) == 16
    for left, right in zip(expected["results"], actual["results"], strict=True):
        assert left["id"] == right["id"]
        assert len(left["states"]) == len(right["states"]) == 6
        for wanted, got in zip(left["states"], right["states"], strict=True):
            for key in ("x", "v", "energy"):
                assert type(got[key]) in (int, float) and math.isfinite(got[key])
                assert abs(got[key] - wanted[key]) <= max(2e-8, 2e-8 * abs(wanted[key]))
