# JSON trace adapter

The JSON adapter lets a team mutation-test traces without importing Mendmark or
DeepEval in its application. Cases and tool declarations use JSON. Existing
evaluators run behind a local command, so prompts and payloads stay inside the
same machine or CI boundary.

## Run the offline example

```bash
mendmark audit-json examples/order_agent_suite.json \
  --evaluator-command "python3 examples/json_evaluator.py" \
  --output /tmp/mendmark-json-report.json
```

The command produces the same 13 controlled faults as the DeepEval example and
makes no model or network calls.

## Suite format

The canonical JSON Schema ships in
`src/mendmark/schemas/suite-v1.schema.json`. A suite has this shape:

```json
{
  "schema_version": "1.0",
  "policy": {"minimum_kill_rate": 0.9},
  "tools": [
    {
      "name": "refund_order",
      "input_schema": {
        "type": "object",
        "properties": {"amount": {"type": "number"}},
        "required": ["amount"]
      },
      "side_effecting": true
    }
  ],
  "cases": [
    {
      "case_id": "refund-104",
      "input": "Refund order 104.",
      "actual_output": "Refund accepted.",
      "expected_output": "Refund accepted.",
      "tools_called": [
        {
          "name": "refund_order",
          "input_parameters": {"amount": 29.99},
          "output": {"status": "accepted"}
        }
      ],
      "expected_tools": []
    }
  ]
}
```

Case IDs and tool names must be unique. Mendmark validates field types, policy
keys, trace structure, required tool arguments, and basic JSON Schema argument
types. Validation errors include a JSON location but never echo argument
values.

## Evaluator command protocol

Mendmark starts the configured command once for the complete audit. It does not
use a shell. The command receives one compact JSON object on stdin:

```json
{"schema_version":"1.0","evaluations":[{"evaluation_id":"evaluation-0","case":{"case_id":"refund-104"}}]}
```

The complete `case` object follows the suite case shape. The evaluator writes
one response to stdout:

```json
{
  "schema_version": "1.0",
  "evaluations": [
    {"evaluation_id": "evaluation-0", "results": [
      {"name": "Tool policy", "score": 1.0, "passed": true}
    ]}
  ]
}
```

The request and response schemas ship as
`src/mendmark/schemas/evaluator-request-v1.schema.json` and
`src/mendmark/schemas/evaluator-response-v1.schema.json`. Metric names must be
unique within each evaluation. Evaluation IDs must be echoed exactly and results
must be returned in request order, one per case. A command failure, timeout,
oversized response, or malformed response
is an infrastructure error and exits with code 2; it never counts as a killed
mutation. The default batch timeout is 60 seconds and can be set to a value
greater than 0 and at most 3600 seconds with `--evaluator-timeout`.

The evaluator receives case content because it must judge each mutation. The
Mendmark report still excludes prompts, answers, tool arguments, and tool
outputs. Treat the suite and evaluator command as trusted local inputs.

The generated privacy-safe contracts ship as `report-v1.schema.json` and
`baseline-v1.schema.json`. Reports include a canonical policy digest and may
include source, suite, policy, and CI identifiers. These values are operational
metadata; do not place secrets or customer content in explicit version flags.

## CI outputs and faster pull requests

Use `--junit path.xml` for test-report systems and `--sarif path.sarif` for code
scanning systems. Both formats contain only the privacy-safe audit metadata.

After accepting a full baseline, `--changed-tools-only` runs original cases and
mutations only for tools whose declaration digest is new or changed. It still
checks all case/tool contracts and untested tools. Keep a scheduled full audit
to cover evaluator or case changes unrelated to tool declarations.

Use `--maximum-mutants N` to abort before any evaluator call when generation
exceeds an approved budget. This controls mutation volume; provider cost per
evaluation remains the evaluator owner's responsibility.
