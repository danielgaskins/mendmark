# Mendmark ML integrity pack evaluation card

This card covers the original ML repository-integrity pack. Mendmark 0.3 also
includes mutation audits for general agent eval suites. See
[`agent-mutation-audits.md`](agent-mutation-audits.md) for that system's scope
and interpretation.

Status: framework demonstration, not a model leaderboard

## Evaluation question

Mendmark asks whether a coding agent's edited repository still satisfies the
experiment contract stated by an ML repair task. It focuses on failures that can
survive a clean final answer and a passing public test suite.

It is intended for:

- Testing repository-changing agents against explicit ML invariants.
- Comparing agent scaffolds or models under controlled conditions.
- Turning discovered ML failure modes into deterministic regression cases.
- Adding repository-level evidence to an output or trace evaluation system.

It does not estimate general software-engineering ability, frontier-model
safety, or production readiness from one aggregate score.

## Relationship to DeepEval

DeepEval evaluates LLM applications through test cases, traces, component-level
metrics, and agent metrics. Mendmark operates after a coding agent has edited a
repository. It runs hidden deterministic tests against the edited code and
returns a binary experiment-integrity result.

The optional `MendmarkIntegrityMetric` exposes that result as a DeepEval custom
metric. It does not use an LLM judge. This separation allows a team to evaluate
the agent's behavior and the repaired system's invariants in the same CI run.

## Unit of evaluation

One task contains:

- A versioned repository.
- A written issue and public tests.
- A hidden deterministic grader.
- An author-maintained reference repair.

A run records task and workspace digests, framework version, operator label,
timestamps, grader runtime, raw output, and infrastructure status.

## Current coverage

The development set contains five introductory tasks:

1. Entity leakage across a random data split.
2. Micro-averaging that overweights frequently retried tasks.
3. Seed handling that mutates inputs and global random state.
4. Temporal training leakage from labels unavailable at the cutoff.
5. Preprocessing refit at inference time.

These tasks validate the harness and taxonomy. They are not enough to rank
models credibly.

## Grading

Current tasks use deterministic Python tests. Public tests define the callable
contract and common behavior. Hidden tests measure the target failure and edge
conditions. A reference repair must pass the combined suite. A broken baseline
must fail for a failure-specific reason.

Default grading requests Bubblewrap isolation with networking disabled and the
host runtime mounted read-only. If the host cannot create the namespace, the
attempt is labeled `infrastructure_error`, `valid: false`, and `isolated: false`.
It is never counted as an agent failure. Local grading exists for trusted
framework development and is marked non-isolated.

## Validity controls

- Hidden requirements must be stated or reasonably inferable from the issue and
  repository context.
- Framework tests exercise every baseline and reference pair.
- Task and workspace contents are hashed into run manifests.
- Infrastructure failures remain separate from behavioral outcomes.
- Inputs, seeds, ordering, and tie-break rules are explicit where relevant.
- Task wording and hidden tests require independent review before a public model
  comparison.

The entity-split task originally asked for a test size that was merely
"reasonably close" while its grader imposed a numerical tolerance. Review found
that the grader was enforcing a rule the task had not stated. The task now asks
for the closest attainable complete-entity partition with an explicit tie-break,
and the hidden test computes that contract directly. This correction is retained
as an example of why graders themselves must be audited.

## Known limitations

- The task set is small, synthetic, and authored by one team.
- Tasks are introductory and do not measure long-horizon agent behavior.
- Checked-in tasks, hidden tests, and references cannot serve as a protected
  holdout.
- No independent task review has been completed.
- No repeated agent runs, uncertainty intervals, cost, or latency comparison has
  been published.
- The framework does not yet capture agent trajectories.
- Bubblewrap cannot run under every host kernel configuration.

## Publication gate

Do not present a model ranking until all of the following hold:

1. At least 20 audited tasks span several difficulty levels.
2. A protected holdout or generated variants reduce direct exposure.
3. Each task receives independent issue and grader review.
4. Multiple trials support uncertainty and variance reporting.
5. Costs, latency, timeouts, and invalid infrastructure runs are reported.
6. A stratified sample of trajectories receives blinded human review.
