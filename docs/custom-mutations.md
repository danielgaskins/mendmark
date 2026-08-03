# Custom mutation plugins

Built-in faults cover common tool and response failures. A domain can add its
own controlled faults without changing Mendmark.

An operator defines stable metadata and returns `Mutant` objects:

```python
from mendmark.mutations import Mutant


class RemoveApprovalCode:
    name = "payments.approval_code_removed"
    category = "payments"
    description = "A payment confirmation omits its approval code"
    severity = "high"

    def mutate(self, case, tools):
        return [
            Mutant(
                mutant_id=f"{case.case_id}:{self.name}:final",
                operator=self.name,
                category=self.category,
                description=self.description,
                severity=self.severity,
                source_case_id=case.case_id,
                case=case.with_changes(actual_output="Payment accepted."),
                tool_name="charge_card",
            )
        ]


MUTATION_OPERATORS = (RemoveApprovalCode(),)
```

Pass a trusted file to either audit command:

```bash
mendmark audit examples/order_agent_suite.py \
  --mutation-plugin examples/refund_mutations.py
```

A DeepEval suite may export `MUTATION_OPERATORS` or
`get_mutation_operators()` directly. Installed packages can publish an entry
point in the `mendmark.mutations` group, and a CLI plugin can also use
`package.module:attribute`.

Operator names must match `^[a-z][a-z0-9_.-]*$` and be unique. Severity is one
of `low`, `medium`, `high`, or `critical`. Every mutation ID must start with
`<case_id>:<operator_name>:` and be unique across the audit. These rules keep
baseline comparisons deterministic. Import, initialization, generation, and
contract failures stop the audit as infrastructure errors; they do not become
successful kills.

Plugins are executable Python. Load only code trusted at the same level as the
suite and evaluator command.
