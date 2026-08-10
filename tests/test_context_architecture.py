"""Context architecture invariants for tasks, roles, and skills."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "pi" / "agent"
KNOWN_EFFECTS = {"read_workspace", "write_artifacts", "edit_files", "write_workspace", "update_beads", "external_write", "push", "deploy", "delete_files"}
WRITE_EFFECTS = {"edit_files", "write_workspace", "update_beads", "external_write", "push", "deploy", "delete_files"}


def load_frontmatter(common, path: Path):
    meta, _body = common.parse_frontmatter_file(path)
    return meta


def test_role_tasks_reference_existing_task_files(common):
    task_ids = {path.stem for path in (AGENT / "tasks").glob("*.md")}
    assert task_ids

    for role_path in sorted((AGENT / "AGENTS.d" / "roles").glob("*.md")):
        meta = load_frontmatter(common, role_path)
        task = meta.get("task")
        assert task in task_ids, f"{role_path} references missing task {task!r}"


def test_roles_declare_boolean_write_access(common):
    for role_path in sorted((AGENT / "AGENTS.d" / "roles").glob("*.md")):
        meta = load_frontmatter(common, role_path)
        assert isinstance(meta.get("writeAccess"), bool), f"{role_path} needs boolean writeAccess"


def test_role_relevant_process_skills_exist():
    skill_ids = {path.parent.name for path in (AGENT / "skills").glob("*/SKILL.md")}
    assert skill_ids

    for role_path in sorted((AGENT / "AGENTS.d" / "roles").glob("*.md")):
        text = role_path.read_text(encoding="utf-8")
        for skill in sorted(set(re.findall(r"`([a-z][a-z0-9]+(?:-[a-z0-9]+)+)`", text))):
            assert skill in skill_ids, f"{role_path} references missing skill {skill!r}"


def test_task_frontmatter_ids_match_filenames(common):
    for task_path in sorted((AGENT / "tasks").glob("*.md")):
        meta = load_frontmatter(common, task_path)
        assert meta.get("id") == task_path.stem


def test_skill_frontmatter_names_match_directories(common):
    for skill_path in sorted((AGENT / "skills").glob("*/SKILL.md")):
        meta = load_frontmatter(common, skill_path)
        if meta.get("name"):
            assert meta["name"] == skill_path.parent.name
        assert meta.get("description"), f"{skill_path} needs a description"


def test_skill_descriptions_use_supported_single_line_scalars():
    for skill_path in sorted((AGENT / "skills").glob("*/SKILL.md")):
        frontmatter = skill_path.read_text(encoding="utf-8").split("---", 2)[1]
        description_lines = [line for line in frontmatter.splitlines() if line.startswith("description:")]
        assert len(description_lines) == 1, f"{skill_path} needs one description line"
        value = description_lines[0].split(":", 1)[1].strip()
        assert value and not value.startswith((">", "|")), f"{skill_path} uses unsupported multiline description syntax"


def test_active_skills_do_not_reference_removed_plan_helper():
    for skill_path in sorted((AGENT / "skills").glob("*/SKILL.md")):
        assert "pi-plans-dir" not in skill_path.read_text(encoding="utf-8"), skill_path


def test_graphify_skill_matches_current_cli_contract():
    graphify = AGENT / "skills" / "graphify"
    assert (graphify / ".graphify_version").read_text(encoding="utf-8") == "0.9.25"
    skill = (graphify / "SKILL.md").read_text(encoding="utf-8")
    assert "agnt graphify" in skill
    assert "path-qualified" in skill
    assert "explicitly approves" in skill
    assert {path.name for path in (graphify / "references").glob("*.md")} == {
        "add-watch.md",
        "exports.md",
        "extraction-spec.md",
        "github-and-merge.md",
        "hooks.md",
        "query.md",
        "transcribe.md",
        "update.md",
    }


def test_simplification_uses_native_tools_and_canonical_references():
    project_init = AGENT / "skills" / "project-init"
    stamp_skill = (AGENT / "skills" / "stamp-stpa-sec" / "SKILL.md").read_text(encoding="utf-8")
    stamp_reference = (AGENT / "skills" / "stamp-stpa-sec" / "references" / "stpa-security.md").read_text(encoding="utf-8")
    research_skill = (AGENT / "skills" / "research" / "SKILL.md").read_text(encoding="utf-8")

    assert not (ROOT / ".envrc.d" / "gh.sh").exists()
    assert not (project_init / "templates" / "gh.sh").exists()
    assert not (AGENT / "skills" / "requesting-code-review" / "references" / "structured-format-parsing.md").exists()
    assert "## STPA-Sec Process" not in stamp_skill
    assert "## STPA-Sec Process" in stamp_reference
    assert "## Core Insight" not in stamp_skill
    assert "## Core Insight" in stamp_reference
    assert "references/UrlVerificationProtocol.md" in research_skill
    for workflow in ("StandardResearch.md", "ExtensiveResearch.md"):
        text = (AGENT / "skills" / "research" / "workflows" / workflow).read_text(encoding="utf-8")
        assert "## CRITICAL: URL Verification Required" not in text
        assert 'curl -s -o /dev/null -w "%{http_code}"' not in text
    assert "shellHook" not in (project_init / "templates" / "flake.nix").read_text(encoding="utf-8")


def test_ponytail_code_cuts_use_native_and_existing_helpers():
    flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
    lock = (ROOT / "flake.lock").read_text(encoding="utf-8")
    agnt = (AGENT / "bin" / "agnt").read_text(encoding="utf-8")
    doctor = (AGENT / "bin" / "agnt_lib" / "doctor.py").read_text(encoding="utf-8")
    health = (AGENT / "bin" / "agnt_lib" / "health.py").read_text(encoding="utf-8")
    runner = (AGENT / "bin" / "agnt_lib" / "runner.py").read_text(encoding="utf-8")
    protocol = (AGENT / "bin" / "agnt_lib" / "runner_protocol.py").read_text(encoding="utf-8")
    scheduler = (AGENT / "bin" / "agnt_lib" / "runner_scheduler.py").read_text(encoding="utf-8")
    tasks = (AGENT / "bin" / "agnt_lib" / "tasks.py").read_text(encoding="utf-8")
    instructions = (AGENT / "bin" / "agent-instructions").read_text(encoding="utf-8")

    assert "flake-utils" not in flake + lock
    assert "nixpkgs.lib.genAttrs" in flake
    assert "jq" not in flake
    assert "direnv" not in flake
    assert not (AGENT / "bin" / "openrouter-api-key").exists()
    assert not (AGENT / "mcp.json").exists()
    assert "install_patch_base" not in (ROOT / "scripts" / "update-pi-config.sh").read_text(encoding="utf-8")
    assert not (ROOT / ".pi" / "skill-evals" / "project-skills-maintenance").exists()
    assert all(name not in agnt.split("from agnt_lib.tasks", 1)[0] for name in ("EVALS", "PROMPT_PATTERNS", "TASKS", "VALID_OUTCOMES", "capture"))
    assert "def check_result(" not in doctor and "check_result," in doctor
    assert "def default_status_runner(" not in health and "default_status_runner" in health
    assert "def utc_now(" not in runner
    assert "def _default_budget(" not in protocol
    assert "TERMINAL_STATUSES" not in scheduler
    assert "def parse_frontmatter(" not in tasks
    assert "def split_frontmatter(" not in instructions
    assert "dependencies = []" not in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "DEFAULT_BASE" not in (AGENT / "bin" / "web-search").read_text(encoding="utf-8")
    assert "catalog-free" not in (AGENT / "bin" / "agnt_lib" / "metrics.py").read_text(encoding="utf-8")


def test_ponytail_shrinks_use_stdlib_and_concrete_clients():
    agnt = (AGENT / "bin" / "agnt").read_text(encoding="utf-8")
    runtime_paths = (AGENT / "bin" / "agnt_lib" / "runtime_paths.py").read_text(encoding="utf-8")
    runner_client = (AGENT / "bin" / "agnt_lib" / "runner_client.py").read_text(encoding="utf-8")
    work = (AGENT / "bin" / "agnt_lib" / "work.py").read_text(encoding="utf-8")
    gateway = (AGENT / "bin" / "agnt_lib" / "gateway.py").read_text(encoding="utf-8")
    metrics = (AGENT / "bin" / "agnt_lib" / "metrics.py").read_text(encoding="utf-8")

    assert not (AGENT / "bin" / "pi-plans-dir").exists()
    assert '"plans-dir": ("print/create the active plans directory", cmd_plans_dir)' in agnt
    assert "def cmd_plans_dir(" in runtime_paths
    for name in ("evals.py", "prompt.py", "runs.py"):
        text = (AGENT / "bin" / "agnt_lib" / name).read_text(encoding="utf-8")
        assert "re.sub(" in text
        assert "for ch in value.lower()" not in text
        assert "for char in value.lower()" not in text
    for name in ("runner_client_status", "runner_client_pause", "runner_client_resume", "runner_client_tick"):
        assert f"def {name}(" not in runner_client
        assert name not in work
        assert name not in gateway
    assert "RunnerClient" in work
    assert "RunnerClient" in gateway
    assert "argparse.BooleanOptionalAction" in metrics
    assert 'add_argument("--no-human-override"' not in metrics
    assert 'add_argument("--no-fallback-used"' not in metrics


def test_project_init_eval_excludes_opt_in_github_templates():
    skill = (AGENT / "skills" / "project-init" / "SKILL.md").read_text(encoding="utf-8")
    workflow_eval = (ROOT / "scripts" / "eval-workflow-compliance.sh").read_text(encoding="utf-8")
    case = workflow_eval.split("case_project_init_clean_scaffold()", 1)[1].split("case_implementation_commits_task_owned_changes()", 1)[0]

    scaffold_paths = case.split("for path in", 1)[1].split("; do", 1)[0]
    prompt = case.split("run_pi '", 1)[1].split("' >", 1)[0]
    assert ".github/pull_request_template.md" in skill.split("Optional only when requested:", 1)[1]
    assert ".envrc.d" not in prompt
    assert ".github/pull_request_template.md" not in scaffold_paths
    assert ".envrc.d/gh.sh" not in scaffold_paths
    assert "created opt-in GitHub template without request" in case


def test_workflow_eval_requires_explicit_skill_provenance():
    workflow_eval = (ROOT / "scripts" / "eval-workflow-compliance.sh").read_text(encoding="utf-8")

    assert "--skill-mode" in workflow_eval
    assert "candidate|deployed" in workflow_eval
    assert "--no-skills" in workflow_eval
    assert '"--skill" "$SKILL_ROOT"' in workflow_eval
    assert "--no-extensions" in workflow_eval
    assert "--no-context-files" in workflow_eval
    assert "--no-prompt-templates" in workflow_eval
    assert "--no-tools" not in workflow_eval
    assert "provenance.txt" in workflow_eval


def test_executing_plans_isolates_main_orchestration_checkout():
    skill = (AGENT / "skills" / "executing-plans" / "SKILL.md").read_text(encoding="utf-8")
    scenario = (ROOT / ".pi" / "skill-evals" / "executing-plans" / "scenarios" / "isolated-main-orchestration.md").read_text(encoding="utf-8")
    workflow_eval = (ROOT / "scripts" / "eval-workflow-compliance.sh").read_text(encoding="utf-8")
    case = workflow_eval.split("case_executing_plans_stops_on_main()", 1)[1].split("case_subagent_driven_rejects_shared_file_parallelism()", 1)[0]

    assert "Treat the current checkout as the orchestration checkout" in skill
    assert "Never switch the orchestration checkout to a feature branch" in skill
    assert "generic implementation or commit authority is not same-checkout authority" in skill
    assert "Load `using-git-worktrees`" in skill
    assert "Prune the worktree only after integration" in skill
    assert "git branch -M main" in case
    assert ".worktrees/" in case
    assert "git branch --show-current" in case
    assert "git status --porcelain" in case
    assert "git worktree list --porcelain" in case
    assert "orchestration checkout left main" in case
    assert "orchestration checkout HEAD changed" in case
    assert "implementation worktree was not on a feature branch" in case
    assert "isolated execution worktree was not created" in case
    assert "execution neither stopped safely nor completed in isolated worktree" in case
    assert "Must keep the orchestration checkout on `main`" in scenario
    assert "Must not merge, delete the branch, or remove the worktree without approval" in scenario


def test_approved_implementation_defaults_through_local_commit():
    global_instructions = (AGENT / "AGENTS.md").read_text(encoding="utf-8")
    project_instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    template_instructions = (AGENT / "skills" / "project-init" / "templates" / "AGENTS.md").read_text(encoding="utf-8")
    common = (AGENT / "skills" / "dev-workflow-common" / "SKILL.md").read_text(encoding="utf-8")

    required_default = "implementation approval includes staging and one local atomic commit"
    assert required_default in global_instructions
    assert required_default in project_instructions
    assert required_default in template_instructions
    assert "Explicit `do not commit` instructions override this default" in common
    assert "Never stage unrelated pre-existing changes" in common
    assert "Do not close the Bead or claim completion while task-owned changes remain uncommitted" in common
    assert "Push, merge, deploy" in common and "explicit approval" in common

    workflow_eval = (ROOT / "scripts" / "eval-workflow-compliance.sh").read_text(encoding="utf-8")
    assert "implementation_commits_task_owned_changes" in workflow_eval
    assert "implementation_honors_no_commit" in workflow_eval


def test_global_instructions_use_direct_lifecycle_start():
    instructions = (AGENT / "AGENTS.md").read_text(encoding="utf-8")

    assert "`agnt work direct-start <id> [--claim]`" in instructions
    assert "`agnt direct start" not in instructions
    assert "run `agnt improve link <id>`" not in instructions
    assert "does not create run bundles, runners, or worktrees" in instructions


def test_default_instructions_batch_reads_and_use_phase_progress():
    instructions = (AGENT / "AGENTS.md").read_text(encoding="utf-8")

    assert "Batch independent read-only tool calls in one turn" in instructions
    assert "Keep ordered mutations, approvals, and safety gates serial" in instructions
    assert "Update progress at phase boundaries" in instructions
    assert "prefer harness/tool execution state over model-authored progress-only turns" in instructions


def test_default_instructions_route_questions_by_durability():
    instructions = (AGENT / "AGENTS.md").read_text(encoding="utf-8")

    assert "Use transient `ask`" in instructions
    assert "current interactive session" in instructions
    assert "Use durable `ticket_question`" in instructions
    assert "survive handoff" in instructions
    assert "block a Bead" in instructions
    assert "selectionMode" in instructions
    assert "typed custom response" in instructions
    assert "Do not chain durable questions" in instructions
    assert "No interactive UI" in instructions and "remain blocked" in instructions
    assert "Approvals are not questions" in instructions
    assert "`ticket_approval`" in instructions


def test_ticket_question_prompt_guidance_keeps_durable_boundary_and_approval_separation():
    bridge = (AGENT / "extensions" / "beads-ask-bridge.ts").read_text(encoding="utf-8")
    question_section, approval_section = bridge.split('name: "ticket_approval"', 1)

    assert "only for handoff, later resumption, or a Bead blocker" in question_section
    assert "before asking for human input" not in question_section
    assert "only when the answer must survive the current session" in question_section
    assert "Use transient ask for current-session clarification or exploration" in question_section
    assert "Do not chain durable questions for ideation" in question_section
    assert "Use ticket_approval for consequential actions requiring approval" in approval_section


def test_token_saver_explains_bounded_batching_and_progress_fallback():
    skill = (AGENT / "skills" / "token-saver" / "SKILL.md").read_text(encoding="utf-8")

    assert "## Batching and progress" in skill
    assert "Batch only independent read-only operations" in skill
    assert "Writes, approvals, and safety gates stay serial" in skill
    assert "Use execution-derived status" in skill
    assert "Update `manage_todo_list` at phase boundaries" in skill
    assert "description: Use when token/context discipline matters" in skill


def test_brainstorming_distinguishes_transient_todos_from_durable_work_state():
    brainstorming = (AGENT / "skills" / "brainstorming" / "SKILL.md").read_text(encoding="utf-8")

    assert "Transient `manage_todo_list` tracking is allowed" in brainstorming
    assert "Do not create or mutate Beads, issues, or PRs before design approval" in brainstorming


def test_preparing_upstream_pr_allows_safe_user_fork_staging_drafts():
    skill_root = AGENT / "skills" / "preparing-upstream-pr"
    skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    mechanics = (skill_root / "references" / "pr-mechanics.md").read_text(encoding="utf-8")

    assert "creation and iterative updates of draft PRs" in skill
    assert "create or update a draft in the user's fork without asking again" in skill
    assert "reviewed predecessor branch for a stacked sequence" in skill
    assert "does not include fork creation, any upstream-repository branch or PR" in skill
    assert "Never mark any draft ready" in skill
    assert "remote destination is absent or an ancestor of the reviewed head" in mechanics
    assert 'git merge-base --is-ancestor "$remote_sha" HEAD' in mechanics
    assert "Without another approval, create the staging draft" in mechanics
    assert "It does not include fork creation, upstream-repository pushes or PRs" in mechanics


def test_nested_skill_runtime_references_are_checked(tmp_path):
    skill_root = tmp_path / "skills" / "example"
    (skill_root / "references").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("---\nname: example\n---\n", encoding="utf-8")
    (skill_root / "references" / "guide.md").write_text("Read `references/missing.md`.\n", encoding="utf-8")

    failures = _skill_runtime_reference_failures(tmp_path)

    assert any("missing references/missing.md" in failure for failure in failures)


def _skill_runtime_reference_failures(agent):
    skill_ids = {path.parent.name for path in (agent / "skills").glob("*/SKILL.md")}
    failures = []

    for path in sorted((agent / "skills").glob("**/*.md")):
        skill_root = agent / "skills" / path.relative_to(agent / "skills").parts[0]
        text = re.sub(
            r"```.*?```",
            lambda match: "\n" * match.group().count("\n"),
            path.read_text(encoding="utf-8"),
            flags=re.DOTALL,
        )
        for line_no, line in enumerate(text.splitlines(), start=1):
            for raw in re.findall(r"`([^`]+)`", line):
                if raw.startswith("~/.pi/agent/skills/"):
                    target = agent / "skills" / raw.removeprefix("~/.pi/agent/skills/")
                    if not target.exists():
                        failures.append(f"{path.relative_to(agent)}:{line_no}: missing {raw}")
                elif raw.startswith("pi/agent/skills/"):
                    failures.append(f"{path.relative_to(agent)}:{line_no}: repo-relative runtime path {raw}")
                elif Path(raw).suffix and raw.startswith(("references/", "scripts/", "templates/", "themes/", "workflows/")):
                    if "<" not in raw and raw != "themes/X.md" and not (skill_root / raw).exists():
                        failures.append(f"{path.relative_to(agent)}:{line_no}: missing {raw}")
                elif "/" in raw and raw.split("/", 1)[0] in skill_ids:
                    failures.append(f"{path.relative_to(agent)}:{line_no}: cross-skill path must use ~/.pi/agent/skills/: {raw}")

    return failures


def test_skill_runtime_references_resolve():
    failures = _skill_runtime_reference_failures(AGENT)
    assert not failures, "broken skill runtime references:\n" + "\n".join(failures)


def test_active_skills_reserve_agnt_invoke_for_cold_or_headless_peers():
    common_path = AGENT / "skills" / "dev-workflow-common" / "SKILL.md"
    common = common_path.read_text(encoding="utf-8")
    assert "plain `agnt invoke` only for noninteractive headless or artifact-backed workers" in common

    review_path = AGENT / "skills" / "requesting-code-review" / "SKILL.md"
    for line in review_path.read_text(encoding="utf-8").splitlines():
        if "agnt invoke" in line:
            assert "--one-shot" in line

    allowed = {common_path, review_path}
    violations = []
    for skill_path in sorted((AGENT / "skills").glob("**/*.md")):
        if skill_path in allowed:
            continue
        for line_no, line in enumerate(skill_path.read_text(encoding="utf-8").splitlines(), start=1):
            if "agnt invoke" in line:
                violations.append(f"{skill_path.relative_to(ROOT)}:{line_no}")
    assert not violations, "interactive peer guidance must use subagent: " + ", ".join(violations)


def test_finish_action_uses_one_closeout_coordinator(common):
    action_path = AGENT / "actions" / "finish.md"
    meta = load_frontmatter(common, action_path)
    body = action_path.read_text(encoding="utf-8")

    assert meta["skills"] == ["finishing-a-development-branch"]
    assert "sole closeout coordinator" in body
    assert "Do not pre-load or stack companion closeout skills" in body


def test_finish_coordinator_declares_trigger_subsumption_and_verification_phases():
    skill = (AGENT / "skills" / "finishing-a-development-branch" / "SKILL.md").read_text(encoding="utf-8")

    expected_rows = [
        "| `verification-before-completion` | Every closeout and after any closeout fix | **Required.** Load once; reuse the recorded baseline, run focused checks after fixes, and run one complete gate for each final candidate; never subsumed. |",
        "| `documentation-standards` | Documentation requested, impacted, or uncertain | Load in validate mode; otherwise coordinator documentation check subsumes generic docs prose. |",
        "| `requesting-code-review` | Non-trivial or risky diff, merge/PR preparation, or required review | Load; otherwise coordinator scope check handles trivial closeout. |",
        "| `code-simplification` | Verification passed and simplification is requested or clearly useful in touched files | Load only now; otherwise coordinator scope check subsumes generic cleanup advice. |",
        "| `session-to-skill-extractor` | Substantial non-trivial wrap-up or Bead close | Load once at final wrap-up; skip routine summaries. |",
    ]
    assert all(row in skill for row in expected_rows)
    assert "Do not repeat the full baseline during repair" in skill
    assert "A tracked final-candidate change invalidates the final gate" in skill
    assert "reuse its current instructions instead of rereading" in skill
    assert "`writing-clearly-and-concisely` is subsumed" in skill
    assert "Safety, approval, verification, documentation, and review gates are never subsumed" in skill


def test_workflow_skills_share_baseline_repair_final_gate_contract():
    verification = (AGENT / "skills" / "verification-before-completion" / "SKILL.md").read_text(encoding="utf-8")
    executing = (AGENT / "skills" / "executing-plans" / "SKILL.md").read_text(encoding="utf-8")
    worktrees = (AGENT / "skills" / "using-git-worktrees" / "SKILL.md").read_text(encoding="utf-8")

    for skill in (verification, executing, worktrees):
        assert "Baseline once" in skill
        assert "Focused repair" in skill
        assert "Final candidate gate" in skill
        assert "unchanged baseline failure" in skill
    assert "task regression: PASS" in verification
    assert "release verdict: NOT VERIFIED" in verification
    assert "If task regression verdict is not PASS, do not claim task completion" in verification
    assert "If release verdict is not PASS, do not claim release readiness" in verification


def test_action_templates_reference_existing_architecture(common):
    task_ids = {path.stem for path in (AGENT / "tasks").glob("*.md")}
    skill_ids = {path.parent.name for path in (AGENT / "skills").glob("*/SKILL.md")}
    role_ids = {path.stem for path in (AGENT / "AGENTS.d" / "roles").glob("*.md")}
    assert task_ids and skill_ids and role_ids

    for action_path in sorted((AGENT / "actions").glob("*.md")):
        meta = load_frontmatter(common, action_path)
        assert meta.get("id") == action_path.stem
        assert meta.get("routingTask") in task_ids
        for skill in meta.get("skills") or []:
            assert skill in skill_ids, f"{action_path} references missing skill {skill!r}"
        role = meta.get("defaultRole")
        assert role in role_ids
        role_meta = load_frontmatter(common, AGENT / "AGENTS.d" / "roles" / f"{role}.md")
        effects = set(meta.get("allowedEffects") or [])
        assert effects, f"{action_path} needs allowedEffects"
        assert effects <= KNOWN_EFFECTS, f"{action_path} has unknown effects {effects - KNOWN_EFFECTS}"
        if role_meta.get("writeAccess") is False:
            assert not WRITE_EFFECTS.intersection(effects), f"{action_path} gives write effects to read-only role {role}"
        assert meta.get("outputContract")
