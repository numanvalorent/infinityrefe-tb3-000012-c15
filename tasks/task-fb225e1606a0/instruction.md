# Stable mechanical oscillator propagation

An instrumentation team needs one reusable solver for ring-down experiments.
The current placeholder returns no measurements. Implement `/app/propagate.py`
and run `/app/run.sh` to create `/app/output.json` from `/app/data/input.json`.
Use Python's standard library; all required runtimes are installed already.

For each case solve, independently at every requested time `t`,

`m*x''(t) + c*x'(t) + k*x(t) = 0`, with `x(0)=x0`, `x'(0)=v0`.

The input is `{"cases":[{"id":string,"m":number,"c":number,"k":number,
"x0":number,"v0":number,"times":[number,...]},...]}`.
Inputs are valid finite JSON: `0.25 <= m <= 4`, `0.1 <= sqrt(k/m) <= 5`,
`0 <= c/(2*m) <= 1000`, `abs(x0),abs(v0) <= 3` and `0 <= t <= 50`.
There are exactly 16 cases, each with six times, including zero and small times.
Cases cover zero damping, underdamping, exact/near critical damping and stiff
overdamping. A formula that divides by zero at critical damping or overflows
while computing an ultimately finite state does not meet the contract.

Write exactly `{"results":[{"id":string,"states":[{"x":number,"v":number,
"energy":number},...]},...]}`. Preserve case and time order and IDs. `v=x'` and
`energy=(m*v*v+k*x*x)/2`. Every number must be finite; no NaN, Infinity, strings
or booleans. Each value is compared with the independent solution using
`max(2e-8, 2e-8*abs(expected))` absolute error. Output energy must also be
nonnegative and agree with the reported position and velocity to this tolerance.

`/app/run.sh` must keep working on a replacement input file with the same schema
and documented ranges. The grader checks the shipped output and re-runs the
program on fresh systems. Do not change the input file. Retain the three
declared artifacts: `/app/run.sh`, `/app/propagate.py`, `/app/output.json`.

You have 900 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
