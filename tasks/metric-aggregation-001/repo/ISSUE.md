# Benchmark scores change when one task is retried

`macro_task_success` currently pools every trial for a model. Tasks with more
trials therefore receive more weight, so retrying one task can move the headline
score even when no task-level success rate changes.

Return a mapping from model name to macro task success:

1. Compute the success rate separately for each `(model, task_id)` pair.
2. Average those task-level rates with equal weight within each model.
3. Reject duplicate `(model, task_id, trial)` identifiers.
4. Require non-empty string `model` and `task_id`, a non-boolean integer `trial`,
   and a boolean `passed` value.
5. Reject an empty record collection.
6. Return model keys in deterministic lexical order.

Do not add third-party dependencies.

