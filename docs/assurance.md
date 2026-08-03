# User assurance

Mendmark treats user experience, privacy, and package integrity as release
contracts rather than informal expectations.

The automated assurance suite checks that:

- A built wheel installs without network dependency resolution and works from a
  directory outside the source checkout.
- `mendmark --version`, `--help`, packaged tasks, packaged schemas, and the
  complete JSON audit journey work from that clean installation.
- Reports, console output, JUnit, and SARIF do not expose canary values placed in
  prompts, answers, metadata, tags, tool arguments, tool outputs, or descriptions.
- Repeated audits preserve mutation IDs, ordering, decisions, JUnit, SARIF, and
  normalized report contents.
- A failed gate cannot overwrite an accepted baseline.
- Missing inputs, invalid JSON, missing evaluators, timeouts, and mutation-budget
  failures return infrastructure exit code 2 with a concise message and no
  traceback.

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
