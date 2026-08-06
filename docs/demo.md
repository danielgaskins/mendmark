# Mendmark demonstration

The narrated two-minute demonstration is published at
[`docs/assets/mendmark-weak-eval-demo.mp4`](assets/mendmark-weak-eval-demo.mp4).

## What the demonstration shows

The recording uses the original v1 fault inventory. The refund-agent case
passes because its evaluator compares only the final response. Nine of thirteen
controlled changes escape, including changed refund arguments, corrupted tool
results, and a duplicated refund.

The complete evaluator checks ordered tool calls, arguments, results, and the
final response. It catches all thirteen changes.

The current inventory adds omitted, unexpected, and wrong-type argument faults.
The same weak example now misses 15 of 19 mutations, while the complete
evaluator kills all 19. The recording remains useful for the workflow and UI;
the README and generated reports are authoritative for current counts.
