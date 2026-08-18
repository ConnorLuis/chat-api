from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
from typing import Protocol


class MessageLike(Protocol):
    role: str
    content: str


@dataclass(
    frozen=True,
    slots=True,
)
class ContextMessage:
    role: str
    content: str


@dataclass(
    frozen=True,
    slots=True,
)
class ContextWindowResult:
    messages: tuple[ContextMessage, ...]
    history_messages: int
    current_messages: int
    truncated: bool
    estimated_tokens: int


def estimate_text_tokens(
    text: str,
) -> int:
    """中文优先的保守近似 token 估算."""

    return max(
        1,
        ceil(len(text) / 2),
    )


def estimate_message_tokens(
    message: MessageLike,
) -> int:
    # 近似计算 role / message framing overhead。
    return (
        estimate_text_tokens(message.content)
        + 4
    )


def _to_context_message(
    message: MessageLike,
) -> ContextMessage:
    return ContextMessage(
        role=str(message.role),
        content=str(message.content),
    )


def _split_history(
    history: Sequence[ContextMessage],
) -> tuple[
    list[ContextMessage],
    list[list[ContextMessage]],
]:
    """拆分会话前缀和 user-led turns."""

    prefix: list[ContextMessage] = []
    turns: list[list[ContextMessage]] = []
    active_turn: list[ContextMessage] | None = None

    for message in history:
        if message.role == "user":
            if active_turn is not None:
                turns.append(active_turn)

            active_turn = [message]
            continue

        if active_turn is None:
            prefix.append(message)
        else:
            active_turn.append(message)

    if active_turn is not None:
        turns.append(active_turn)

    return prefix, turns


def build_context_window(
    *,
    history: Sequence[MessageLike],
    current: Sequence[MessageLike],
    system_text: str | None,
    max_turns: int,
    token_budget: int,
) -> ContextWindowResult:
    """选择最近历史，同时始终保留当前请求."""

    if max_turns < 0:
        raise ValueError(
            "max_turns must be greater than "
            "or equal to 0"
        )

    if token_budget < 1:
        raise ValueError(
            "token_budget must be greater than 0"
        )

    history_messages = [
        _to_context_message(message)
        for message in history
    ]

    current_messages = [
        _to_context_message(message)
        for message in current
    ]

    reserved_tokens = sum(
        estimate_message_tokens(message)
        for message in current_messages
    )

    if system_text:
        reserved_tokens += (
            estimate_text_tokens(system_text)
            + 4
        )

    available = max(
        0,
        token_budget - reserved_tokens,
    )

    prefix, turns = _split_history(
        history_messages
    )

    if max_turns == 0:
        turns = []
    else:
        turns = turns[-max_turns:]

    selected_prefix: list[
        ContextMessage
    ] = []

    prefix_cost = sum(
        estimate_message_tokens(message)
        for message in prefix
    )

    if prefix and prefix_cost <= available:
        selected_prefix = prefix
        available -= prefix_cost

    selected_turns_reversed: list[
        list[ContextMessage]
    ] = []

    for turn in reversed(turns):
        turn_cost = sum(
            estimate_message_tokens(message)
            for message in turn
        )

        # 保持最近历史连续；最新一轮都放不下时，
        # 不跳过去选择更老但更短的轮次。
        if turn_cost > available:
            break

        selected_turns_reversed.append(
            turn
        )
        available -= turn_cost

    selected_turns: list[
        list[ContextMessage]
    ] = list(
        reversed(
            selected_turns_reversed
        )
    )

    selected_history = [
        *selected_prefix,
        *[
            message
            for turn in selected_turns
            for message in turn
        ],
    ]

    final_messages = (
        selected_history
        + current_messages
    )

    estimated_tokens = (
        reserved_tokens
        + sum(
            estimate_message_tokens(message)
            for message in selected_history
        )
    )

    return ContextWindowResult(
        messages=tuple(final_messages),
        history_messages=len(
            selected_history
        ),
        current_messages=len(
            current_messages
        ),
        truncated=(
            len(selected_history)
            < len(history_messages)
        ),
        estimated_tokens=estimated_tokens,
    )
