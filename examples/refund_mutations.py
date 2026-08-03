"""Example domain-specific mutation plugin for refund confirmations."""

from __future__ import annotations

from mendmark.mutations import Mutant


class RemoveRefundAmount:
    name = "refund.amount_omitted"
    category = "refund-policy"
    description = "The refund confirmation omits the refunded amount"
    severity = "high"

    def mutate(self, case, tools):
        if not any(call.name == "refund_order" for call in case.tools_called):
            return []
        return [
            Mutant(
                mutant_id=f"{case.case_id}:{self.name}:final",
                operator=self.name,
                category=self.category,
                description=self.description,
                severity=self.severity,
                source_case_id=case.case_id,
                case=case.with_changes(actual_output="The refund was accepted."),
                tool_name="refund_order",
            )
        ]


MUTATION_OPERATORS = (RemoveRefundAmount(),)
