# Design-partner pilot guide

The pilot goal is to learn whether Mendmark finds an evaluator blind spot that a
team considers worth fixing before release. It is not a general product demo.

## Entry criteria

- A tool-using agent with at least one passing eval case.
- A local or CI environment allowed to process the suite.
- An owner who can change an evaluator if a meaningful mutation survives.
- Agreement not to send Mendmark raw case content or credentials.

## Sixty-minute onboarding

1. Record the current framework, case count, tool count, and release decision.
2. Choose DeepEval or export `order_agent_suite.json`-shaped JSON.
3. Run a full audit with `--maximum-mutants` set to an agreed cost ceiling.
4. Review critical survivors and tool-contract failures.
5. Strengthen one evaluator, rerun, and save an accepted baseline only on pass.
6. Add a changed-tool audit to pull requests and schedule a full audit.

## Measurements

Record only aggregate or approved metadata:

| Measure | Before | After |
| --- | ---: | ---: |
| Setup minutes | | |
| Original cases | | |
| Generated mutations | | |
| Evaluator/model calls | | |
| Runtime seconds | | |
| Estimated evaluator cost | | |
| Critical survivors | | |
| Total survivors | | |
| Evaluators changed | | |

Also record whether a survivor would have blocked a real release, which adapter
work was painful, and whether the privacy-safe report may leave the environment.

## Success criteria

A strong pilot finds at least one relevant survivor, leads to an evaluator or
policy improvement, and results in a second CI audit. A clean audit is still
useful if the team accepts the tested failure classes as relevant. General
interest without a real suite run is not product validation.

Apply through the repository's **Mendmark pilot request** issue form. Never paste
prompts, traces, tool arguments, outputs, or customer data into an issue.
