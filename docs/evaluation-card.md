# Mendmark v0.1 evaluation card

Status: development artifact; not yet a model leaderboard

## Intended use

Mendmark measures whether a tool-using coding agent can identify and repair
small, realistic failures in machine-learning pipelines. It is intended for:

- Comparing agent scaffolds or models under controlled conditions.
- Studying which ML-system failure classes agents miss.
- Producing failure traces for a later post-training experiment.
- Demonstrating and testing evaluation infrastructure.

It is not intended to estimate general software-engineering ability, frontier
model safety, or production readiness from a single aggregate score.

## Unit of evaluation

One task is a versioned repository, issue statement, public test suite, hidden
deterministic grader, and author-only reference repair. A run records the task
digest, initial and final workspace digests, framework version, operator, disclosed
assistant, timestamps, grader runtime, raw output, and infrastructure status.

## Current coverage

The development set contains five introductory tasks:

1. Entity leakage across a random data split.
2. Micro-averaging that overweights frequently retried tasks.
3. Seed handling that mutates inputs and global random state.
4. Temporal training leakage from labels unavailable at the cutoff.
5. Preprocessing refit at inference time.

These tasks validate the harness and taxonomy. Five hand-authored introductory
tasks are not enough to rank models credibly.

## Grading

Current tasks use deterministic Python tests. Public tests establish the callable
contract and common behavior. Hidden tests measure the target failure and edge
conditions. Reference repairs must pass the combined suite; broken baselines must
fail for a failure-specific reason.

Default grading requests Bubblewrap isolation with networking disabled and the host
runtime mounted read-only. If the host cannot create the required namespace, the
attempt is labeled `infrastructure_error`, `valid: false`, and `isolated: false`.
It is never counted as agent failure. Local grading exists only for framework
development and is marked non-isolated.

## Validity controls

- Requirements enforced by hidden tests must be stated or reasonably inferable
  from the issue and repository context.
- Each baseline and reference pair is exercised in framework integration tests.
- Task and workspace content are hashed into run manifests.
- Infrastructure failures are separated from behavioral outcomes.
- Inputs, seeds, ordering, and tie-break rules are explicit where relevant.
- Task wording and hidden tests should be independently reviewed before any public
  model comparison.

The entity-split task originally asked for a test size that was merely "reasonably
close" while its hidden grader imposed a numerical tolerance. That ambiguity was
found during interview-preparation review. The contract now asks for the closest
attainable complete-entity partition with an explicit tie-break, and the hidden
test computes that contract directly. This correction is retained as a concrete
example of task auditing.

## Known limitations

- The task set is small, synthetic, and authored by one team.
- Tasks are introductory and do not yet measure long-horizon agent behavior.
- The checked-in development tasks, hidden tests, and references are public to
  repository readers and therefore cannot serve as a protected holdout.
- There is no model-based or blinded human grader yet.
- No inter-rater agreement or external task review has been completed.
- No repeated model runs, uncertainty intervals, cost, or latency comparison has
  been published.
- Bubblewrap cannot run under every host kernel configuration. Hosted evaluation
  should use disposable VMs or comparably strong isolation.

## Publication gate

Do not present a model ranking until all of the following hold:

1. At least 20 audited tasks span several difficulty levels.
2. A protected holdout or procedurally generated variants reduce direct exposure.
3. Each task receives independent prompt/grader review.
4. Multiple trials support uncertainty and variance reporting.
5. Costs, latency, timeouts, and invalid infrastructure runs are reported.
6. A stratified sample of trajectories receives blinded human review.

## AI assistance and ownership

Agents may help implement tasks, framework code, tests, and analysis. Run manifests
record disclosed assistance. Daniel Gaskins remains responsible for the research
question, task validity, acceptance of changes, independent reproduction, and every
published claim. Employer-specific restrictions still govern interviews and
take-home assessments.
