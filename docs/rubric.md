# Rubric integration

Mendmark can test a [Rubric](https://github.com/Kareem-Rashed/rubric-eval)
metric suite through the framework-neutral JSON evaluator protocol.

From a source checkout, install the optional dependency:

```bash
pip install -e '.[rubric]'
```

From a Mendmark source checkout, run:

```bash
mendmark audit-json examples/order_agent_suite.json \
  --evaluator-command "python examples/rubric_evaluator.py" \
  --output /tmp/mendmark-rubric-report.json
```

The example combines Rubric's `ToolCallAccuracy`, `ToolCallEfficiency`, and
`ExactMatch` metrics. Mendmark plants 13 faults in the refund-agent case and
reports which faults that combination catches.

With Rubric 0.2.0 and the example configuration, 7 of 13 mutations are killed.
The selected metrics catch missing and reordered tools plus damaged responses.
They do not reject changed arguments, corrupted tool results, an undeclared
tool, or the duplicated refund at the default efficiency threshold. Those six
survivors show exactly where another assertion or stricter policy is needed.

This is a test of the configured metrics, not a ranking of Rubric. A survivor
means the selected metrics need another assertion or domain-specific metric for
that failure. Teams should choose metrics that match their own release risks.

The adapter is an ordinary local command. Mendmark sends it a versioned batch
request over stdin and validates the response from stdout. Neither tool needs a
hosted service, and the canonical Mendmark report omits prompts, tool arguments,
and tool outputs.
