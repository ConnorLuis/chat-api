class ChatProviderError(RuntimeError):
    """Provider 层异常基类。"""


class UnsupportedProviderError(ChatProviderError):
    """请求了未支持的 Provider。"""


class ProviderDependencyError(ChatProviderError):
    """Provider 所需可选依赖未安装。"""


class ProviderConfigurationError(ChatProviderError):
    """Provider 配置缺失或无效。"""
