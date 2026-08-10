# Agent harness integrations

Mendmark converts public harness traces into its stable local JSON contract. It
does not import a harness at package import time, constrain the harness version,
or send trace content to a hosted service.

## Supported first-class paths

The initial targets were selected from active Python agent projects on
2026-08-10. GitHub stars are an imperfect adoption signal, so activity and a
stable tool/trace interface were considered as well.

| Harness path | Adoption signal at selection | Mendmark input |
| --- | ---: | --- |
| LangChain / LangGraph | 143,910 / 39,385 GitHub stars | `AIMessage` and `ToolMessage` history |
| CrewAI | 56,908 GitHub stars | Public tool-usage and completion events |
| OpenAI Agents SDK | 28,542 GitHub stars | Public `RunResult.new_items` |

The project sources are the [LangChain](https://github.com/langchain-ai/langchain),
[LangGraph](https://github.com/langchain-ai/langgraph),
[CrewAI](https://github.com/crewAIInc/crewAI), and
[OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
repositories. Mendmark's compatibility job exercises current real objects from
each framework instead of relying only on local facsimiles.

These paths follow the frameworks' documented structures: LangGraph exposes
tool lifecycle events and correlated message tool calls, CrewAI exposes an
event bus with tool-completion events, and the OpenAI Agents SDK exposes public
run items and trace processors. See the official [LangGraph event-streaming
guide](https://docs.langchain.com/oss/python/langgraph/event-streaming),
[CrewAI documentation](https://docs.crewai.com/), and [OpenAI Agents SDK tracing
guide](https://openai.github.io/openai-agents-python/tracing/).

## One-command setup

From the agent application repository:

```bash
python -m pip install 'mendmark-evals==0.6.0'
mendmark equip --framework auto
```

Detection reads only bounded dependency files; it does not import or execute the
application. The command creates five reviewable files under `.mendmark/`:

- `agent-setup.md`: harness-specific capture code and acceptance criteria.
- `evaluator.py`: a deterministic offline evaluator for reviewed snapshots.
- `mendmark-ci.yml`: an inactive, pinned CI template.
- `config.json`: detected integration metadata.
- `.gitignore`: excludes generated report artifacts.

It never edits application code, activates CI, overwrites an existing differing
file, or accepts a baseline. Running it again is idempotent. Use `--dry-run` to
preview its targets.

## Let a coding agent self-equip the repository

Print a prompt that works with repository-capable coding agents:

```bash
mendmark equip --print-agent-prompt
```

The prompt instructs the agent to run detection, read the generated setup file,
capture a real tool-using case, pass the audit, and meet every review criterion.
It explicitly forbids uploading trace content or silently treating observed
production behavior as correct.

The short prompt can also be copied directly:

> Run `mendmark equip --framework auto`, read `.mendmark/agent-setup.md`
> completely, integrate the detected harness, capture at least one reviewed
> tool-using case, run the local audit, and satisfy every acceptance criterion
> before enabling CI. Do not upload trace content or approve observed behavior
> without human review.

## Direct Python API

### LangChain and LangGraph

```python
from mendmark.integrations import write_suite
from mendmark.integrations.langchain import case_from_messages, tool_specs

case = case_from_messages(
    result["messages"],
    case_id="refund-reviewed",
    input=test_input,
    expected_output=expected_output,
    approve_observed=True,
)
write_suite(
    ".mendmark/suite.json",
    [case],
    tool_specs(tools, side_effecting=["refund_order"]),
)
```

Tool calls are joined to `ToolMessage` results by call ID. Both framework
objects and their documented dictionary forms are supported.

### OpenAI Agents SDK

```python
from mendmark.integrations import write_suite
from mendmark.integrations.openai_agents import case_from_result, tool_specs

result = Runner.run_sync(agent, test_input)
case = case_from_result(
    result,
    case_id="refund-reviewed",
    input=test_input,
    expected_output=expected_output,
    approve_observed=True,
)
write_suite(
    ".mendmark/suite.json",
    [case],
    tool_specs(agent.tools, side_effecting=["refund_order"]),
)
```

The adapter pairs public `ToolCallItem` and `ToolCallOutputItem` objects using
their call ID. No OpenAI API call is made by the adapter.

### CrewAI

```python
from mendmark.integrations import write_suite
from mendmark.integrations.crewai import CrewAIRecorder, tool_specs

recorder = CrewAIRecorder().attach()
result = crew.kickoff(inputs=test_inputs)
case = recorder.case(
    case_id="refund-reviewed",
    input=test_input,
    expected_output=expected_output,
    approve_observed=True,
)
write_suite(
    ".mendmark/suite.json",
    [case],
    tool_specs(all_tools, side_effecting=["refund_order"]),
)
```

Attach one recorder in an isolated capture/test process and clear it between
cases. CrewAI's event bus is process-global, so concurrent crews should capture
in separate processes or pass their already-separated event sequences directly
to `case_from_events`.

## Approval boundary

All converters require `expected_tools` unless the caller explicitly supplies
`approve_observed=True`. That escape hatch exists for a one-off, human-reviewed
snapshot. It must not be applied automatically to arbitrary production traces.

For maintained capture code, build and pass an explicit sequence of
`ToolCallRecord` expectations. Mark side-effecting tools explicitly: duplicate
payment, refund, email, write, and deployment calls are otherwise treated as
ordinary calls and receive weaker mutation severity.

The adapters above produce the stable ordered-trace schema `1.0`. If agent
identity, delegation, parallel branches, shared state, or causal dependencies
matter, use `CausalCaseBuilder`, which emits Mendmark's native [multi-agent
schema 2.0](multi-agent.md). Do not flatten a coordination test and then claim
coverage of coordination failures.

```python
from mendmark.integrations import CausalCaseBuilder, write_suite

case = (
    CausalCaseBuilder(
        case_id="parallel-review",
        input=test_input,
        root_agent_id="supervisor",
    )
    .agent("supervisor")
    .agent("billing", allowed_tools=["lookup_order", "refund_order"])
    .agent("risk", allowed_tools=["assess_risk"])
    .delegation("delegate-billing", "supervisor", "billing")
    .delegation("delegate-risk", "supervisor", "risk")
    .tool_call(
        "lookup",
        "billing",
        "lookup_order",
        input_parameters={"order_id": "104"},
        output={"status": "paid"},
        depends_on=["delegate-billing"],
    )
    .result("billing-result", "billing", "supervisor", depends_on=["lookup"])
    .result("risk-result", "risk", "supervisor", depends_on=["delegate-risk"])
    .message(
        "aggregate",
        "supervisor",
        depends_on=["billing-result", "risk-result"],
    )
    .build(
        actual_output=actual_output,
        expected_output=expected_output,
        approve_observed=True,
    )
)
write_suite(".mendmark/multi-agent-suite.json", [case], tool_contracts)
```

The builder validates agent identities, tool authority, unique event IDs,
dependency targets, and acyclicity. Dependencies remain explicit; it never
turns unreliable wall-clock ordering into a causal claim.

## Run and activate CI

```bash
mendmark audit-json .mendmark/suite.json \
  --evaluator-command "python .mendmark/evaluator.py" \
  --output .mendmark/report.json \
  --junit .mendmark/report.xml \
  --sarif .mendmark/report.sarif
```

Review survivors and create an accepted baseline only from a passing audit.
Then copy `.mendmark/mendmark-ci.yml` to
`.github/workflows/mendmark.yml`, open a pull request, and require its
`agent-eval-assurance` check after the first successful run.
