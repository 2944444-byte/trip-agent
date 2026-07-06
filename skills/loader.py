"""Load Markdown skills.

A "skill" is a folder under skills/ containing a SKILL.md file with YAML-ish
frontmatter (name, description) followed by the instructions body. Skills are
expertise expressed as prompt text — they are injected into the model, unlike
tools, which are code the model calls. This loader keeps the format dependency-free
(no PyYAML): the frontmatter is a few simple `key: value` lines.
"""
from pathlib import Path

_SKILLS_DIR = Path(__file__).resolve().parent


def _parse(text):
    """Split a SKILL.md into {name, description, body}."""
    name = description = None
    body = text.strip()

    if text.lstrip().startswith("---"):
        # frontmatter is delimited by the first two '---' lines
        _, _, rest = text.partition("---")
        header, sep, remainder = rest.partition("---")
        if sep:
            body = remainder.strip()
            for line in header.strip().splitlines():
                key, sep, value = line.partition(":")
                if not sep:
                    continue
                key, value = key.strip().lower(), value.strip()
                if key == "name":
                    name = value
                elif key == "description":
                    description = value
    return {"name": name, "description": description, "body": body}


def load_skills(skills_dir=_SKILLS_DIR):
    """Return a list of parsed skills found in `skills_dir` (sorted by name)."""
    skills = []
    for skill_md in sorted(Path(skills_dir).glob("*/SKILL.md")):
        skills.append(_parse(skill_md.read_text(encoding="utf-8")))
    return skills


def skills_prompt(skills_dir=_SKILLS_DIR):
    """Render all skills as a prompt section to append to the system prompt.

    Returns (prompt_text, loaded_names). prompt_text is "" if no skills exist.
    """
    skills = load_skills(skills_dir)
    if not skills:
        return "", []
    sections = "\n\n".join(s["body"] for s in skills)
    text = (
        "\n\n# Loaded skills\n"
        "Apply the following expert skills when relevant:\n\n" + sections
    )
    return text, [s["name"] for s in skills]
