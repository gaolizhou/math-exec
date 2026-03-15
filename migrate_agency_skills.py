from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

WORKSPACE = Path("/Users/lizgao/code/math-exec")
SOURCE_ROOT = WORKSPACE / "agency-agents-src"
SKILLS_ROOT = WORKSPACE / ".codebuddy" / "skills"
INIT_SCRIPT = Path(
    "/Applications/CodeBuddy CN.app/Contents/Resources/app/extensions/genie/out/extension/builtin/skill-creator/scripts/init_skill.py"
)

AGENT_DIRS = [
    "design",
    "engineering",
    "game-development",
    "marketing",
    "paid-media",
    "sales",
    "product",
    "project-management",
    "testing",
    "support",
    "spatial-computing",
    "specialized",
    "strategy",
]

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


def slugify(value: str) -> str:
    lowered = value.lower()
    collapsed = re.sub(r"[^a-z0-9]+", "-", lowered)
    return collapsed.strip("-")


def parse_source_markdown(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text.strip()

    raw_frontmatter, body = match.groups()
    metadata: dict[str, str] = {}
    for line in raw_frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")

    return metadata, body.strip()


def yaml_quote(value: str) -> str:
    normalized = " ".join(value.split())
    escaped = normalized.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_skill_content(skill_slug: str, source_name: str, source_description: str, source_relpath: Path, source_body: str) -> str:
    description = (
        f"This skill should be used when the user needs the imported {source_name} specialization. "
        f"Original scope: {source_description}"
    )
    return f"""---
name: {skill_slug}
description: {yaml_quote(description)}
---

# {source_name}

## Overview

Provide the imported `{source_name}` specialization from `agency-agents` as a CodeBuddy project skill. Apply the role's mission, rules, workflows, deliverables, and success metrics to the current task.

## When to Use

Activate this skill when the user's request matches this source scope:

- `{source_description}`
- Source file: `{source_relpath.as_posix()}`

## Operating Guidelines

- Treat the imported content below as domain guidance for this specialization.
- Adapt all recommendations to the current repository, tool availability, and explicit user instructions.
- Ignore source-platform-specific metadata such as `color`, `emoji`, `vibe`, and unsupported tool declarations.
- Prefer concrete deliverables, repo-aware edits, and measurable outcomes whenever the imported workflow suggests them.
- Follow higher-priority system, developer, user, and project rules if anything conflicts.

## Imported Instructions

{source_body}
"""


def init_skill_dir(skill_slug: str) -> Path:
    skill_dir = SKILLS_ROOT / skill_slug
    if skill_dir.exists():
        shutil.rmtree(skill_dir)

    subprocess.run(
        ["python3", str(INIT_SCRIPT), skill_slug, "--path", str(SKILLS_ROOT)],
        check=True,
        cwd=str(WORKSPACE),
    )

    for extra_dir in ("scripts", "references", "assets"):
        extra_path = skill_dir / extra_dir
        if extra_path.exists():
            shutil.rmtree(extra_path)

    return skill_dir


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for dirname in AGENT_DIRS:
        base = SOURCE_ROOT / dirname
        if not base.exists():
            continue
        files.extend(sorted(base.rglob("*.md")))
    return files


def main() -> None:
    source_files = iter_source_files()
    if not source_files:
        raise SystemExit("No source agent markdown files found.")

    SKILLS_ROOT.mkdir(parents=True, exist_ok=True)

    converted = []
    for path in source_files:
        metadata, body = parse_source_markdown(path)
        source_name = metadata.get("name", path.stem.replace("-", " ").title())
        source_description = metadata.get("description", f"Imported from {path.name}")
        skill_slug = slugify(path.stem)
        skill_dir = init_skill_dir(skill_slug)
        skill_content = build_skill_content(
            skill_slug=skill_slug,
            source_name=source_name,
            source_description=source_description,
            source_relpath=path.relative_to(SOURCE_ROOT),
            source_body=body,
        )
        (skill_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")
        converted.append(skill_slug)

    print(f"Converted {len(converted)} skills into {SKILLS_ROOT}")
    print("First 10 skills:")
    for skill in converted[:10]:
        print(f"- {skill}")


if __name__ == "__main__":
    main()
