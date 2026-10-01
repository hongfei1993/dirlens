"""pytest 共享配置与夹具。

放在 tests/ 下并显式把仓库根目录加进 sys.path：pytest 默认只把测试文件
所在目录加入搜索路径，这样 `from app import ...` 才能找到根目录的 app.py。
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def write_file(root, relative_path, size):
    """按 POSIX 风格相对路径写文件，自动创建中间目录。

    统一用 "/" 分隔再由 pathlib 转换，避免测试里出现平台相关的分隔符写法。
    """
    path = root.joinpath(*relative_path.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def rel_paths(*posix_paths):
    """把 POSIX 风格路径转成本平台形式，便于与 scan_directory 的 rel 比较。"""
    return [os.path.join(*p.split("/")) for p in posix_paths]


#: 标准测试目录树：POSIX 相对路径 -> 字节数
TREE_CONTENT = {
    "a.txt": 10,
    "z.txt": 11,
    "无扩展名": 3,
    "sub1/b.txt": 20,
    "sub1/file2.txt": 21,
    "sub1/file10.txt": 22,
    "sub1/deep/c.txt": 30,
    "sub1/deep/a.txt": 40,
    "中文子目录/报告.pdf": 50,
}

#: 上述目录树中位于根目录下的文件与文件夹
TOP_LEVEL_FILES = ["a.txt", "z.txt", "无扩展名"]
TOP_LEVEL_DIRS = ["sub1", "中文子目录"]

#: 根目录下所有文件的字节数合计
TOP_LEVEL_TOTAL_SIZE = 24


@pytest.fixture
def tree(tmp_path):
    """构造一棵固定的测试目录树，返回根路径（pathlib.Path）。"""
    for rel, size in TREE_CONTENT.items():
        write_file(tmp_path, rel, size)
    return tmp_path
