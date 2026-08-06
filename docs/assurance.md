# User assurance

Mendmark treats user experience, privacy, and package integrity as release
contracts rather than informal expectations.

The automated assurance suite checks that:

- A built wheel installs without network dependency resolution and works from a
  directory outside the source checkout.
- `mendmark --version`, `--help`, packaged tasks, packaged schemas, and the
  complete single- and multi-agent JSON audit journeys work from that clean
  installation.
- Reports, console output, JUnit, and SARIF do not expose canary values placed in
  prompts, answers, metadata, tags, tool arguments, tool outputs, or descriptions.
- Repeated audits preserve mutation IDs, ordering, decisions, JUnit, SARIF, and
  normalized report contents.
- A failed gate cannot overwrite an accepted baseline.
- Missing inputs, invalid JSON, missing evaluators, timeouts, and mutation-budget
  failures return infrastructure exit code 2 with a concise message and no
  traceback.
- The Agent Eval Golden Set preserves the exact case corpus, mutation-ID digest,
  applicability counts, evaluator outcomes, and gate decisions across releases.
- The Multi-Agent Golden Set pins agent and tool contracts, graph shape,
  mutation identities, all 44 outcomes, and the release-gate decision.
- Independent branches may appear in either scheduler order without creating a
  false positive; event identity and causal dependencies remain authoritative.
- An intentionally output-only multi-agent evaluator detects just 5 of 44
  faults. The other 39 are grouped by failure category and identify the agent,
  event, and tool involved without exposing their payloads.
- Every built-in mutation changes its observed case while preserving the
  expected-output oracle, expected trace, case metadata, tags, and agent
  declarations. Mutation generation never modifies the source case.
- A 25-agent, 100-event graph generates stable, unique mutation IDs, while
  evaluator batching preserves result order and request limits fail before
  spawning customer code.

Run the unit and user-contract suite with:

```bash
python -m pytest
```

Exercise an actual built distribution with:

```bash
python -m build --wheel
python scripts/assure_distribution.py dist/*.whl --project-root .
```

These checks establish repeatable product behavior. They do not replace pilot
evidence. A successful design-partner session should reach a first passing audit
within ten minutes, produce at least one mutation the team considers realistic,
and make any setup failure understandable without reading Mendmark source code.
