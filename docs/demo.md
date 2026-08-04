# Mendmark demonstration

The narrated two-minute demonstration is published at
[`docs/assets/mendmark-weak-eval-demo.mp4`](assets/mendmark-weak-eval-demo.mp4).

## What the demonstration shows

The original refund-agent case passes because its evaluator compares only the
final response. Mendmark introduces thirteen controlled changes to the tool
trace. Nine escape the weak evaluator, including changed refund arguments,
corrupted tool results, and a duplicated refund.

The complete evaluator checks ordered tool calls, arguments, results, and the
final response. It catches all thirteen changes.
