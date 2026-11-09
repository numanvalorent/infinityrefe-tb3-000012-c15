"""Plausible near-miss: applies the undamped formula to every experiment."""
import json
import math
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
results = []
for case in data["cases"]:
    omega = math.sqrt(case["k"] / case["m"])
    states = []
    for t in case["times"]:
        x = case["x0"]*math.cos(omega*t) + case["v0"]*math.sin(omega*t)/omega
        v = -case["x0"]*omega*math.sin(omega*t) + case["v0"]*math.cos(omega*t)
        states.append({"x": x, "v": v, "energy": (case["m"]*v*v + case["k"]*x*x)/2})
    results.append({"id": case["id"], "states": states})
Path(sys.argv[2]).write_text(json.dumps({"results": results}) + "\n")
