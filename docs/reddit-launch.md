# Reddit feedback launch

The goal is to recruit qualified design partners and learn where Mendmark fails
on real suites. It is not to maximize clicks.

## Posting guidance

- Disclose that you are the author and that Mendmark is free, MIT-licensed, and
  local-only today.
- Lead with the evaluator blind spot, one reproducible result, and questions for
  practitioners.
- Link directly to the repository. Do not use tracking or shortened links.
- Post once in a community whose current rules allow it. Answer technical
  questions and do not repeat the same promotional copy across communities.
- Never ask respondents to post private traces, prompts, payloads, credentials,
  or customer data.

As checked on August 4, 2026, r/LLMDevs permits transparent sharing of free
open-source projects. r/MachineLearning directs projects and commercial posts to
its recurring self-promotion thread. Re-check the displayed community rules
immediately before posting because moderation policies change.

## Primary post draft for r/LLMDevs

**Title:** I built an open-source mutation tester for agent evals—what failure
classes are missing?

**Body:**

I am the author of Mendmark, a free MIT-licensed Python tool that tests whether
agent evals actually notice broken tool behavior.

The problem I kept seeing was that an agent case could pass because the final
answer looked right while its evaluator ignored the tool trace. Mendmark starts
with a passing case, changes one thing at a time—such as removing a required
call, changing an argument, corrupting a result, or repeating a side effect—and
runs the same evaluator again.

In the included refund-agent example, a deliberately weak final-answer evaluator
misses 9 of 13 injected faults. A complete tool-trace evaluator catches all 13.
The run is deterministic and offline.

Mendmark runs locally or in CI. It supports DeepEval plus a framework-neutral
JSON subprocess protocol, and its reports omit prompts, answers, tool arguments,
and tool outputs. There is no hosted service.

Repository: https://github.com/danielgaskins/mendmark

I would value blunt feedback from people running tool-using agents:

1. Which built-in mutation looks unrealistic?
2. Which important tool or recovery failure is missing?
3. What trace/eval format would prevent you from trying this on a real suite?

I am also looking for a few design partners willing to run a one-hour local
pilot. Please do not share private traces or customer data publicly.

## Short entry for r/MachineLearning's self-promotion thread

I built Mendmark, a free MIT-licensed mutation-testing tool for tool-using agent
eval suites. It injects controlled faults into passing traces, reruns the team's
existing evaluators, and reports the wrong calls, repeated side effects, hidden
tool errors, or damaged responses those evaluators miss. It runs locally, has no
mandatory runtime dependencies, and supports DeepEval or a JSON subprocess
protocol. I am looking for technical feedback and design partners with real
agent eval suites: https://github.com/danielgaskins/mendmark

## Response qualification

A useful design-partner lead has a tool-using agent, at least one passing case,
permission to run the suite locally, and an owner able to improve an evaluator.
Move qualified respondents to the privacy-safe pilot process rather than asking
for implementation details in a public Reddit thread.
