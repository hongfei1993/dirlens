"""核心逻辑单元测试：排序、格式化、目录扫描。

这些函数不依赖 Tk，可在任何环境运行；它们是整个工具的基础，
一旦出错会以"列表顺序乱、大小算错、漏文件"等形式出现在界面上。
"""
import os
from datetime import datetime

import pytest

from app import (
    format_mtime,
    format_size,
    natural_sort_key,
    path_sort_key,
    scan_directory,
)

from conftest import (
    TOP_LEVEL_DIRS,
    TOP_LEVEL_FILES,
    TREE_CONTENT,
    rel_paths,
    write_file,
)


class TestNaturalSortKey:
    def test_numeric_segments_compare_as_numbers(self):
        names = ["file10.txt", "file2.txt", "file1.txt", "file20.txt", "file3.txt"]
        assert sorted(names, key=natural_sort_key) == [
            "file1.txt", "file2.txt", "file3.txt", "file10.txt", "file20.txt",
        ]

    def test_chinese_chapter_names(self):
        names = ["第10章.pdf", "第2章.pdf", "第1章.pdf"]
        assert sorted(names, key=natural_sort_key) == [
            "第1章.pdf", "第2章.pdf", "第10章.pdf",
        ]

    def test_pure_numeric_names(self):
        assert sorted(["1.jpg", "10.jpg", "2.jpg", "100.jpg"],
                      key=natural_sort_key) == [
            "1.jpg", "2.jpg", "10.jpg", "100.jpg",
        ]

    def test_case_insensitive(self):
        assert sorted(["B.txt", "a.txt", "C.txt"], key=natural_sort_key) == [
            "a.txt", "B.txt", "C.txt",
        ]

    @pytest.mark.parametrize("value", [
        "", "a", "1", "a1", "1a", "a-1", "-1a", "...",
        "中文2文件", "A1B2", "a1b10", "  ", "a b",
    ])
    def test_edge_values_do_not_raise(self, value):
        # 只要不抛 TypeError（str 与 int 相比）即可
        assert isinstance(natural_sort_key(value), list)

    def test_mixed_comparison_is_type_stable(self):
        # 曾经的风险：同一下标位置上出现 str 与 int 相比
        names = ["1", "a", "2b", "b2", "10", "无", "x10y2", "x2y10"]
        assert sorted(names, key=natural_sort_key)


class TestPathSortKey:
    def test_stem_compared_before_extension(self):
        # 回归：直接按完整名自然排序时，"报告2.pdf" 会跑到 "报告.pdf" 前面
        assert sorted(["报告2.pdf", "报告.pdf"], key=path_sort_key) == [
            "报告.pdf", "报告2.pdf",
        ]

    def test_names_with_and_without_numbers(self):
        names = ["file10.txt", "file2.txt", "file.txt"]
        assert sorted(names, key=path_sort_key) == [
            "file.txt", "file2.txt", "file10.txt",
        ]

    def test_version_like_names(self):
        assert sorted(["v1.10", "v1.2", "v1.2.1"], key=path_sort_key) == [
            "v1.2", "v1.10", "v1.2.1",
        ]

    def test_same_stem_with_and_without_extension(self):
        # 主名相同时靠完整名兜底：无扩展名的排在带扩展名的前面
        assert sorted(["报告.pdf", "报告"], key=path_sort_key) == [
            "报告", "报告.pdf",
        ]

    def test_paths_keep_directory_order(self):
        paths = rel_paths("sub2/b.txt", "sub1/b.txt", "a.txt")
        assert sorted(paths, key=path_sort_key) == [
            "a.txt", os.path.join("sub1", "b.txt"), os.path.join("sub2", "b.txt"),
        ]


class TestFormatSize:
    @pytest.mark.parametrize("num,expected", [
        (0, "0 B"),
        (1, "1 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1024 ** 2 - 1, "1024.0 KB"),
        (1024 ** 2, "1.0 MB"),
        (5 * 1024 ** 2, "5.0 MB"),
        (1024 ** 3, "1.0 GB"),
        (1024 ** 4, "1.0 TB"),
    ])
    def test_expected_rendering(self, num, expected):
        assert format_size(num) == expected


class TestFormatMtime:
    def test_known_timestamp(self):
        stamp = datetime(2026, 10, 1, 20, 15).timestamp()
        assert format_mtime(stamp) == "2026-10-01 20:15"

    @pytest.mark.parametrize("bad", [
        float("inf"), float("-inf"), float("nan"), 1e18, -1e18,
    ])
    def test_invalid_timestamp_returns_placeholder(self, bad):
        # 时间异常时应显示占位符而不是让整个列表加载失败
        assert format_mtime(bad) == "-"


class TestScanDirectoryNonRecursive:
    def test_only_top_level_files(self, tree):
        files, _ = scan_directory(str(tree))
        assert sorted(f["name"] for f in files) == sorted(TOP_LEVEL_FILES)

    def test_top_level_dirs_collected(self, tree):
        _, dirs = scan_directory(str(tree))
        assert sorted(d["name"] for d in dirs) == sorted(TOP_LEVEL_DIRS)

    def test_dirs_are_marked(self, tree):
        _, dirs = scan_directory(str(tree))
        assert all(d["is_dir"] is True for d in dirs)

    def test_nested_files_are_not_included(self, tree):
        files, _ = scan_directory(str(tree))
        assert "报告.pdf" not in [f["name"] for f in files]

    def test_record_fields(self, tree):
        files, _ = scan_directory(str(tree))
        rec = next(f for f in files if f["name"] == "a.txt")
        assert rec["stem"] == "a"
        assert rec["ext"] == "txt"
        assert rec["size"] == 10
        assert rec["rel"] == "a.txt"
        assert os.path.isabs(rec["path"])
        assert rec["mtime"] > 0
        assert rec["is_dir"] is False

    def test_total_size_matches_payload(self, tree):
        files, _ = scan_directory(str(tree))
        assert sum(f["size"] for f in files) == 24


class TestScanDirectoryRecursive:
    def test_all_levels_listed(self, tree):
        files, _ = scan_directory(str(tree), recursive=True)
        assert sorted(f["rel"] for f in files) == sorted(rel_paths(*TREE_CONTENT))

    def test_dirs_not_collected(self, tree):
        # 递归时层级由相对路径体现，再列文件夹会把列表淹没
        _, dirs = scan_directory(str(tree), recursive=True)
        assert dirs == []

    def test_same_name_in_different_levels_kept_apart(self, tree):
        files, _ = scan_directory(str(tree), recursive=True)
        names = sorted(f["name"] for f in files if f["name"] == "a.txt")
        assert names == ["a.txt", "a.txt"]
        rels = sorted(f["rel"] for f in files if f["name"] == "a.txt")
        assert rels == ["a.txt", rel_paths("sub1/deep/a.txt")[0]]

    def test_total_size_covers_whole_tree(self, tree):
        files, _ = scan_directory(str(tree), recursive=True)
        assert sum(f["size"] for f in files) == sum(TREE_CONTENT.values())

    def test_traversal_order_is_reproducible(self, tmp_path):
        for name in ["c", "a", "b"]:
            write_file(tmp_path, "%s/f.txt" % name, 1)
        first = [f["rel"] for f in scan_directory(str(tmp_path), recursive=True)[0]]
        second = [f["rel"] for f in scan_directory(str(tmp_path), recursive=True)[0]]
        assert first == second


class TestScanDirectoryEdgeCases:
    def test_extension_lowercased_and_missing_extension_empty(self, tmp_path):
        write_file(tmp_path, "UPPER.TXT", 1)
        write_file(tmp_path, "MiXeD.JpG", 1)
        write_file(tmp_path, "README", 1)
        files, _ = scan_directory(str(tmp_path))
        by_name = {f["name"]: f["ext"] for f in files}
        assert by_name == {"UPPER.TXT": "txt", "MiXeD.JpG": "jpg", "README": ""}

    def test_missing_directory_returns_empty(self, tmp_path):
        files, dirs = scan_directory(str(tmp_path / "并不存在"))
        assert files == [] and dirs == []

    def test_path_pointing_to_a_file_returns_empty(self, tmp_path):
        target = write_file(tmp_path, "a.txt", 1)
        files, dirs = scan_directory(str(target))
        assert files == [] and dirs == []

    def test_empty_directory(self, tmp_path):
        files, dirs = scan_directory(str(tmp_path))
        assert files == [] and dirs == []

    def test_empty_file_has_zero_size(self, tmp_path):
        write_file(tmp_path, "empty.bin", 0)
        files, _ = scan_directory(str(tmp_path))
        assert files[0]["size"] == 0

    def test_chinese_names_survive(self, tree):
        files, dirs = scan_directory(str(tree), recursive=True)
        assert "报告.pdf" in [f["name"] for f in files]
        files_top, dirs_top = scan_directory(str(tree))
        assert "中文子目录" in [d["name"] for d in dirs_top]
