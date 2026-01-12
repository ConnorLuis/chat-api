import sys
from pathlib import Path

# 将项目根目录手动添加到 Python 的模块搜索路径（sys.path）中，解决测试文件（tests/ 目录下）无法直接导入项目源代码（src/ 目录下）的问题
"""
chat-api/          # 项目根目录（我们要添加到sys.path的目录）
├── src/           # 源代码目录
└── tests/         # 测试目录
    └── test_chat_mock.py  # 这段代码所在的测试文件
"""
# __file__是当前执行脚本文件路径，转换为Path对象，解析为绝对路径，获取当前路径的第一级父目录
ROOT = Path(__file__).resolve().parents[1]
# 将项目根目录加入搜索路径
sys.path.insert(0, str(ROOT))