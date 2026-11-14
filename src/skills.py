"""Agent Skills (https://agentskills.io): discovered only in <cwd>/.agents/skills/<name>/SKILL.md."""
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path


def discover(root: Path | None = None) -> dict[str, Skill]:
    """Parse every SKILL.md under root (default <cwd>/.agents/skills), sorted by name."""
    root = root or Path(os.getcwd()) / ".agents" / "skills"
    skills = {}
    for path in sorted(root.glob("*/SKILL.md")):
        try:
            _, front, body = path.read_text().split("---", 2)
            meta = yaml.safe_load(front) or {}
        except (ValueError, yaml.YAMLError) as e:
            print(f"⚠️  skill {path}: bad frontmatter ({e}), skipped", file=sys.stderr)
            continue
        name, description = meta.get("name"), meta.get("description")
        if not name or not description:
            print(f"⚠️  skill {path}: missing name or description, skipped", file=sys.stderr)
            continue
        if name != path.parent.name:
            print(f"⚠️  skill {path}: name '{name}' != directory name, loading anyway", file=sys.stderr)
        skills[name] = Skill(name, " ".join(str(description).split()), body.strip(), path)
    return skills


def catalog(skills: dict[str, Skill]) -> str:
    return "\n".join(f"- {s.name}: {s.description}" for s in skills.values())


def render(skill: Skill) -> str:
    """Skill body as given to the model, with its directory so relative references resolve."""
    return (f'<skill_content name="{skill.name}" dir="{skill.path.parent}">\n'
            f"When to use: {skill.description}\n\n{skill.body}\n</skill_content>")
