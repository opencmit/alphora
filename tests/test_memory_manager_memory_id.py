"""MemoryManager: memory_id 与弃用的 session_id 行为。"""

import warnings

import pytest

from alphora.memory import MemoryManager


def test_add_user_memory_id_no_warning() -> None:
    m = MemoryManager()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", category=DeprecationWarning)
        m.add_user("hi", memory_id="slot_a")
        assert len(w) == 0
    assert m.get_messages("slot_a")[0].content == "hi"


def test_add_user_session_id_emits_deprecation() -> None:
    m = MemoryManager()
    with pytest.warns(DeprecationWarning, match="session_id"):
        m.add_user("x", session_id="legacy")


def test_build_history_session_id_keyword_deprecated() -> None:
    m = MemoryManager()
    m.add_user("u", memory_id="z")
    with pytest.warns(DeprecationWarning, match="session_id"):
        h = m.build_history(session_id="z", max_rounds=1)
    assert h.message_count >= 1


def test_conflicting_memory_id_and_session_id_raises() -> None:
    m = MemoryManager()
    with pytest.raises(TypeError, match="冲突"):
        m.add_user("x", memory_id="a", session_id="b")


def test_has_session_session_id_deprecated() -> None:
    m = MemoryManager()
    m.add_user("u", memory_id="k")
    with pytest.warns(DeprecationWarning, match="session_id"):
        assert m.has_session(session_id="k") is True


def test_is_empty_memory_id_and_session_id_deprecated() -> None:
    m = MemoryManager()
    assert m.is_empty(memory_id="empty_slot") is True

    m.add_user("u", memory_id="k")
    assert m.is_empty(memory_id="k") is False

    with pytest.warns(DeprecationWarning, match="session_id"):
        assert m.is_empty(session_id="empty_slot") is True


def test_delete_session_positional_only() -> None:
    m = MemoryManager()
    m.add_user("u", memory_id="to_del")
    assert m.delete_session("to_del") is True


def test_add_tool_result_session_id_deprecated() -> None:
    m = MemoryManager()
    m.add_user("q", memory_id="t1")
    with pytest.warns(DeprecationWarning, match="session_id"):
        m.add_tool_result(
            tool_call_id="c1",
            name="n",
            content="{}",
            session_id="t1",
        )


def test_merge_memory_appends_from_other_manager() -> None:
    a = MemoryManager()
    b = MemoryManager()

    a.add_user("a1", memory_id="target")
    b.add_user("b1", memory_id="source")
    b.add_assistant("b2", memory_id="source")

    merged = a.merge_memory(
        other_memory=b,
        source_memory_id="source",
        other_memory_id="target",
    )

    assert merged == 2
    assert [m.content for m in a.get_messages("target")] == ["a1", "b1", "b2"]
    assert [m.content for m in b.get_messages("source")] == ["b1", "b2"]


def test_merge_memory_creates_target_if_missing() -> None:
    a = MemoryManager()
    b = MemoryManager()

    b.add_user("b1", memory_id="source")

    merged = a.merge_memory(
        other_memory=b,
        source_memory_id="source",
        other_memory_id="new_target",
    )

    assert merged == 1
    assert [m.content for m in a.get_messages("new_target")] == ["b1"]


def test_merge_memory_returns_zero_for_missing_source() -> None:
    a = MemoryManager()
    b = MemoryManager()
    a.add_user("a1", memory_id="target")

    merged = a.merge_memory(
        other_memory=b,
        source_memory_id="missing",
        other_memory_id="target",
    )

    assert merged == 0
    assert [m.content for m in a.get_messages("target")] == ["a1"]
