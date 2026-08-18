class ConversationNotFoundError(LookupError):
    """目标 Conversation 不存在."""


class MessageNotFoundError(LookupError):
    """目标 Message 不存在."""


class InvalidMessageRoleError(ValueError):
    """Message role 不在允许集合中."""
