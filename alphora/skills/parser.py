# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
SKILL.md 文件解析器

负责解析 agentskills.io 标准格式的 SKILL.md 文件：
- YAML frontmatter（由 --- 分隔符包裹）
- Markdown 正文（指令内容）

支持宽松解析模式和严格校验模式。
"""

from pathlib import Path
from typing import Tuple, Dict, Any, List
import logging
import re

import yaml

from .models import Skill, SkillContent, NAME_PATTERN
from .exceptions import SkillParseError, SkillValidationError

logger = logging.getLogger(__name__)

# frontmatter 分隔符正则
_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n?(.*)",
    re.DOTALL
)


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    解析 YAML frontmatter 和 Markdown 正文

    Args:
        content: SKILL.md 文件的完整文本内容

    Returns:
        (frontmatter_dict, markdown_body) 元组

    Raises:
        SkillParseError: frontmatter 格式错误或 YAML 解析失败
    """
    content = content.strip()

    if not content.startswith("---"):
        raise SkillParseError(
            "SKILL.md must start with YAML frontmatter (---). "
            "See https://agentskills.io/specification for format details."
        )

    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise SkillParseError(
            "Invalid frontmatter format. Expected:\n"
            "---\n"
            "name: skill-name\n"
            "description: ...\n"
            "---\n"
            "(markdown body)"
        )

    yaml_str = match.group(1)
    body = match.group(2).strip()

    try:
        frontmatter = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        raise SkillParseError(f"YAML parsing failed: {e}")

    if not isinstance(frontmatter, dict):
        raise SkillParseError(
            "Frontmatter must be a YAML mapping (key: value pairs). "
            f"Got: {type(frontmatter).__name__}"
        )

    return frontmatter, body


def parse_skill_md(skill_dir: Path) -> Tuple[Dict[str, Any], str]:
    """
    从 Skill 目录读取并解析 SKILL.md

    Args:
        skill_dir: Skill 目录路径

    Returns:
        (frontmatter_dict, markdown_body) 元组

    Raises:
        SkillParseError: 文件不存在或解析失败
    """
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        raise SkillParseError(
            f"SKILL.md not found in '{skill_dir}'. "
            f"Every skill directory must contain a SKILL.md file."
        )

    if not skill_md.is_file():
        raise SkillParseError(f"'{skill_md}' is not a regular file.")

    try:
        content = skill_md.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise SkillParseError(
            f"Failed to read '{skill_md}' as UTF-8. "
            f"SKILL.md files must be UTF-8 encoded."
        )
    except OSError as e:
        raise SkillParseError(f"Failed to read '{skill_md}': {e}")

    return parse_frontmatter(content)


def parse_properties(skill_dir: Path) -> Skill:
    """
    解析 Skill 元数据（仅 frontmatter，不加载正文）。

    Args:
        skill_dir: Skill 目录路径

    Returns:
        Skill 实例（instructions 尚未加载，首次访问时懒加载）

    Raises:
        SkillParseError: 解析失败
    """
    frontmatter, _ = parse_skill_md(skill_dir)

    if "name" not in frontmatter:
        raise SkillParseError(
            f"Missing required field 'name' in {skill_dir}/SKILL.md frontmatter."
        )
    if "description" not in frontmatter:
        raise SkillParseError(
            f"Missing required field 'description' in {skill_dir}/SKILL.md frontmatter."
        )

    if "allowed-tools" in frontmatter:
        raw = frontmatter.pop("allowed-tools")
        if isinstance(raw, str):
            frontmatter["allowed_tools"] = raw.split()
        elif isinstance(raw, list):
            frontmatter["allowed_tools"] = raw

    frontmatter["path"] = skill_dir.resolve()

    try:
        skill = Skill(**frontmatter)
    except Exception as e:
        raise SkillParseError(
            f"Failed to create Skill from {skill_dir}/SKILL.md: {e}"
        )

    return skill


def parse_content(skill_dir: Path) -> SkillContent:
    """
    解析 Skill 完整内容（frontmatter + 正文）。

    .. deprecated::
        Prefer ``parse_properties()`` which returns a ``Skill`` with lazy
        instructions. This function is kept for backward compatibility.

    Args:
        skill_dir: Skill 目录路径

    Returns:
        SkillContent 实例
    """
    frontmatter, body = parse_skill_md(skill_dir)

    skill = parse_properties(skill_dir)

    raw_content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

    return SkillContent(
        properties=skill,
        instructions=body,
        raw_content=raw_content,
    )


def validate_skill(skill_dir: Path) -> List[str]:
    """
    校验 Skill 目录是否符合 agentskills.io 规范

    返回所有违规项列表，空列表表示通过校验。

    校验规则：
    - SKILL.md 存在且可解析
    - name: 1-64字符，kebab-case，无连续连字符
    - name 与父目录名一致
    - description: 1-1024字符
    - instructions 建议不超过 500 行
    - 文件引用路径不超过一层深度

    Args:
        skill_dir: Skill 目录路径

    Returns:
        违规描述列表，空表示全部通过
    """
    violations: List[str] = []
    skill_dir = Path(skill_dir).resolve()

    # SKILL.md 存在性
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        violations.append("SKILL.md file not found")
        return violations

    # 解析
    try:
        frontmatter, body = parse_frontmatter(
            skill_md.read_text(encoding="utf-8")
        )
    except SkillParseError as e:
        violations.append(f"Parse error: {e}")
        return violations

    # name 字段
    name = frontmatter.get("name")
    if not name:
        violations.append("Missing required field: name")
    else:
        if len(name) > 64:
            violations.append(f"name exceeds 64 characters (got {len(name)})")
        if not NAME_PATTERN.match(name):
            violations.append(
                f"name '{name}' is invalid. "
                f"Must be lowercase alphanumeric with hyphens only."
            )
        if "--" in name:
            violations.append(f"name '{name}' contains consecutive hyphens")
        if name != skill_dir.name:
            violations.append(
                f"name '{name}' does not match directory name '{skill_dir.name}'"
            )

    # description 字段
    desc = frontmatter.get("description")
    if not desc:
        violations.append("Missing required field: description")
    elif len(desc) > 1024:
        violations.append(
            f"description exceeds 1024 characters (got {len(desc)})"
        )

    # compatibility 字段
    compat = frontmatter.get("compatibility")
    if compat and len(compat) > 500:
        violations.append(
            f"compatibility exceeds 500 characters (got {len(compat)})"
        )

    # instructions 长度建议
    if body:
        line_count = body.count("\n") + 1
        if line_count > 500:
            violations.append(
                f"Instructions have {line_count} lines (recommended: < 500). "
                f"Consider moving details to references/."
            )

    return violations
