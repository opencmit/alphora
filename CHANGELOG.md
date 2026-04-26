# ChangeLog

## [1.2.9] - 2026-04-23
### Fixed
- 新增公开 processor ensure_tool_call_integrity，修复了Agent中可能出现的找不到父 assistant 的孤儿 tool 情况；(alphora/memory/processor.py)

### Update
- 新增 Hook - MessageInspector 的对话导出功能


## [1.3.0] - 2026-04-24
### Update
- 重写 OpenAILike 类，优化了可拓展性和鲁棒性
- 新增DeepSeek-V4适配
- 新增Qwen适配


