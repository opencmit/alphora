from enum import Enum


class HookEvent(str, Enum):
    TOOLS_BEFORE_EXECUTE = "tools.before_execute"
    TOOLS_AFTER_EXECUTE = "tools.after_execute"
    TOOLS_ON_ERROR = "tools.on_error"

    TOOLS_BEFORE_REGISTER = "tools.before_register"
    TOOLS_AFTER_REGISTER = "tools.after_register"

    MEMORY_BEFORE_ADD = "memory.before_add"
    MEMORY_AFTER_ADD = "memory.after_add"
    MEMORY_BEFORE_BUILD_HISTORY = "memory.before_build_history"
    MEMORY_AFTER_BUILD_HISTORY = "memory.after_build_history"

    PROMPTER_BEFORE_BUILD_MESSAGES = "prompter.before_build_messages"
    PROMPTER_AFTER_BUILD_MESSAGES = "prompter.after_build_messages"
    LLM_BEFORE_CALL = "llm.before_call"
    LLM_AFTER_CALL = "llm.after_call"
    LLM_ON_STREAM_CHUNK = "llm.on_stream_chunk"

    SANDBOX_BEFORE_START = "sandbox.before_start"
    SANDBOX_AFTER_START = "sandbox.after_start"
    SANDBOX_BEFORE_STOP = "sandbox.before_stop"
    SANDBOX_AFTER_STOP = "sandbox.after_stop"
    SANDBOX_BEFORE_EXECUTE = "sandbox.before_execute"
    SANDBOX_AFTER_EXECUTE = "sandbox.after_execute"
    SANDBOX_BEFORE_WRITE_FILE = "sandbox.before_write_file"
    SANDBOX_AFTER_WRITE_FILE = "sandbox.after_write_file"

    AGENT_BEFORE_RUN = "agent.before_run"
    AGENT_AFTER_RUN = "agent.after_run"
    AGENT_BEFORE_ITERATION = "agent.before_iteration"
    AGENT_AFTER_ITERATION = "agent.after_iteration"
