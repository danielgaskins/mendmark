from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import sysconfig
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .audit import AuditPolicy, run_audit
from .models import SpecError, TaskSpec
from .mutations import (
    AGENT_EVAL_V1_MUTATIONS,
    DEFAULT_MUTATIONS,
    MULTI_AGENT_V1_MUTATIONS,
    OUTCOME_FIRST_MUTATIONS,
)
from .plugins import load_mutation_plugins
from .runner import RunnerError, _write_json, grade_run, load_manifest, prepare_run


def _tasks_root(value: str) -> Path:
    requested = Path(value).expanduser().resolve()
    if requested.exists() or value != "tasks":
        return requested
    installed = (
        Path(sysconfig.get_path("data")) / "share" / "mendmark" / "tasks"
    ).resolve()
    return installed if installed.is_dir() else requested


def _task(tasks_root: Path, task_id: str) -> TaskSpec:
    return TaskSpec.load(tasks_root / task_id)


def _audit_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", default="mendmark-report.json")
    parser.add_argument("--baseline", default=".mendmark-baseline.json")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--minimum-kill-rate", type=float, default=None)
    parser.add_argument("--allow-critical-survivors", action="store_true")
    parser.add_argument("--allow-untested-tools", action="store_true")
    parser.add_argument("--allow-tool-contract-issues", action="store_true")
    parser.add_argument("--allow-regressions", action="store_true")
    parser.add_argument(
        "--changed-tools-only",
        action="store_true",
        help="evaluate only cases that exercise tools added or changed since baseline",
    )
    parser.add_argument("--junit", help="also write JUnit XML to this path")
    parser.add_argument("--sarif", help="also write SARIF 2.1 JSON to this path")
    parser.add_argument(
        "--maximum-mutants",
        type=int,
        help="stop before evaluation if the audit generates more mutations",
    )
    parser.add_argument("--source-commit", help="source revision recorded in provenance")
    parser.add_argument("--source-ref", help="source branch or tag recorded in provenance")
    parser.add_argument("--suite-version", help="customer suite version recorded in provenance")
    parser.add_argument("--policy-version", help="customer policy version recorded in provenance")
    parser.add_argument(
        "--mutation-plugin",
        action="append",
        default=[],
        metavar="PLUGIN",
        help="trusted operator file, module:attribute, or installed entry-point name",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mendmark",
        description="Mutation-test agent evals and grade ML repair tasks.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--tasks-root", default="tasks", help="task directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("tasks", help="list and validate available tasks")

    equip = subparsers.add_parser(
        "equip", help="scaffold a reviewed agent-harness integration"
    )
    equip.add_argument(
        "--framework",
        choices=("auto", "langgraph", "crewai", "openai-agents", "generic"),
        default="auto",
        help="detect from dependency files or select an integration (default: auto)",
    )
    equip.add_argument(
        "--agent",
        choices=("auto", "codex", "claude-code", "generic", "all"),
        default="auto",
        help="detect or select repository coding-agent instructions (default: auto)",
    )
    equip.add_argument("--project-root", default=".", help="project to equip")
    equip.add_argument(
        "--dry-run", action="store_true", help="show files without writing them"
    )
    equip.add_argument(
        "--print-agent-prompt",
        action="store_true",
        help="print a prompt for a repository coding agent without writing files",
    )

    demo = subparsers.add_parser(
        "demo", help="run a reviewable outcome-assurance enterprise demo"
    )
    demo.add_argument(
        "scenario",
        nargs="?",
        choices=("all", "customer-support", "invoice-approval", "employee-access"),
        default="all",
        help="common business workflow to demonstrate (default: all)",
    )
    demo.add_argument(
        "--output-dir",
        default="mendmark-enterprise-demo",
        help="directory for the reviewable suite and reports",
    )

    prepare = subparsers.add_parser("prepare", help="create a public agent workspace")
    prepare.add_argument("task_id")
    prepare.add_argument("--runs-root", default="runs")
    prepare.add_argument("--operator", required=True)

    grade = subparsers.add_parser("grade", help="grade an existing run")
    grade.add_argument("run_dir")
    grade.add_argument(
        "--runtime",
        choices=("bwrap", "local"),
        default="bwrap",
        help="use local only for framework development",
    )

    show = subparsers.add_parser("show", help="show a run manifest")
    show.add_argument("run_dir")

    audit = subparsers.add_parser(
        "audit", help="mutation-test a DeepEval suite"
    )
    audit.add_argument("suite", help="trusted Python suite file")
    _audit_arguments(audit)

    audit_json = subparsers.add_parser(
        "audit-json", help="mutation-test framework-neutral JSON traces"
    )
    audit_json.add_argument("suite", help="validated Mendmark JSON suite")
    audit_json.add_argument(
        "--evaluator-command",
        required=True,
        help="local command that exchanges a JSON case batch over stdin/stdout",
    )
    audit_json.add_argument(
        "--evaluator-timeout",
        type=float,
        default=60,
        help="batch evaluator timeout in seconds (default: 60)",
    )
    audit_json.add_argument(
        "--evaluator-batch-size",
        type=int,
        help="maximum cases per evaluator process; default sends one complete batch",
    )
    audit_json.add_argument(
        "--evaluator-maximum-request-bytes",
        type=int,
        default=64_000_000,
        help="maximum serialized evaluator request size (default: 64000000)",
    )
    audit_json.add_argument(
        "--mutation-profile",
        choices=("current", "agent-eval-v1", "multi-agent-v1", "outcome-first"),
        default="current",
        help="replay a historical built-in operator profile (default: current)",
    )
    _audit_arguments(audit_json)

    audit_outcomes = subparsers.add_parser(
        "audit-outcomes",
        help="audit reviewed business outcomes without an evaluator dependency",
    )
    audit_outcomes.add_argument("suite", help="validated Mendmark JSON suite")
    _audit_arguments(audit_outcomes)

    sign = subparsers.add_parser(
        "sign", help="sign a report or baseline with Sigstore Cosign"
    )
    sign.add_argument("artifact")
    sign.add_argument("--bundle", required=True)
    sign.add_argument(
        "--key",
        help="Cosign key path or KMS URI; omit for keyless OIDC signing",
    )

    verify = subparsers.add_parser(
        "verify-signature", help="verify a Sigstore Cosign bundle"
    )
    verify.add_argument("artifact")
    verify.add_argument("--bundle", required=True)
    verify.add_argument("--key", help="Cosign public key path or KMS URI")
    verify.add_argument("--certificate-identity")
    verify.add_argument("--certificate-oidc-issuer")
    return parser


def _load_baseline(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {"tools": {}, "agents": {}, "mutations": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        raise RunnerError("invalid Mendmark baseline schema_version")
    unknown = sorted(
        set(data)
        - {"schema_version", "tools", "agents", "mutations", "accepted_from"}
    )
    if unknown:
        raise RunnerError(
            "invalid Mendmark baseline field(s): " + ", ".join(unknown)
        )
    loaded: dict[str, dict[str, str]] = {}
    for field in ("tools", "agents", "mutations"):
        values = data.get(field, {})
        if not isinstance(values, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in values.items()
        ):
            raise RunnerError(f"invalid Mendmark {field} baseline")
        loaded[field] = values
    if not all(
        digest.startswith("sha256:")
        and len(digest) == 71
        and all(character in "0123456789abcdef" for character in digest[7:])
        for digest in list(loaded["tools"].values())
        + list(loaded["agents"].values())
    ):
        raise RunnerError("invalid Mendmark tool or agent digest in baseline")
    if not all(
        status in {"killed", "survived", "error"}
        for status in loaded["mutations"].values()
    ):
        raise RunnerError("invalid Mendmark mutation status in baseline")
    accepted_from = data.get("accepted_from")
    if accepted_from is not None:
        allowed = {
            "mendmark_version",
            "adapter",
            "policy_digest",
            "source_commit",
            "source_ref",
            "suite_version",
            "policy_version",
            "ci_provider",
            "ci_run_id",
        }
        if not isinstance(accepted_from, dict) or set(accepted_from) - allowed:
            raise RunnerError("invalid Mendmark accepted baseline provenance")
        if not all(isinstance(value, str) and value for value in accepted_from.values()):
            raise RunnerError("invalid Mendmark accepted baseline provenance value")
        if not {"mendmark_version", "adapter", "policy_digest"} <= set(accepted_from):
            raise RunnerError("incomplete Mendmark accepted baseline provenance")
        if accepted_from["adapter"] not in {"deepeval", "json-command"}:
            raise RunnerError("invalid Mendmark accepted baseline adapter")
        digest = accepted_from["policy_digest"]
        if not (
            digest.startswith("sha256:")
            and len(digest) == 71
            and all(character in "0123456789abcdef" for character in digest[7:])
        ):
            raise RunnerError("invalid Mendmark accepted baseline policy digest")
    return loaded


def _provenance_value(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if not value or len(value) > 512 or any(ord(character) < 32 for character in value):
        raise RunnerError(
            f"{field} provenance must be 1 to 512 printable characters"
        )
    return value


def _print_audit(report: dict[str, object], output: Path) -> None:
    summary = report["summary"]
    gate = report["gate"]
    tools = report["tools"]
    print("Mendmark agent-eval audit")
    business = report["business_assurance"]
    print(
        "Business assurance: "
        + ("PROTECTED" if business["status"] == "protected" else "AT RISK")
    )
    print(business["headline"])
    if business["estimated_exposure_usd"]:
        print(f"Estimated exposure represented: ${business['estimated_exposure_usd']:,.2f}")
    if business["estimated_recovery_minutes"]:
        print(
            "Estimated recovery effort represented: "
            f"{business['estimated_recovery_minutes']} minutes"
        )
    print(f"Cases: {summary['cases']}")
    print(
        f"Mutations: {summary['mutants']}  "
        f"Killed: {summary['killed']}  "
        f"Survived: {summary['survived']}  "
        f"Errors: {summary['errors']}"
    )
    print(f"Mutation kill rate: {summary['kill_rate']:.1%}")
    if tools["untested"]:
        print("Untested tools: " + ", ".join(tools["untested"]))
    if tools["added_since_baseline"]:
        print("New tools: " + ", ".join(tools["added_since_baseline"]))
    if tools["contract_issues"]:
        print(f"Tool contract issues: {len(tools['contract_issues'])}")
    agents = report.get("agents")
    if agents:
        print(
            f"Agents: {len(agents['declared'])}  "
            f"Events: {agents['events']}  "
            f"Multi-agent cases: {agents['cases']}"
        )
        if agents["untested"]:
            print("Untested agents: " + ", ".join(agents["untested"]))
        if agents["contract_issues"]:
            print(f"Agent contract issues: {len(agents['contract_issues'])}")
        if agents["added_since_baseline"]:
            print("New agents: " + ", ".join(agents["added_since_baseline"]))
        if agents["changed_since_baseline"]:
            print("Changed agents: " + ", ".join(agents["changed_since_baseline"]))
    regressed = report["regressions"]["regressed"]
    if regressed:
        print("Regressed mutations:")
        for mutant_id in regressed:
            print(f"  {mutant_id}")
    survived = [
        mutation
        for mutation in report["mutations"]
        if mutation["status"] == "survived"
    ]
    if survived:
        risks = business["surviving_risks"]
        if risks:
            print("Business risks needing coverage:")
            for risk in risks:
                print(f"  {risk['severity']}: {risk['headline']} [{risk['case_id']}]")
        categories = report["coverage"]["by_category"]
        category_counts = [
            f"{category}={coverage['survived']}"
            for category, coverage in categories.items()
            if coverage["survived"]
        ]
        if category_counts:
            print("Survivors by category: " + ", ".join(category_counts))
        print("Surviving mutations:")
        for mutation in survived:
            context = [
                f"{field.removesuffix('_id')}={mutation[field]}"
                for field in ("agent_id", "target_agent_id", "event_id")
                if field in mutation
            ]
            if mutation.get("tool_name") is not None:
                context.append(f"tool={mutation['tool_name']}")
            context_text = f" ({', '.join(context)})" if context else ""
            print(
                f"  {mutation['severity']}: {mutation['business_headline']} "
                f"({mutation['operator']}) "
                f"[{mutation['source_case_id']}]{context_text}"
            )
    print("Gate: " + ("PASS" if gate["passed"] else "FAIL"))
    for failure in gate["failures"]:
        print(f"  {failure}")
    print(f"Report: {output}")


def _effective_policy(args: argparse.Namespace, base: AuditPolicy) -> AuditPolicy:
    return AuditPolicy(
        minimum_kill_rate=(
            args.minimum_kill_rate
            if args.minimum_kill_rate is not None
            else base.minimum_kill_rate
        ),
        fail_on_critical_survivor=(
            False if args.allow_critical_survivors else base.fail_on_critical_survivor
        ),
        fail_on_untested_tools=(
            False if args.allow_untested_tools else base.fail_on_untested_tools
        ),
        fail_on_tool_contract_issues=(
            False
            if args.allow_tool_contract_issues
            else base.fail_on_tool_contract_issues
        ),
        fail_on_regression=(
            False if args.allow_regressions else base.fail_on_regression
        ),
    )


def _finish_audit(
    report: dict[str, object],
    args: argparse.Namespace,
    *,
    adapter: str,
) -> int:
    report["generated_at"] = datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    policy_json = json.dumps(report["policy"], sort_keys=True, separators=(",", ":"))
    provenance = {
        "mendmark_version": __version__,
        "adapter": adapter,
        "policy_digest": "sha256:"
        + hashlib.sha256(policy_json.encode("utf-8")).hexdigest(),
    }
    optional_provenance = {
        "source_commit": args.source_commit
        or os.environ.get("GITHUB_SHA")
        or os.environ.get("CI_COMMIT_SHA"),
        "source_ref": args.source_ref
        or os.environ.get("GITHUB_REF")
        or os.environ.get("CI_COMMIT_REF_NAME"),
        "suite_version": args.suite_version,
        "policy_version": args.policy_version,
        "ci_run_id": os.environ.get("GITHUB_RUN_ID")
        or os.environ.get("CI_PIPELINE_ID"),
    }
    if os.environ.get("GITHUB_ACTIONS") == "true":
        optional_provenance["ci_provider"] = "github-actions"
    elif os.environ.get("GITLAB_CI") == "true":
        optional_provenance["ci_provider"] = "gitlab-ci"
    provenance.update(
        {
            key: checked
            for key, value in optional_provenance.items()
            if (checked := _provenance_value(value, key)) is not None
        }
    )
    report["provenance"] = provenance
    if args.junit:
        from .ci_outputs import write_junit

        write_junit(args.junit, report)
    if args.sarif:
        from .ci_outputs import write_sarif

        write_sarif(args.sarif, report)
    output = Path(args.output).expanduser().resolve()
    _write_json(output, report)
    baseline_path = Path(args.baseline).expanduser().resolve()
    if args.write_baseline and report["gate"]["passed"]:
        _write_json(
            baseline_path,
            {
                "schema_version": "1.0",
                "tools": report["tools"]["schema_digests"],
                **(
                    {"agents": report["agents"]["schema_digests"]}
                    if "agents" in report
                    else {}
                ),
                "mutations": {
                    item["mutant_id"]: item["status"]
                    for item in report["mutations"]
                },
                "accepted_from": report["provenance"],
            },
        )
    elif args.write_baseline:
        print(
            "Baseline was not updated because the audit gate failed.",
            file=sys.stderr,
        )
    _print_audit(report, output)
    return 0 if report["gate"]["passed"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    tasks_root = _tasks_root(args.tasks_root)
    try:
        if args.command == "tasks":
            for task_dir in sorted(path for path in tasks_root.iterdir() if path.is_dir()):
                task = TaskSpec.load(task_dir)
                print(
                    f"{task.task_id}\t{task.failure_class}\t"
                    f"{task.difficulty}\t{task.title}"
                )
            return 0

        if args.command == "equip":
            from .equip import agent_prompt, equip_project, resolve_agent_hosts

            if args.print_agent_prompt:
                print(agent_prompt(args.project_root, agent=args.agent))
                return 0
            root = Path(args.project_root).expanduser().resolve()
            agent_hosts = resolve_agent_hosts(root, args.agent)
            frameworks, created, unchanged = equip_project(
                args.project_root,
                framework=args.framework,
                agent=args.agent,
                dry_run=args.dry_run,
            )
            action = "Would create" if args.dry_run else "Created"
            print("Detected: " + ", ".join(frameworks))
            print("Agent host: " + ", ".join(agent_hosts))
            for path in created:
                print(f"{action}: {path}")
            for path in unchanged:
                print(f"Unchanged: {path}")
            if not args.dry_run:
                print("Next: ask your coding agent to complete .mendmark/agent-setup.md")
            return 0

        if args.command == "demo":
            from .enterprise_demo import run_enterprise_demo

            result = run_enterprise_demo(
                Path(args.output_dir).expanduser().resolve(), args.scenario
            )
            weak = result["state_only"]["business_assurance"]
            protected = result["protected"]["business_assurance"]
            print("Mendmark enterprise outcome demo")
            print(
                f"State-only evaluation: {weak['status'].upper()} — "
                f"{weak['headline']}"
            )
            print(
                f"Outcome + invariants: {protected['status'].upper()} — "
                f"{protected['headline']}"
            )
            print(f"Reviewable artifacts: {result['output_dir']}")
            return 0 if protected["status"] == "protected" else 1

        if args.command == "prepare":
            task = _task(tasks_root, args.task_id)
            run_dir = prepare_run(
                task,
                Path(args.runs_root),
                operator=args.operator,
            )
            print(run_dir)
            return 0

        if args.command == "grade":
            run_dir = Path(args.run_dir)
            manifest = load_manifest(run_dir)
            task = _task(tasks_root, manifest["task"]["id"])
            result = grade_run(run_dir, task, runtime=args.runtime)
            print(json.dumps(result, indent=2, sort_keys=True))
            if result["infrastructure_error"]:
                return 2
            return 0 if result["success"] else 1

        if args.command == "show":
            print(json.dumps(load_manifest(Path(args.run_dir)), indent=2, sort_keys=True))
            return 0

        if args.command == "sign":
            from .signatures import sign_blob

            sign_blob(args.artifact, args.bundle, key=args.key)
            print(Path(args.bundle).expanduser().resolve())
            return 0

        if args.command == "verify-signature":
            from .signatures import verify_blob

            verify_blob(
                args.artifact,
                args.bundle,
                key=args.key,
                certificate_identity=args.certificate_identity,
                certificate_oidc_issuer=args.certificate_oidc_issuer,
            )
            print("Signature verified.")
            return 0

        if args.command in {"audit", "audit-json", "audit-outcomes"}:
            if args.command == "audit":
                from .deepeval import load_deepeval_suite

                suite = load_deepeval_suite(args.suite)
                evaluator = suite.evaluator
                operators = suite.operators
                adapter = "deepeval"
            elif args.command == "audit-json":
                from .json_adapter import JsonCommandEvaluator, load_json_suite

                suite = load_json_suite(args.suite)
                evaluator = JsonCommandEvaluator(
                    args.evaluator_command,
                    timeout_seconds=args.evaluator_timeout,
                    batch_size=args.evaluator_batch_size,
                    protocol_version=suite.schema_version,
                    maximum_request_bytes=args.evaluator_maximum_request_bytes,
                )
                operators = {
                    "current": DEFAULT_MUTATIONS,
                    "agent-eval-v1": AGENT_EVAL_V1_MUTATIONS,
                    "multi-agent-v1": MULTI_AGENT_V1_MUTATIONS,
                    "outcome-first": OUTCOME_FIRST_MUTATIONS,
                }[args.mutation_profile]
                adapter = "json-command"
            else:
                from .json_adapter import load_json_suite
                from .outcomes import OutcomeContractEvaluator

                suite = load_json_suite(args.suite)
                evaluator = OutcomeContractEvaluator()
                operators = OUTCOME_FIRST_MUTATIONS
                adapter = "json-command"
            external_operators = load_mutation_plugins(args.mutation_plugin)
            operators = operators + external_operators
            baseline_path = Path(args.baseline).expanduser().resolve()
            baseline = _load_baseline(baseline_path)
            mutation_case_ids = None
            previous_mutations = baseline["mutations"]
            changed_tools: list[str] = []
            if args.changed_tools_only:
                changed_tools = sorted(
                    tool.name
                    for tool in suite.tools
                    if baseline["tools"].get(tool.name) != tool.digest
                )
                changed_set = set(changed_tools)
                mutation_case_ids = frozenset(
                    case.case_id
                    for case in suite.cases
                    if any(
                        call.name in changed_set
                        for call in case.actual_tool_calls()
                        + case.expected_tool_calls()
                    )
                )
                previous_mutations = {
                    mutant_id: status
                    for mutant_id, status in previous_mutations.items()
                    if any(
                        mutant_id.startswith(f"{case_id}:")
                        for case_id in mutation_case_ids
                    )
                }
            report = run_audit(
                cases=suite.cases,
                tools=suite.tools,
                evaluator=evaluator,
                policy=_effective_policy(args, suite.policy),
                operators=operators,
                previous_tools=baseline["tools"],
                previous_agents=baseline["agents"],
                previous_mutations=previous_mutations,
                mutation_case_ids=mutation_case_ids,
                maximum_mutants=args.maximum_mutants,
            )
            if args.changed_tools_only:
                report["scope"]["mode"] = "changed-tools"
                report["scope"]["changed_tools"] = changed_tools
            return _finish_audit(report, args, adapter=adapter)
    except (
        FileNotFoundError,
        ImportError,
        KeyError,
        OSError,
        SpecError,
        RunnerError,
        ValueError,
    ) as error:
        print(f"mendmark: {error}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
