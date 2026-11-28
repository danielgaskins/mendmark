# Agent Guide (`danielgaskins/mendmark`)

`mendmark-evals` (`pip install mendmark-evals`) mutation-tests AI agent evaluation suites across tool calls, arguments, ordering, multi-agent causal handoffs, and durable business outcomes.

## Quick Verification & Equip Workflow

```bash
mendmark demo
mendmark equip --framework auto --agent auto
```

## Pairing Mendmark (CI) with LatchGate (Runtime)

- **Closed APIs (`OpenAI`, `Anthropic`, hosted APIs):** Use `mendmark-evals` in CI alongside deterministic tool-boundary invariants.
- **Self-hosted open-weights models (`Transformers`, `vLLM`, `SGLang`):** Export counterfactual fault pairs from any Mendmark suite into [`latchgate`](https://github.com/danielgaskins/latchgate) (`pip install latchgate`):

```bash
mendmark export-latchgate examples/order_agent_suite.json --output calibration_pairs.jsonl
latchgate fit calibration_pairs.jsonl --model Qwen/Qwen2.5-7B-Instruct --output order_agent.lgate --json
```
