# Mendmark

Mendmark checks whether a coding agent repaired a machine-learning system
without breaking the experiment that system was meant to run.

A patch can make every visible test pass while leaking labels, fitting
preprocessing on inference data, changing the scoring rule, or contaminating
global state. Mendmark gives each repair task a stated contract and a hidden,
deterministic grader. It runs the submitted workspace in isolation and records
the exact code that was graded.

## Why this exists

Output and trace evaluators answer important questions about an agent:

- Did it complete the task?
- Did it call the right tools?
- Was its final answer relevant and well supported?

Code-changing agents create another problem. The final answer can sound right
and the public tests can pass while the edited repository no longer measures
what its owner intended. Mendmark checks the repository itself after the agent
finishes.

Mendmark is designed to run beside [DeepEval](https://github.com/confident-ai/deepeval),
not replace it. DeepEval can score the agent's output, trace, plan, and tool use.
Mendmark adds a deterministic experiment-integrity result to that evaluation.

```text
agent request and trace  ->  DeepEval metrics
edited ML repository     ->  Mendmark hidden grader
                         ->  one CI report
```

## What it catches

| Task | Integrity failure |
| --- | --- |
| `group-leakage-001` | Repeated entities cross the train/test boundary |
| `metric-aggregation-001` | Frequently retried tasks dominate the headline score |
| `reproducible-initialization-001` | Seeded initialization mutates inputs and global RNG state |
| `temporal-label-leakage-001` | Training consumes labels unavailable at the historical cutoff |
| `train-serve-skew-001` | Inference silently refits preprocessing statistics |

Every checked-in baseline must fail its hidden grader. Every reference repair
must pass. The framework test suite verifies both conditions across the complete
task set.

## Quick start

Mendmark requires Linux and Python 3.10 or newer. Isolated grading also requires
Bubblewrap and a host that permits unprivileged user namespaces.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .

mendmark tasks
mendmark prepare group-leakage-001 --operator "local-run"
```

The prepare command prints a run directory. Give its `workspace/` directory to
the coding agent. Grade the edited workspace when the agent finishes:

```bash
mendmark grade runs/<run-id>
mendmark show runs/<run-id>
```

The default grader uses Bubblewrap with networking disabled. For framework
development on a trusted repository, `--runtime local` bypasses isolation. The
result is marked `isolated: false` and should not be used as benchmark evidence.

## DeepEval integration

Install the optional integration:

```bash
pip install -e '.[deepeval]'
```

Add the Mendmark run directory to a DeepEval test case and include the metric:

```python
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from mendmark.deepeval import MendmarkIntegrityMetric

test_case = LLMTestCase(
    input="Repair the group leakage in this evaluation split.",
    actual_output="The coding agent completed its repair.",
    metadata={"mendmark_run_dir": "runs/<run-id>"},
)

assert_test(
    test_case,
    [MendmarkIntegrityMetric(tasks_root="tasks")],
    run_async=False,
)
```

DeepEval records a score of `1.0` when the hidden integrity contract passes and
`0.0` when it fails. Sandbox failures raise an error rather than being counted
as agent failures. See [the integration guide](docs/deepeval.md) for a complete
example.

## Trust model

The public workspace never contains hidden tests. Grading copies the submitted
workspace into a temporary directory and adds the hidden tests only to that copy.
Run manifests record:

- Task and framework versions.
- Initial and final workspace digests.
- Grader command and runtime.
- Raw grader output.
- Duration, timeout, isolation, and infrastructure status.

The default Bubblewrap sandbox has no network namespace, a read-only host
runtime, a fresh `/tmp`, and write access only to the temporary workspace. This
is suitable for controlled benchmark tasks. It is not a hardened service for
arbitrary hostile submissions. A hosted runner should use disposable VMs or an
equivalent boundary.

## Project layout

```text
src/mendmark/                  Runner, task schema, CLI, and integrations
tasks/<task-id>/task.json      Public task metadata
tasks/<task-id>/repo/          Workspace copied for the agent
tasks/<task-id>/hidden_tests/  Deterministic integrity contract
tasks/<task-id>/reference/     Author-only reference repair
tests/                         Framework and end-to-end tests
runs/                          Local run artifacts, ignored by Git
```

## Present limits

Mendmark currently contains five small, hand-authored development tasks. The
checked-in hidden tests are visible to repository readers, so this release is a
framework demonstration rather than a protected model leaderboard. It does not
yet run agents, capture trajectories, repeat trials, or report cost and latency.

See [the evaluation card](docs/evaluation-card.md) for the validity controls,
known limitations, and publication gate.
