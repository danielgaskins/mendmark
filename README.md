# Faultline

Faultline is an evaluation and post-training lab for agents repairing broken
machine-learning systems. It asks a deliberately harder question than "did the
patch make the visible tests pass?": did the agent preserve the validity of the
experiment and the behavior of the resulting ML system?

The first vertical slice includes:

- A versioned, dependency-free task format.
- Public workspaces that never contain hidden graders.
- Isolated grading through Bubblewrap with networking disabled and the host
  system mounted read-only.
- Immutable task and workspace digests.
- Run manifests that record human and AI collaboration.
- A realistic entity-leakage task with public and hidden tests.

## Quick start

Faultline currently requires Linux, Python 3.10+, and `bwrap` (Bubblewrap).
The host must permit unprivileged user namespaces. If it does not, the grader
records an `infrastructure_error` rather than counting the task as a model
failure.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .

faultline tasks
faultline prepare group-leakage-001 \
  --operator "Daniel Gaskins" \
  --assistant "OpenAI Codex"
```

The prepare command prints a run directory. Work only in its `workspace/`
directory. Then grade the result:

```bash
faultline grade runs/<run-id>
faultline show runs/<run-id>
```

For framework development only, `faultline grade ... --runtime local` bypasses
isolation. Results produced that way are marked `isolated: false` and must not be
used as benchmark evidence.

## Project layout

```text
src/faultline/                 Runner, schema, grading, and CLI
tasks/<task-id>/task.json      Public task metadata
tasks/<task-id>/repo/          Files copied into an agent workspace
tasks/<task-id>/hidden_tests/  Private deterministic grader inputs
tasks/<task-id>/reference/     Author-only reference material
tests/                         Framework and end-to-end tests
runs/                          Local run artifacts (ignored by git)
```

## AI collaboration policy

This repository is intentionally agent-native. Agents may help author code,
tasks, tests, analysis, and documentation. That assistance is recorded rather
than concealed.

The human owner remains responsible for:

1. Choosing the research question and accepting or rejecting design changes.
2. Auditing task validity, hidden graders, and headline findings.
3. Reproducing results from a clean environment.
4. Understanding and defending every material claim in the report.
5. Following each employer's rules during applications and assessments.

Agent use here is not permission to use an agent during an interview or take-home
where the employer prohibits it. The benchmark is portfolio evidence; it is not
a substitute for unaided technical ability.

## Security model

The default grader copies the submitted workspace into a temporary directory and
runs it under Bubblewrap. The sandbox has no network namespace, a read-only host
runtime, a fresh `/tmp`, and write access only to the temporary workspace. Hidden
tests are added only to that temporary grading copy.

This is defense in depth for benchmark tasks, not a hardened hostile-code service.
Do not run untrusted public submissions on a personal machine. A later hosted
runner should use disposable VMs or similarly strong isolation.

## Roadmap

- Validate the task and grader format with five distinct failure classes.
- Add an agent adapter and complete trajectory capture.
- Add repeated trials, cost/latency accounting, and bootstrap intervals.
- Calibrate model-based grading against blinded human review.
- Publish a protected holdout and post-training study.
