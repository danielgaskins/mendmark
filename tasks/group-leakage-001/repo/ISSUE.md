# Evaluation scores look suspiciously high

Our churn classifier has multiple observations per customer. The current helper
splits individual rows, so observations from one customer can land in both train
and test. That leaks entity-specific information and makes the evaluation
optimistic.

Repair `ml_pipeline.split.split_rows` so that:

- Every row for an `entity_id` stays in exactly one partition.
- The same input and seed always produce the same result.
- Different seeds can change which entities are selected.
- The test partition is reasonably close to `test_fraction` by row count while
  preserving complete entities.
- Inputs are not mutated.
- Invalid fractions and rows without `entity_id` fail clearly.

Do not add third-party dependencies. Preserve the public function signature.

