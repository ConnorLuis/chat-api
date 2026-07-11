class APIKeyError(Exception):
    """API key 领域错误基类."""


class APIKeyConfigurationError(
    APIKeyError
):
    """API key 服务端配置不完整."""


class InvalidAPIKeyError(
    APIKeyError
):
    """密钥格式错误、未知或签名不匹配."""


class RevokedAPIKeyError(
    APIKeyError
):
    """密钥已经吊销."""


class APIKeyNotFoundError(
    APIKeyError
):
    """API key id 不存在."""


class InvalidAPIKeyNameError(
    APIKeyError
):
    """API key name 不合法."""
