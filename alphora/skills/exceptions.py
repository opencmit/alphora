# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Skills 组件异常定义

所有 Skill 相关异常均继承自 SkillError，方便统一捕获。

异常层级：
    SkillError
    ├── SkillParseError          # SKILL.md 解析失败
    ├── SkillValidationError     # Skill 格式校验不通过
    ├── SkillNotFoundError       # 指定名称的 Skill 不存在
    ├── SkillLoadError           # Skill 加载失败
    └── SkillResourceError       # 资源文件访问失败
"""


class SkillError(Exception):
    """Skills 模块基础异常"""
    pass


class SkillParseError(SkillError):
    """SKILL.md 文件解析失败

    常见原因：
    - YAML frontmatter 格式错误
    - 缺少必需字段 (name, description)
    - 文件编码问题
    """
    pass


class SkillValidationError(SkillError):
    """Skill 格式校验不通过

    校验规则遵循 agentskills.io 规范：
    - name: 1-64 字符，仅小写字母、数字、连字符
    - description: 1-1024 字符，非空
    - name 须与父目录名一致
    """

    def __init__(self, skill_name: str, violations: list[str]):
        self.skill_name = skill_name
        self.violations = violations
        detail = "; ".join(violations)
        super().__init__(f"Skill '{skill_name}' validation failed: {detail}")


class SkillNotFoundError(SkillError):
    """指定名称的 Skill 不存在

    当 activate() 或 get_skill() 找不到对应 Skill 时抛出。
    会尝试提供相似名称建议。
    """

    def __init__(self, skill_name: str, available: list[str] | None = None):
        self.skill_name = skill_name
        self.available = available or []

        msg = f"Skill '{skill_name}' not found."
        if self.available:
            from difflib import get_close_matches
            similar = get_close_matches(skill_name, self.available, n=3, cutoff=0.4)
            if similar:
                msg += f" Did you mean: {', '.join(similar)}?"
            else:
                msg += f" Available skills: {', '.join(self.available)}"

        super().__init__(msg)


class SkillLoadError(SkillError):
    """Skill 加载失败

    常见原因：
    - SKILL.md 文件被删除或损坏
    - 文件权限不足
    - 内容超出建议大小限制
    """
    pass


# deprecated alias
SkillActivationError = SkillLoadError


class SkillResourceError(SkillError):
    """Skill 资源文件访问失败

    常见原因：
    - 资源文件不存在
    - 路径遍历攻击检测（路径逃逸出 Skill 目录）
    - 文件过大
    """
    pass
