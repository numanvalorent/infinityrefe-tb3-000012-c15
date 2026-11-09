# Fellow authoring guide

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

## Published source snapshot

- [Contribution guide](https://github.com/harbor-framework/terminal-bench/blob/4def1f367467b34b18e0dbdc086400ba71c3e037/CONTRIBUTING.md)
- [Task guidelines](https://github.com/harbor-framework/terminal-bench/blob/4def1f367467b34b18e0dbdc086400ba71c3e037/docs/task-guidelines.md)
- [Proposal rubric](https://github.com/harbor-framework/terminal-bench/blob/4def1f367467b34b18e0dbdc086400ba71c3e037/docs/prompts/task-proposal.md)
- [Review automation](https://github.com/harbor-framework/terminal-bench/blob/4def1f367467b34b18e0dbdc086400ba71c3e037/docs/TASK_REVIEW_AUTOMATION.md)