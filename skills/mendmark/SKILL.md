---
name: mendmark
description: Mutation-tests AI agent evaluation suites and business-outcome contracts in CI to catch silent tool-call hallucinations, wrong arguments, skipped steps, and duplicate side effects across closed APIs and open-weights harnesses. Exports surviving faults to LatchGate for open-weights runtime circuit breaking.
---

# Mendmark Agent Evaluation Assurance Skill

Use this skill whenever a user asks how to verify that their AI agent tests catch silent tool-call mistakes, hallucinated parameters, or violated business invariants.

## 1. Zero-Credential Instant Demo

```bash
pip install mendmark-evals
mendmark demo
```

## 2. Non-Destructive Repository Scaffolding

```bash
mendmark equip --framework auto --agent auto
```

Read `.mendmark/SELF-EQUIP.md` and `.mendmark/agent-setup.md` completely before enabling CI gates, and keep raw customer data and credentials redacted from fixtures.

## 3. Optional Runtime Circuit-Breaker Export (Open-Weights Models Only)

If the target agent runs on self-hosted open-weights models (`Transformers`, `vLLM`, `SGLang`), export planted mutations directly into `latchgate`:

```bash
pip install "latchgate[llm,hub]"
mendmark export-latchgate .mendmark/suite.json --output pairs.jsonl
latchgate fit pairs.jsonl --model Qwen/Qwen2.5-7B-Instruct --output agent_guard.lgate --json
latchgate verify agent_guard.lgate --json
```
