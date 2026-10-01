"""界面集成测试：真实创建 Tk 窗口（移到屏幕外），跑完整流程后断言结果。

单元测试只验证单个函数；桌面程序最常见的故障恰恰是"每个函数都对、
组合起来不对"（例如状态栏被挤掉、排序键与显示的列不一致）。
所以这一层必须真的把窗口建出来、真的走一遍用户操作。
"""
import tkinter as tk
from tkinter import ttk

import pytest

from app import OUTPUT_FORMATS, FileListViewer

from conftest import TREE_CONTENT, rel_paths, write_file

# 整份文件都依赖 Tk；无图形环境时可用 `pytest -m "not gui"` 跳过
pytestmark = pytest.mark.gui


@pytest.fixture
def make_app():
    """返回一个工厂：给定目录，创建并加载好列表的界面对象。

    窗口被移到屏幕外（+9000+9000）并在用例结束时销毁，尽量不干扰使用者。
    """
    roots = []

    def _make(directory):
        try:
            root = tk.Tk()
        except tk.TclError as exc:  # 无图形环境（如无显示的 CI）时跳过
            pytest.skip("当前环境无法初始化 Tk：%s" % exc)
        root.geometry("+9000+9000")
        roots.append(root)

        viewer = FileListViewer(root)
        viewer.directory_var.set(str(directory))
        viewer._load_file_list(str(directory))
        root.update_idletasks()
        return viewer, root

    yield _make

    for root in roots:
        try:
            root.destroy()
        except tk.TclError:
            pass


def visible(viewer):
    """表格当前第一列的可见内容"""
    return [viewer.tree.item(iid, "values")[0]
            for iid in viewer.tree.get_children()]


def all_cells(viewer):
    """表格全部单元格"""
    return [viewer.tree.item(iid, "values")
            for iid in viewer.tree.get_children()]


def is_empty_placeholder(viewer):
    rows = visible(viewer)
    return len(rows) == 1 and "没有符合条件" in rows[0]


class TestListing:
    def test_default_shows_top_level_names_only(self, make_app, tree):
        viewer, _ = make_app(tree)
        assert list(viewer.tree["columns"]) == ["name"]
        assert viewer.tree.heading("name")["text"] == "文件名"
        assert visible(viewer) == ["a.txt", "z.txt", "无扩展名"]

    def test_files_sorted_naturally(self, make_app, tmp_path):
        for name in ["file10.txt", "file2.txt", "file1.txt"]:
            write_file(tmp_path, name, 1)
        viewer, _ = make_app(tmp_path)
        assert visible(viewer) == ["file1.txt", "file2.txt", "file10.txt"]

    def test_status_bar_reports_files_and_total_size(self, make_app, tree):
        viewer, _ = make_app(tree)
        assert viewer.status_var.get() == "找到 3 个项目（文件 3 个，合计 24 B）"

    def test_status_bar_reports_filtered_count(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer.filter_vars["txt"].set(True)
        viewer._on_filter_changed()
        assert "过滤后显示 2 个" in viewer.status_var.get()

    def test_window_title_carries_brand(self, make_app, tree):
        _, root = make_app(tree)
        assert root.title() == "DirLens · 文件列表查看器"


class TestFieldColumns:
    def test_enabling_fields_adds_columns_in_order(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer.col_path_var.set(True)
        viewer.col_size_var.set(True)
        viewer.col_mtime_var.set(True)
        viewer._redraw_list()

        assert list(viewer.tree["columns"]) == ["name", "path", "size", "mtime"]
        assert [viewer.tree.heading(c)["text"] for c in viewer.tree["columns"]] == [
            "文件名", "完整路径", "大小", "修改时间",
        ]

    def test_output_follows_columns_with_tabs(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer.col_path_var.set(True)
        viewer.col_size_var.set(True)
        viewer._redraw_list()

        line = viewer._output_lines(viewer._get_items_to_display())[0]
        fields = line.split("\t")
        assert fields[0] == "a.txt"
        assert fields[1] == str(tree / "a.txt")
        assert fields[2] == "10 B"

    def test_disabling_fields_restores_plain_names(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer.col_size_var.set(True)
        viewer._redraw_list()
        assert "\t" in viewer._output_lines(viewer._get_items_to_display())[0]

        viewer.col_size_var.set(False)
        viewer._redraw_list()
        assert viewer._output_lines(viewer._get_items_to_display()) == [
            "a.txt", "z.txt", "无扩展名",
        ]

    def test_folder_size_shows_dash_not_zero(self, make_app, tree):
        # Windows 上目录 st_size 恒为 0，显示 "0 B" 会误导成空文件夹
        viewer, _ = make_app(tree)
        viewer.folders_var.set(True)
        viewer._toggle_folders()
        viewer.col_size_var.set(True)
        viewer._redraw_list()

        cells = {row[0]: row[1] for row in all_cells(viewer)}
        assert cells["sub1"] == "-"
        assert cells["中文子目录"] == "-"
        assert cells["a.txt"] == "10 B"

    def test_folders_listed_before_files(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer.folders_var.set(True)
        viewer._toggle_folders()
        assert visible(viewer) == [
            "sub1", "中文子目录", "a.txt", "z.txt", "无扩展名",
        ]


class TestFiltering:
    def test_type_menu_built_from_actual_extensions(self, make_app, tree):
        viewer, _ = make_app(tree)
        assert sorted(viewer.filter_vars) == ["", "txt"]
        assert viewer.filter_btn.cget("text") == "所有文件"

    def test_single_type_filter(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer.filter_vars["txt"].set(True)
        viewer._on_filter_changed()
        assert viewer.filter_btn.cget("text") == "txt"
        assert visible(viewer) == ["a.txt", "z.txt"]

    def test_select_all_covers_extensionless_files(self, make_app, tree):
        # 回归：README / LICENSE 这类无扩展名文件曾不在任何类型里，
        # 「全选」反而会少几行
        viewer, _ = make_app(tree)
        viewer._set_all_extensions(True)
        assert viewer.filter_btn.cget("text") == "已选 2 种"
        assert visible(viewer) == ["a.txt", "z.txt", "无扩展名"]

    def test_extensionless_can_be_selected_alone(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer._set_all_extensions(False)
        viewer.filter_vars[""].set(True)
        viewer._on_filter_changed()
        assert visible(viewer) == ["无扩展名"]

    def test_clear_all_shows_everything(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer._set_all_extensions(True)
        viewer._set_all_extensions(False)
        assert viewer.filter_btn.cget("text") == "所有文件"
        assert visible(viewer) == ["a.txt", "z.txt", "无扩展名"]

    def test_multi_select_across_case(self, make_app, tmp_path):
        write_file(tmp_path, "图片1.jpg", 1)
        write_file(tmp_path, "图片2.png", 1)
        write_file(tmp_path, "Photo.JPG", 1)
        write_file(tmp_path, "note.txt", 1)
        viewer, _ = make_app(tmp_path)

        viewer.filter_vars["jpg"].set(True)
        viewer.filter_vars["png"].set(True)
        viewer._on_filter_changed()
        assert sorted(visible(viewer)) == ["Photo.JPG", "图片1.jpg", "图片2.png"]

    def test_keyword_filter_is_case_insensitive(self, make_app, tmp_path):
        write_file(tmp_path, "Photo.JPG", 1)
        write_file(tmp_path, "note.txt", 1)
        viewer, _ = make_app(tmp_path)
        viewer.keyword_var.set("photo")
        viewer._redraw_list()
        assert visible(viewer) == ["Photo.JPG"]

    def test_keyword_and_type_are_and_ed(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer.keyword_var.set("a")
        viewer.filter_vars["txt"].set(True)
        viewer._on_filter_changed()
        assert visible(viewer) == ["a.txt"]

        viewer.keyword_var.set("报告")
        viewer._redraw_list()
        assert is_empty_placeholder(viewer)

    def test_empty_result_shows_placeholder(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer.keyword_var.set("绝不可能匹配到的关键词")
        viewer._redraw_list()
        assert is_empty_placeholder(viewer)


class TestRecursive:
    def test_all_levels_listed_and_header_renamed(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer.recursive_var.set(True)
        viewer._toggle_recursive()

        assert viewer.tree.heading("name")["text"] == "相对路径"
        assert sorted(visible(viewer)) == sorted(rel_paths(*TREE_CONTENT))

    def test_no_folders_listed(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer.recursive_var.set(True)
        viewer._toggle_recursive()
        assert "sub1" not in visible(viewer)

    def test_order_follows_relative_path(self, make_app, tmp_path):
        for rel in [
            "a.txt", "z.txt", "sub1/b.txt",
            "sub1/file2.txt", "sub1/file10.txt", "sub1/deep/c.txt",
            "sub2/b.txt", "中文子目录/报告.pdf",
        ]:
            write_file(tmp_path, rel, 1)
        viewer, _ = make_app(tmp_path)
        viewer.recursive_var.set(True)
        viewer._toggle_recursive()

        assert visible(viewer) == rel_paths(
            "a.txt",
            "sub1/b.txt", "sub1/deep/c.txt",
            "sub1/file2.txt", "sub1/file10.txt",
            "sub2/b.txt", "z.txt",
            "中文子目录/报告.pdf",
        )

    def test_show_folders_disabled_and_cleared(self, make_app, tree):
        viewer, _ = make_app(tree)
        viewer.folders_var.set(True)
        viewer._toggle_folders()

        viewer.recursive_var.set(True)
        viewer._toggle_recursive()
        assert viewer.folders_var.get() is False
        assert "disabled" in viewer.folders_check.state()

        viewer.recursive_var.set(False)
        viewer._toggle_recursive()
        assert "disabled" not in viewer.folders_check.state()
        assert viewer.tree.heading("name")["text"] == "文件名"

    def test_type_menu_picks_up_nested_extensions(self, make_app, tree):
        viewer, _ = make_app(tree)
        assert "pdf" not in viewer.filter_vars

        viewer.recursive_var.set(True)
        viewer._toggle_recursive()
        assert "pdf" in viewer.filter_vars


class TestSortOrder:
    def test_descending_is_exact_reverse(self, make_app, tree):
        viewer, _ = make_app(tree)
        ascending = visible(viewer)
        viewer.sort_var.set("降序")
        viewer._redraw_list()
        assert visible(viewer) == ascending[::-1]

    def test_stem_before_extension(self, make_app, tmp_path):
        write_file(tmp_path, "报告2.pdf", 1)
        write_file(tmp_path, "报告.pdf", 1)
        viewer, _ = make_app(tmp_path)
        assert visible(viewer) == ["报告.pdf", "报告2.pdf"]


class TestCopyFormats:
    def test_all_formats(self, make_app, tree):
        viewer, _ = make_app(tree)
        records = viewer._get_items_to_display()

        viewer.copy_format_var.set("仅文件名")
        assert viewer._output_lines(records) == ["a.txt", "z.txt", "无扩展名"]

        viewer.copy_format_var.set("完整路径")
        assert viewer._output_lines(records) == [
            str(tree / "a.txt"), str(tree / "z.txt"), str(tree / "无扩展名"),
        ]

        viewer.copy_format_var.set("完整路径（带引号）")
        assert viewer._output_lines(records) == [
            '"%s"' % (tree / "a.txt"), '"%s"' % (tree / "z.txt"),
            '"%s"' % (tree / "无扩展名"),
        ]

        viewer.copy_format_var.set("逗号分隔")
        assert viewer._output_lines(records) == ["a.txt, z.txt, 无扩展名"]

        viewer.copy_format_var.set("跟随列表")
        assert viewer._output_lines(records) == ["a.txt", "z.txt", "无扩展名"]

    def test_default_format_follows_the_list(self, make_app, tree):
        viewer, _ = make_app(tree)
        assert viewer.copy_format_var.get() == OUTPUT_FORMATS[0]
        assert OUTPUT_FORMATS[0] == "跟随列表"

    def test_quoting_survives_spaces(self, make_app, tmp_path):
        write_file(tmp_path, "带 空格 的名字.txt", 1)
        viewer, _ = make_app(tmp_path)
        viewer.copy_format_var.set("完整路径（带引号）")
        line = viewer._output_lines(viewer._get_items_to_display())[0]
        assert line.startswith('"') and line.endswith('"')
        assert "带 空格 的名字.txt" in line


class TestDirectoryInput:
    def test_current_directory_reads_entry_not_cached_state(self, make_app, tree):
        # 回归 A1：手工在输入框粘贴路径后，列表能加载但复制/导出曾被误拦
        viewer, _ = make_app(tree)
        viewer.directory_var.set(str(tree / "sub1"))
        assert viewer._get_current_directory() == str(tree / "sub1")

        viewer.directory_var.set(str(tree / "并不存在的目录"))
        assert viewer._get_current_directory() is None

    def test_manually_typed_path_loads_and_stays_usable(self, make_app, tree):
        viewer, _ = make_app(tree)
        target = tree / "sub1"
        viewer.directory_var.set(str(target))
        viewer._refresh_file_list()

        assert visible(viewer) == ["b.txt", "file2.txt", "file10.txt"]
        assert viewer._get_current_directory() == str(target)


class TestLayout:
    def test_status_bar_is_not_squeezed_out(self, make_app, tree):
        # 回归：列表区带 expand=True，状态栏若最后 pack 会被压成 0 高度
        viewer, root = make_app(tree)
        root.geometry("1000x600")
        root.update_idletasks()

        labels = [c for c in viewer.main_frame.winfo_children()
                  if isinstance(c, ttk.Label)]
        status = [c for c in labels
                  if str(c.cget("textvariable")) == str(viewer.status_var)]
        assert status, "未找到状态栏控件"
        assert status[0].winfo_height() > 5, "状态栏被挤成 0 高度"

    def test_status_bar_survives_small_window(self, make_app, tree):
        viewer, root = make_app(tree)
        root.geometry("900x520")
        root.update_idletasks()
        labels = [c for c in viewer.main_frame.winfo_children()
                  if isinstance(c, ttk.Label)]
        status = [c for c in labels
                  if str(c.cget("textvariable")) == str(viewer.status_var)]
        assert status and status[0].winfo_height() > 5
