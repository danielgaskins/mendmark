# DeepEval integration

Mendmark uses DeepEval metrics as the test suite under test. The mutation engine
changes a passing `LLMTestCase`, then asks the same metrics to score it again.

## Agent-eval audit

Install the optional adapter:

```bash
pip install 'mendmark-evals[deepeval]'
```

Create a trusted Python suite with `TOOLS`, `get_cases()`, and `get_metrics()`.
Then run:

```bash
mendmark audit evals/mendmark_suite.py \
  --baseline .mendmark-baseline.json \
  --output mendmark-report.json
```

`get_metrics()` is a factory. It must return fresh metric objects because
DeepEval metrics store their latest score, reason, success state, and error.
Metric names must be unique within the suite.

The adapter currently supports the standard `LLMTestCase` fields used for agent
tool evaluation:

- `input`
- `actual_output`
- `expected_output`
- `tools_called`
- `expected_tools`
- `metadata`
- `tags`

Use `metadata["mendmark_case_id"]` when you need a stable ID that differs from
the DeepEval case name.

## Repository-integrity metric

The original Mendmark ML repair pack remains usable as one DeepEval custom
metric:

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

The metric returns `1.0` when the hidden repository contract passes and `0.0`
when it fails. A sandbox failure raises an error so infrastructure trouble is
not counted as an agent failure.
