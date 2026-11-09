"""Artifact-only checks; the witness runtime performs fresh program replay."""
import json
import math
from pathlib import Path


def test_output_schema_and_physical_energy():
    """Enforce ordered finite states and the documented mechanical energy identity."""
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
