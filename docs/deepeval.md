# Using Mendmark with DeepEval

DeepEval evaluates an agent's response, trace, plan, and tool use. Mendmark
checks the machine-learning repository left behind by a code-changing agent.
The two results answer different questions:

| Question | Evaluator |
| --- | --- |
| Did the agent complete the requested task? | DeepEval task-completion metric |
| Did it select and call tools correctly? | DeepEval tool metrics |
| Does the edited repository preserve the experiment contract? | Mendmark integrity metric |

## Install

```bash
pip install 'mendmark-evals[deepeval]'
```

For a repository checkout:

```bash
pip install -e '.[deepeval]'
```

## Prepare and run the coding agent

```bash
RUN_DIR=$(mendmark prepare group-leakage-001 --operator ci)

# Point your coding agent at "$RUN_DIR/workspace".
```

Mendmark does not require a particular agent framework. The agent only needs
permission to edit the prepared workspace.

## Add the integrity result to DeepEval

```python
from deepeval import assert_test
from deepeval.metrics import TaskCompletionMetric
from deepeval.test_case import LLMTestCase
from mendmark.deepeval import MendmarkIntegrityMetric


def test_ml_repair() -> None:
    test_case = LLMTestCase(
        input="Repair the group leakage in this evaluation split.",
        actual_output="The coding agent completed its repair.",
        metadata={
            "mendmark_run_dir": "runs/<run-id>",
        },
    )

    assert_test(
        test_case,
        metrics=[
            TaskCompletionMetric(),
            MendmarkIntegrityMetric(tasks_root="tasks"),
        ],
        run_async=False,
    )
```

`MendmarkIntegrityMetric` loads the task from the run manifest and executes the
hidden grader. It returns:

- `1.0` when the integrity contract passes.
- `0.0` when the contract fails.
- An error when the grader cannot create its requested sandbox.

The metric defaults to Bubblewrap isolation. Use `runtime="local"` only for
tests against code you trust:

```python
MendmarkIntegrityMetric(tasks_root="tasks", runtime="local")
```

## Why the score is binary

The current tasks encode critical invariants. A train/test split either leaks an
entity or it does not. Inference either reuses training statistics or it refits
them. Averaging these failures into a soft score can hide a broken experiment.

Future task families may expose several separately named invariants. Critical
invariants should still act as release gates even when a report includes a
broader aggregate score.
