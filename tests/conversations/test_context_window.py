from dataclasses import dataclass

from src.app.conversations import (
    build_context_window,
)


@dataclass(frozen=True)
class Message:
    role: str
    content: str


def test_context_keeps_recent_turns():
    history = [
        Message("user", "u1"),
        Message("assistant", "a1"),
        Message("user", "u2"),
        Message("assistant", "a2"),
        Message("user", "u3"),
        Message("assistant", "a3"),
    ]

    result = build_context_window(
        history=history,
        current=[
            Message("user", "u4"),
        ],
        system_text=None,
        max_turns=2,
        token_budget=1000,
    )

    assert [
        (message.role, message.content)
        for message in result.messages
    ] == [
        ("user", "u2"),
        ("assistant", "a2"),
        ("user", "u3"),
        ("assistant", "a3"),
        ("user", "u4"),
    ]

    assert result.history_messages == 4
    assert result.current_messages == 1
    assert result.truncated is True


def test_context_respects_token_budget():
    history = [
        Message("user", "A" * 20),
        Message("assistant", "B" * 20),
        Message("user", "C" * 20),
        Message("assistant", "D" * 20),
    ]

    result = build_context_window(
        history=history,
        current=[
            Message("user", "current"),
        ],
        system_text=None,
        max_turns=10,
        token_budget=36,
    )

    assert [
        message.content
        for message in result.messages
    ] == [
        "C" * 20,
        "D" * 20,
        "current",
    ]

    assert result.estimated_tokens == 36
    assert result.truncated is True


def test_current_request_is_always_kept():
    result = build_context_window(
        history=[
            Message("user", "old"),
            Message("assistant", "answer"),
        ],
        current=[
            Message(
                "user",
                "X" * 1000,
            ),
        ],
        system_text="system",
        max_turns=10,
        token_budget=10,
    )

    assert len(result.messages) == 1
    assert result.messages[0].content == (
        "X" * 1000
    )
    assert result.history_messages == 0
    assert result.truncated is True


def test_leading_system_message_is_preserved():
    result = build_context_window(
        history=[
            Message("system", "persistent rule"),
            Message("user", "old question"),
            Message("assistant", "old answer"),
        ],
        current=[
            Message("user", "new question"),
        ],
        system_text=None,
        max_turns=1,
        token_budget=1000,
    )

    assert [
        message.role
        for message in result.messages
    ] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
