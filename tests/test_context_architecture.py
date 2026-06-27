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


def test_active_skills_do_not_reference_removed_plan_helper():
    for skill_path in sorted((AGENT / "skills").glob("*/SKILL.md")):
        assert "pi-plans-dir" not in skill_path.read_text(encoding="utf-8"), skill_path


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
