# Original Experts QA task: damped oscillator

This is an original Tbench-owned physics/numerical-analysis task for exercising
the Experts submission and Infinity evidence flow. It contains no external task,
private customer data or third-party benchmark material. It is not an upstream
Terminal-Bench submission or a claim of frontier-model difficulty.

The `model_tested`/`agent_tested` metadata identifies the pair prescribed by
Infinity's existing canonical contract. It does not record a completed model
run. No GPT-5.4 run is authorized for this free-only QA exercise; canonical
paid-model stages must remain unmeasured or policy-blocked.

The Oracle uses stable closed-form oscillator propagation. The verifier uses an
independent 100-digit Decimal Taylor/scaling-and-squaring matrix exponential.
The shipped input and generated witnesses each contain all damping regimes.
Declared numeric tolerances are 2e-8 absolute/relative. The generated witness
runtime is copied from this repository's first-party Infinity source.

Local authoring/fork precheck uses Harbor 0.18.0; the central completed-candidate
and isolated witness profile uses Harbor 0.24.0. Oracle/NOP controls, model trials,
GitHub delivery, witness admission and final review are separate gates. Record
real results in the control receipt; never infer passes for unavailable stages.

The public Python environment bakes bash, tmux 3.3a and asciinema 2.4.0 before
agent execution. The verifier bakes pytest 9.1.1 and pytest-json-ctrf 0.5.2.
Vendored public packages/wheels are hash-pinned so both images build without
network access. Runtime packages retain their original copyright notices;
`environment/vendor/PROVENANCE.json` records their sources and verification.

Run `python examples/experts-qa/test_damped_oscillator.py` for independent host
math controls. Local Harbor 0.18.0 controls completed with Oracle reward 1.0
(artifact gate plus 3/3 fresh witnesses) and NOP reward 0.0, each with zero
exceptions. The sibling `damped-oscillator.controls.json` records the actual
results and hashes. The W2 numeric-tolerance provenance finding remains an
explicit review item; no synthetic derivation or approval has been added.
Model trials, central Harbor 0.24.0 qualification, isolated candidate witness
admission and final project review remain separate gates. Use only a public
Python base, never a proprietary application image as the task environment.

## Original QA submission

This submission exercises the assigned-fellow fork and pull-request flow. The task root is `tasks/damped-oscillator`; Oracle and NOP are controls, while the reserved free-model attempts and isolated Infinity witness run centrally after the platform admits this exact commit. The source pull request contains no credentials or customer data.
