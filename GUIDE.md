<!-- tbench-managed-authoring-guide -->
# INFINITYREFE-TB3-000012 · terminal-bench-3 authoring guide

Task: `tasks/task-fb225e1606a0/` · Assigned policy: `tbench-tb3-2026-11-07`.

## Claim → proposal → implementation → GitHub review

1. Claim a category in your Experts workspace and submit your own task proposal.
2. After proposal approval, accept the linked GitHub invite and fork this repository.
3. Clone your fork and create `submission`. Keep implementation changes inside the assigned task directory.
4. Complete the instruction, environment, Oracle solution and independent verifier.
5. Run the local checks below, push, and open a PR against this repository's `main`.
6. Each PR push runs the GitHub precheck and reserved Infinity workflow. Read the bot stage cards and fix the reported requirement.

## Local prerequisites and rehearsal

Install Git, Python 3.12 and Docker with a working Linux engine. Review the [developer setup script](https://actions.tbench.in/dev-install.sh) ([Windows PowerShell](https://actions.tbench.in/dev-install.ps1)) before running it. It installs `tbench-dev` and pinned local Harbor 0.18.0; it does not enroll an Actions product worker. The isolated central Infinity candidate/witness jobs use Harbor 0.24.0.

```sh
docker version
tbench-dev doctor
tbench-dev check tasks/task-fb225e1606a0
tbench-dev calibrate tasks/task-fb225e1606a0 --trust-local-task
git add tasks/task-fb225e1606a0
git commit -m 'Implement INFINITYREFE-TB3-000012'
git push -u origin submission
```

Read task code before trusting a local rehearsal. Oracle must earn 1 and Nop must earn 0. Never put provider keys, platform callback tokens, private data or a Docker socket into the task environment.

## Required task files

```text
tasks/task-fb225e1606a0/
  instruction.md
  task.toml
  README.md
  environment/Dockerfile
  solution/solve.sh
  tests/Dockerfile
  tests/test.sh
  tests/test_outputs.py
```

Declare transferred paths in top-level `artifacts` in `task.toml`, and set `[verifier] environment_mode = "separate"`. The verifier sees only declared artifacts and files baked into its own image. Test correct alternatives, a wrong result, missing output, malformed output and grader execution failures. A crashed grader is an execution error.

## Task README and proposal

Fill factual author/category/resource metadata. Personally write the difficulty explanation, solution explanation, verification explanation and relevant experience sections. Explain the substantive expert challenge, not artificial time pressure. Preserve a changelog and the exact source revision associated with each result. Automated feedback requests fixes; it does not supply the author's personal account.

## Pass@2, Pass@5 and the ten-attempt limit

The versioned free v2 profile reserves ten terminal attempts: the first two candidate attempts are also the measured PRECHECK Pass@2 panel; PROBE uses one, adversarial cheat-pass uses two, and GAUNTLET Pass@5 uses five. Sharing the candidate receipt does not create two new attempts. Pass@2 permits at most one solve; Pass@5 permits at most two solves. An invalid/provider-error attempt is unscored and leaves the panel incomplete. The profile, model, agent, resource limits, revision and every reward are recorded. Earlier v1 runs keep their actual Pass@3 results. Your workspace displays the selected profile; free-model evidence does not become frontier-model certification.

## Reading a blocked run

| Result | Next action |
|---|---|
| FAIL | Fix the demonstrated contract violation; rerun the changed revision. |
| REVIEW | Inspect the named requirement or surviving mutation; justify an equivalent candidate or repair an invalid one. |
| ERROR | Resolve the tool, provider or execution failure. It is not a successful defense or a model stump. |
| BLOCKED / not measured | Inspect the preceding job and required runtime; no result was recorded. |

Do not reopen PRs to bypass the allowance. Skip releases work to the operator bucket; an operator may recover and republish it with an explicitly renewed cycle. Earlier evidence remains visible.

## Choose your specialism

Claim an available category and subcategory. You propose the actual task from your domain experience. One active claim at a time; client audit purchases are a separate flow.

## Propose before building

Describe a realistic problem, its difficulty and expert time, the intended approach, objective verification, and why it fits the selected category. Save a draft, then submit for review. Preliminary checks are not a guarantee of model or human approval.

## Accept access and fork

Your permanent task ID follows the claim, repository, PR, and results. Accept the GitHub invitation shown in your workspace, fork the assigned repository, and use a submission branch. Build only after proposal approval. Never share tokens or change the shared workflow.

## Set up your own computer

Install Git, Python 3.12 and Docker with its Linux engine. Download and review https://actions.tbench.in/dev-install.sh (Linux/WSL) or dev-install.ps1 (Windows), then run it as your own user. This installs pinned Harbor 0.18.0 and tbench-dev, not an enrolled background Actions worker. Run tbench-dev doctor, then tbench-dev check tasks/<slug>. Add ~/.local/bin to PATH or use the full launcher path. No Tbench platform key belongs on your device.

## Author the task

Keep the task under the assigned tasks/<slug>/ directory. Write instruction.md, task.toml, environment/Dockerfile, an Oracle solution, and independent tests with their own Dockerfile. Use separate verifier mode and declare transferred artifacts at the top of task.toml. The starter intentionally fails until implemented.

## Validate and open a PR

Review your task code, then run tbench-dev calibrate tasks/<slug> --trust-local-task. Oracle must complete with reward 1 and Nop with reward 0. Local results are rehearsals, not certificates. This CPU-only profile caps agent and verifier timeouts at 3600 seconds each; it is not the universal upstream limit. Push your fork's submission branch and open a PR to upstream main. Only task files may change. Independent PR checks still run even if you skipped the local tool; a first-time fork workflow may need an operator's GitHub approval.

## Trials and review

Each eligible commit can reserve one two-attempt model panel, at most 10 model attempts per production cycle. Static checks and Oracle/Nop do not consume this model allowance. Central candidate and witness jobs use Harbor 0.24.0; the local development and fork precheck profile uses Harbor 0.18.0. Your task shows the exact submitted commit, measured Infinity stages, and blocking results. New witness-contract runs require an isolated replay of the completed candidate. Infrastructure errors do not demonstrate difficulty. Passing a panel does not replace novelty, verifier soundness, rubric or independent human review.

## If you cannot continue

Skip with a reason to release your claim into the operator bucket. Exhausted and skipped work keeps its history. Only an operator may republish it or explicitly authorize a new trial budget. Do not open another PR to bypass the limit.

## Pinned upstream sources

- [Contribution guide](https://github.com/harbor-framework/terminal-bench/blob/4def1f367467b34b18e0dbdc086400ba71c3e037/CONTRIBUTING.md)
- [Task guidelines](https://github.com/harbor-framework/terminal-bench/blob/4def1f367467b34b18e0dbdc086400ba71c3e037/docs/task-guidelines.md)
- [Proposal rubric](https://github.com/harbor-framework/terminal-bench/blob/4def1f367467b34b18e0dbdc086400ba71c3e037/docs/prompts/task-proposal.md)
- [Review automation](https://github.com/harbor-framework/terminal-bench/blob/4def1f367467b34b18e0dbdc086400ba71c3e037/docs/TASK_REVIEW_AUTOMATION.md)

## Current TB4 authoring guidance

This task retains its recorded TB3 assignment. For new TB4 work, read the [current Tbench authoring and review guide](https://experts.tbench.in/guide), [TB4 methodology](https://experts.tbench.in/methodology), and [upstream resource/versioning guidance](https://www.tbench.ai/news/terminal-bench-4-0). TB4's released agent budget is eight hours; this existing CPU rehearsal retains its recorded limits. Updating guidance does not relabel previous trials.
