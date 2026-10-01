import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
import sys
from datetime import datetime

import pyperclip


def natural_sort_key(text):
    """自然排序键：把字符串中的数字段按数值比较，使 file2 排在 file10 之前。

    re.split 保留捕获组后，结果中非数字段与数字段的位置是固定的（下标奇偶性不变），
    因此同一位置上比较的两个元素类型始终一致，不会出现 str 与 int 相比的报错。
    """
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r'(\d+)', text)]


COLUMN_META = {
    "name":  ("文件名",   320, "w", True),
    "path":  ("完整路径", 380, "w", True),
    "size":  ("大小",      90, "e", False),
    "mtime": ("修改时间", 140, "w", False),
}

# 「复制格式」可选值。首项为默认：输出与表格当前显示的列完全一致
OUTPUT_FORMATS = ("跟随列表", "仅文件名", "完整路径", "完整路径（带引号）", "逗号分隔")

_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB")


def path_sort_key(value):
    """文件路径 / 文件名的排序键。

    先按「去掉扩展名后的自然顺序」比，再用完整名兜底。之所以要剥掉扩展名：
    直接对完整名做自然排序会出现反直觉的结果 —— '报告.pdf' 整体是不含数字的
    一段，而 '报告2.pdf' 会拆成 ['报告', 2, '.pdf']，比较时 '报告' 是
    '报告.pdf' 的前缀，于是 '报告2.pdf' 反而排在前面。资源管理器的行为是
    '报告.pdf' 在前，剥掉扩展名即可对齐。
    """
    stem, _ = os.path.splitext(value)
    return (natural_sort_key(stem), natural_sort_key(value))


def format_size(num):
    """把字节数转成人类可读形式，例如 1536 -> '1.5 KB'"""
    if num < 1024:
        return f"{num} B"
    value = float(num)
    for unit in _SIZE_UNITS[1:]:
        value /= 1024.0
        if value < 1024.0:
            return f"{value:.1f} {unit}"
    return f"{value:.1f} {_SIZE_UNITS[-1]}"


def format_mtime(timestamp):
    """把时间戳转成本地时间的可读字符串；时间异常时返回占位符而不是抛异常"""
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return "-"


def scan_directory(directory, recursive=False):
    """扫描目录，返回 (文件记录列表, 文件夹记录列表)。

    recursive=True 时遍历所有层级；此时**不收集文件夹**——深层文件夹会把列表
    淹没，而每个文件在树中的位置已由 rel（相对路径）体现。

    用 os.scandir 而不是 os.listdir：Windows 上 is_file()/is_dir() 直接取自
    目录项缓存，比 listdir + os.path.isfile 少一轮系统调用；且 entry.stat()
    能一次拿到大小与修改时间，避免后续为每个文件重复 stat。

    每条记录的结构：
        name   文件名（含扩展名）
        stem   主名（不含扩展名）
        ext    扩展名（小写、无点号，无扩展名时为空串）
        path   绝对/完整路径
        rel    相对所选根目录的路径（递归时用于区分不同层级的同名文件）
        size   字节数
        mtime  修改时间戳
    """
    files, dirs = [], []

    def build(entry):
        """把一条目录项转成记录；失败时返回 None 而不是抛异常"""
        try:
            st = entry.stat()
            name = entry.name
            stem, ext = os.path.splitext(name)
            return {
                "name": name,
                "stem": stem,
                "ext": ext[1:].lower(),
                "path": entry.path,
                "rel": os.path.relpath(entry.path, directory),
                "size": st.st_size,
                "mtime": st.st_mtime,
                "is_dir": entry.is_dir(),
            }
        except OSError:
            # 权限不足、文件被占用或扫描期间已被删除：跳过这一项，
            # 不要让整个目录的扫描中断
            return None

    def consume(root_path, collect_dirs):
        try:
            with os.scandir(root_path) as it:
                for entry in it:
                    rec = build(entry)
                    if rec is None:
                        continue
                    if rec["is_dir"]:
                        if collect_dirs:
                            dirs.append(rec)
                    else:
                        files.append(rec)
        except OSError:
            # 单个子目录不可读时只跳过它，不影响其余部分
            pass

    if recursive:
        # onerror 兜底：遇到无权限目录时跳过而不是中断整次扫描
        for root_path, subdirs, _ in os.walk(directory, onerror=lambda e: None):
            # 排序保证遍历顺序稳定可复现（os.walk 默认顺序取决于文件系统）
            subdirs.sort(key=natural_sort_key)
            consume(root_path, collect_dirs=False)
    else:
        consume(directory, collect_dirs=True)

    return files, dirs


class FileListViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("文件列表查看器")
        self.root.geometry("1000x600")
        self.root.resizable(True, True)
        
        # 初始化状态栏变量
        self.status_var = tk.StringVar(value="就绪")
        
        # 当前选中的目录
        self.current_directory = ""
        # 文件 / 文件夹记录列表。改存字典记录（而不是纯文件名字符串），是为了让
        # 大小、修改时间、完整路径等属性随扫描一次性取回；后续的字段展示、
        # 递归扫描、多字段导出都依赖这个结构。
        self.files = []
        self.dirs = []
        self.file_extensions = set()  # 当前目录出现过的扩展名（小写、无点号）
        self.show_folders = False  # 是否显示文件夹
        self._keyword_job = None   # 关键词过滤的节流句柄（见 _on_keyword_change）
        
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # 创建样式和组件
        self._setup_styles()
        self._create_directory_section()
        self._create_actions_section()
        self._create_file_list_section()
        
        # 设置窗口外观
        self.root.configure(bg="#f0f0f0")
        
        # 设置窗口图标（如果有）
        try:
            if hasattr(sys, '_MEIPASS'):
                # 在PyInstaller打包后的环境中
                icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
                if os.path.exists(icon_path):
                    self.root.iconbitmap(icon_path)
            else:
                # 在开发环境中
                icon_path = 'icon.ico'
                if os.path.exists(icon_path):
                    self.root.iconbitmap(icon_path)
        except:
            # 图标设置失败不影响程序运行
            pass
    

        
    def _setup_styles(self):
        # 配置UI样式
        self.style = ttk.Style()
        self.style.theme_use("vista")
        
        # 统一按钮样式
        self.style.configure("TButton",
                            padding=(10, 5),
                            relief=tk.RAISED,
                            font=("Microsoft YaHei UI", 10))
        
        # 为不同状态添加更美观的样式
        self.style.map("TButton",
                      foreground=[('pressed', 'black'), ('active', 'blue')],
                      background=[('pressed', '!disabled', '#d9d9d9'), ('active', '#e6e6e6')])

        # 表格样式：中文字体与合适的行高
        self.style.configure("Treeview",
                            font=("Microsoft YaHei UI", 10),
                            rowheight=24,
                            background="white",
                            fieldbackground="white")
        self.style.configure("Treeview.Heading",
                            font=("Microsoft YaHei UI", 10))
    
    def _create_directory_section(self):
        directory_frame = ttk.LabelFrame(self.main_frame, text="目录选择", padding="10")
        directory_frame.pack(fill=tk.X, pady=5)
        
        self.directory_var = tk.StringVar()
        directory_entry = ttk.Entry(directory_frame, textvariable=self.directory_var, width=60)
        directory_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        # 添加回车键事件绑定，输入目录后按回车自动加载文件列表
        directory_entry.bind("<Return>", lambda event: self._refresh_file_list())
        # 添加焦点离开事件绑定，输入目录后点击其他地方自动加载文件列表
        directory_entry.bind("<FocusOut>", lambda event: self._refresh_file_list())
        
        browse_btn = ttk.Button(directory_frame, text="浏览...", command=self._browse_directory)
        browse_btn.pack(side=tk.LEFT, padx=5)
        
        refresh_btn = ttk.Button(directory_frame, text="刷新", command=self._refresh_file_list)
        refresh_btn.pack(side=tk.LEFT, padx=5)
    
    def _create_file_list_section(self):
        # 状态栏必须先于列表区 pack，并固定在底部。
        # Tk 的 pack 在空间不足时会把【最后】pack 的控件压成 0 高度，
        # 而列表区带 expand=True 会吃掉剩余空间 —— 顺序反了状态栏就会消失。
        status_label = ttk.Label(self.main_frame,
                                 textvariable=self.status_var,
                                 relief=tk.FLAT,
                                 anchor=tk.W,
                                 padding=(10, 5),
                                 background="#E0E0E0",
                                 font=("Microsoft YaHei UI", 9))
        status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))

        list_frame = ttk.LabelFrame(self.main_frame, text="文件列表", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5, ipady=5)
        
        # 文件列表改用 Treeview 表格：原生支持多列、表头与选中，
        # 也是后续「字段可选」「勾选部分文件」等功能的基础。
        tree_area = ttk.Frame(list_frame)
        tree_area.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.tree = ttk.Treeview(tree_area, columns=(), show="headings",
                                 selectmode="extended")
        vbar = ttk.Scrollbar(tree_area, orient=tk.VERTICAL, command=self.tree.yview)
        hbar = ttk.Scrollbar(tree_area, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        tree_area.rowconfigure(0, weight=1)
        tree_area.columnconfigure(0, weight=1)
        
        
        
        # 状态栏已在本方法开头创建并固定到底部（必须先于列表区 pack）

    def _create_actions_section(self):
        # 创建一个标签框架，使按钮区域更明显
        actions_frame = ttk.LabelFrame(self.main_frame, text="操作", padding="10")
        actions_frame.pack(fill=tk.X, pady=5)
        
        # 创建一个框架来容纳所有按钮和控件，确保在同一行显示
        buttons_frame = ttk.Frame(actions_frame)
        buttons_frame.pack(fill=tk.X, pady=5)
        
        # 统一按钮的宽度参数
        button_width = 12
        
        # 复制按钮
        copy_btn = ttk.Button(buttons_frame, text="复制", width=button_width, command=self._copy_all_filenames)
        copy_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 导出按钮
        export_btn = ttk.Button(buttons_frame, text="导出", width=button_width, command=self._export_to_text)
        export_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 添加分隔线
        separator = ttk.Separator(buttons_frame, orient='vertical')
        separator.pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        # 复制 / 导出格式。默认"跟随列表"，即输出与表格当前显示的列完全一致
        ttk.Label(buttons_frame, text="复制格式:",
                  font=('Microsoft YaHei UI', 10)).pack(side=tk.LEFT, padx=5)
        self.copy_format_var = tk.StringVar(value=OUTPUT_FORMATS[0])
        fmt_combo = ttk.Combobox(buttons_frame, textvariable=self.copy_format_var,
                                 values=OUTPUT_FORMATS, width=17, state="readonly")
        fmt_combo.pack(side=tk.LEFT, padx=5)

        # 过滤：文件类型（支持多选）。选项在每次扫描后按实际出现的扩展名重建
        ttk.Label(buttons_frame, text="文件类型:",
                  font=('Microsoft YaHei UI', 10)).pack(side=tk.LEFT, padx=5)
        self.filter_btn = ttk.Menubutton(buttons_frame, text="所有文件", width=13)
        self.filter_btn.pack(side=tk.LEFT, padx=5)
        self.filter_menu = tk.Menu(self.filter_btn, tearoff=0)
        self.filter_btn["menu"] = self.filter_menu
        self.filter_vars = {}          # 扩展名 -> BooleanVar

        # 过滤：文件名关键词，输入即过滤（带节流，见 _on_keyword_change）
        ttk.Label(buttons_frame, text="关键词:",
                  font=('Microsoft YaHei UI', 10)).pack(side=tk.LEFT, padx=5)
        self.keyword_var = tk.StringVar()
        keyword_entry = ttk.Entry(buttons_frame, textvariable=self.keyword_var, width=16)
        keyword_entry.pack(side=tk.LEFT, padx=5)
        keyword_entry.bind("<KeyRelease>", self._on_keyword_change)
        
        # 第二行：扫描范围与显示选项
        options_frame = ttk.Frame(actions_frame)
        options_frame.pack(fill=tk.X, pady=(0, 5))

        # 递归扫描：勾选后列出所有层级的文件，此时不再列出文件夹
        self.recursive_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="包含子文件夹",
                        variable=self.recursive_var,
                        command=self._toggle_recursive).pack(side=tk.LEFT, padx=5)

        self.folders_var = tk.BooleanVar(value=False)
        self.folders_check = ttk.Checkbutton(options_frame, text="显示文件夹",
                                             variable=self.folders_var,
                                             command=self._toggle_folders)
        self.folders_check.pack(side=tk.LEFT, padx=8)

        # 排序（由第一行移到这里，为关键词输入框腾出横向空间）
        ttk.Label(options_frame, text="排序:",
                  font=('Microsoft YaHei UI', 10)).pack(side=tk.LEFT, padx=(5, 0))
        self.sort_var = tk.StringVar(value="升序")
        sort_combo = ttk.Combobox(options_frame, textvariable=self.sort_var,
                                  values=["升序", "降序"], width=6, state="readonly")
        sort_combo.pack(side=tk.LEFT, padx=5)
        sort_combo.bind("<<ComboboxSelected>>", lambda event: self._redraw_list())

        ttk.Separator(options_frame, orient='vertical').pack(
            side=tk.LEFT, padx=10, fill=tk.Y)

        ttk.Label(options_frame, text="显示字段:",
                  font=('Microsoft YaHei UI', 10)).pack(side=tk.LEFT, padx=5)

        self.col_path_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="完整路径", variable=self.col_path_var,
                        command=self._redraw_list).pack(side=tk.LEFT, padx=8)

        self.col_size_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="大小", variable=self.col_size_var,
                        command=self._redraw_list).pack(side=tk.LEFT, padx=8)

        self.col_mtime_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="修改时间", variable=self.col_mtime_var,
                        command=self._redraw_list).pack(side=tk.LEFT, padx=8)
    
    def _browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.directory_var.set(directory)
            self.current_directory = directory
            self._load_file_list(directory)
    
    def _refresh_file_list(self):
        directory = self.directory_var.get().strip()
        if not directory:
            # 恢复使用messagebox显示错误
            messagebox.showinfo("提示", "请先选择一个目录")
            return
        
        if not os.path.isdir(directory):
            messagebox.showerror("错误", "指定的路径不是有效的目录")
            return
        
        self._load_file_list(directory)
    
    def _load_file_list(self, directory):
        try:
            # 记录当前目录（手工输入路径走这里时也要同步，否则复制/导出会被误拦）
            self.current_directory = directory

            # 扫描目录，一次性取回文件与文件夹记录（含大小、修改时间、完整路径）
            self.files, self.dirs = scan_directory(directory,
                                                   self.recursive_var.get())
            # 这里保留空串（无扩展名的文件，如 README / LICENSE），
            # 让「全选」能覆盖到它们，避免"点了全选反而少了几行"的困惑
            self.file_extensions = {r["ext"] for r in self.files}

            # 按当前目录实际出现的扩展名重建类型多选菜单
            self._rebuild_filter_menu()
            
            # 重绘表格与状态栏
            self._redraw_list()
            
        except Exception as e:
            messagebox.showerror("错误", f"加载文件列表时出错：{str(e)}")
            self.status_var.set("加载失败")
    
    def _get_items_to_display(self):
        """获取需要显示 / 输出、且已按当前排序与过滤条件处理好的记录列表"""
        # 获取排序顺序
        sort_order = self.sort_var.get() if hasattr(self, 'sort_var') else "升序"
        reverse = (sort_order == "降序")

        # 应用关键词与扩展名过滤
        filtered_files = self._filter_records(self.files)

        # 排序键跟随实际显示的第一列：递归时按相对路径排（读起来就是目录树的顺序），
        # 否则按文件名排。若一律按文件名排，递归结果会按名字散落在不同目录间，
        # 完全无法按层级阅读。
        if self.recursive_var.get():
            sort_key = lambda r: path_sort_key(r["rel"])
        else:
            sort_key = lambda r: path_sort_key(r["name"])
        filtered_files.sort(key=sort_key, reverse=reverse)

        # 如果需要显示文件夹
        if self.show_folders:
            sorted_dirs = sorted(self.dirs,
                                 key=lambda r: path_sort_key(r["name"]),
                                 reverse=reverse)
            # 文件夹和文件分开显示
            return sorted_dirs + filtered_files
        else:
            return filtered_files

    def _selected_extensions(self):
        """当前选中的扩展名集合；空集表示不限类型"""
        return {ext for ext, var in self.filter_vars.items() if var.get()}

    def _filter_records(self, records):
        """按关键词与扩展名过滤文件记录。

        两个条件是「且」的关系，都未设置时原样返回。
        关键词同时匹配文件名与相对路径（递归模式下可用来筛某个子目录）；
        中间用 \n 拼接，避免关键词恰好横跨两段产生误匹配。
        """
        exts = self._selected_extensions()
        keyword = self.keyword_var.get().strip().lower()

        if not exts and not keyword:
            return records

        result = []
        for r in records:
            if exts and r["ext"] not in exts:
                continue
            if keyword and keyword not in (r["name"] + "\n" + r["rel"]).lower():
                continue
            result.append(r)
        return result

    def _active_columns(self):
        """当前启用的列。文件名始终显示，其余列由勾选框决定。"""
        cols = ["name"]
        if self.col_path_var.get():
            cols.append("path")
        if self.col_size_var.get():
            cols.append("size")
        if self.col_mtime_var.get():
            cols.append("mtime")
        return cols

    def _cell_value(self, rec, key):
        """取出某条记录在指定列上的展示值"""
        if key == "name":
            # 递归时改用相对路径：不同子目录下的同名文件必须能区分开
            return rec["rel"] if self.recursive_var.get() else rec["name"]
        if key == "path":
            return rec["path"]
        if key == "size":
            # 文件夹不统计大小（目录的 st_size 在 Windows 上恒为 0，显示"0 B"会误导）
            return "-" if rec.get("is_dir") else format_size(rec["size"])
        if key == "mtime":
            return format_mtime(rec["mtime"])
        return ""

    def _rebuild_tree_columns(self):
        """按当前启用的列重建表头"""
        cols = self._active_columns()
        self.tree["columns"] = cols
        for key in cols:
            _, width, anchor, stretch = COLUMN_META[key]
            # 递归时第一列内容变成相对路径，表头同步改名，避免文不对题
            title = COLUMN_META[key][0]
            if key == "name" and self.recursive_var.get():
                title = "相对路径"
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=60,
                             anchor=anchor, stretch=stretch)

    def _redraw_list(self):
        """用已扫描到的记录重绘表格与状态栏（不重新读取磁盘）。

        过滤、排序、切换字段、显示文件夹等操作都走这里，
        避免每次操作都重新扫描一遍目录。
        """
        self._rebuild_tree_columns()

        for iid in self.tree.get_children():
            self.tree.delete(iid)

        records = self._get_items_to_display()
        cols = self._active_columns()

        if records:
            for rec in records:
                self.tree.insert("", tk.END,
                                 values=[self._cell_value(rec, k) for k in cols])
        else:
            # 空结果时占位，避免出现一片空白让人以为程序坏了
            self.tree.insert("", tk.END,
                             values=["（没有符合条件的项目）"] + [""] * (len(cols) - 1))

        self._update_status(len(records))

    def _update_status(self, shown_count):
        """更新状态栏：项目总数、文件数、合计大小"""
        total = len(self.files) + (len(self.dirs) if self.show_folders else 0)
        text = f"找到 {total} 个项目"
        if self.files:
            total_size = sum(r["size"] for r in self.files)
            text += f"（文件 {len(self.files)} 个，合计 {format_size(total_size)}）"
        if shown_count != total:
            text += f"，过滤后显示 {shown_count} 个"
        self.status_var.set(text)

    def _output_lines(self, records):
        """把记录列表转成待输出的文本行（复制与导出共用）。

        默认「跟随列表」：输出与表格当前显示的列完全一致 —— 只看文件名时每行一个
        名称；勾选了额外字段时用制表符分列，可直接粘进 Excel / WPS。
        （单列时 \t 拼接不会产生制表符，行为与旧版一致。）

        其余格式则覆盖列设置，直接输出指定形态。
        """
        fmt = self.copy_format_var.get()

        if fmt == "仅文件名":
            return [r["name"] for r in records]
        if fmt == "完整路径":
            return [r["path"] for r in records]
        if fmt == "完整路径（带引号）":
            # Windows 路径常含空格，贴进命令行时必须有引号
            return ['"%s"' % r["path"] for r in records]
        if fmt == "逗号分隔":
            # 单行输出，便于贴进聊天窗口或表格的单个单元格
            return [", ".join(r["name"] for r in records)]

        # 跟随列表
        cols = self._active_columns()
        return ["\t".join(self._cell_value(r, k) for k in cols)
                for r in records]
    
    def _rebuild_filter_menu(self):
        """按当前目录实际出现的扩展名重建「文件类型」多选菜单。

        重建时保留上一次已勾选的扩展名，避免刷新或切换目录后选择被清空。
        """
        previously = self._selected_extensions()

        self.filter_menu.delete(0, tk.END)
        self.filter_menu.add_command(label="全选",
                                     command=lambda: self._set_all_extensions(True))
        self.filter_menu.add_command(label="清除选择",
                                     command=lambda: self._set_all_extensions(False))

        exts = sorted(self.file_extensions, key=natural_sort_key)
        self.filter_vars = {}
        if exts:
            self.filter_menu.add_separator()
            for ext in exts:
                var = tk.BooleanVar(value=(ext in previously))
                self.filter_vars[ext] = var
                self.filter_menu.add_checkbutton(
                    label=ext if ext else "（无扩展名）",
                    variable=var,
                    command=self._on_filter_changed)

        self._update_filter_button()

    def _set_all_extensions(self, value):
        """一键全选 / 清除全部类型"""
        for var in self.filter_vars.values():
            var.set(value)
        self._on_filter_changed()

    def _update_filter_button(self):
        """按钮文字反映当前选择：不限 / 单个类型 / 已选 N 种"""
        selected = self._selected_extensions()
        if not selected:
            text = "所有文件"
        elif len(selected) == 1:
            text = next(iter(selected))
        else:
            text = "已选 %d 种" % len(selected)
        self.filter_btn.configure(text=text)

    def _on_filter_changed(self):
        """类型选择变化：更新按钮文字并重绘表格"""
        self._update_filter_button()
        self._redraw_list()

    def _on_keyword_change(self, event=None):
        """关键词输入：节流后再重绘。

        逐字触发会在大目录下反复重建整张表格，因此用 after 合并连续输入，
        只在停止输入约 200ms 后真正过滤一次。
        """
        if self._keyword_job is not None:
            self.root.after_cancel(self._keyword_job)
        self._keyword_job = self.root.after(200, self._redraw_list)

    def _toggle_folders(self):
        """切换是否显示文件夹（只重绘表格，不重新读磁盘）"""
        self.show_folders = self.folders_var.get()
        self._redraw_list()

    def _toggle_recursive(self):
        """切换是否递归扫描子文件夹。

        递归模式下只列文件（层级由相对路径体现），「显示文件夹」随之失去意义，
        因此一并置灰并取消勾选，避免出现「勾了却没反应」的困惑。

        递归需要重新遍历整棵目录树，所以这里走完整的重新扫描，
        而不是像 _toggle_folders 那样只重绘。
        """
        recursive = self.recursive_var.get()
        if recursive:
            self.show_folders = False
            self.folders_var.set(False)
        self.folders_check.state(["disabled"] if recursive else ["!disabled"])
        self._refresh_file_list()
    
    def _get_current_directory(self):
        """实时从输入框取目录，作为复制/导出的唯一校验来源。

        不能只依赖 self.current_directory：用户手工在输入框粘贴路径后回车时
        列表能正常加载，若该属性未同步就会把复制/导出误判为「未选择目录」。
        """
        directory = self.directory_var.get().strip()
        if directory and os.path.isdir(directory):
            return directory
        return None

    def _copy_all_filenames(self):
        try:
            if not self._get_current_directory():
                messagebox.showerror("错误", "请先选择有效的目录")
                return
            
            # 获取当前显示的项目列表
            items_to_copy = self._get_items_to_display()
            
            if not items_to_copy:
                messagebox.showinfo("提示", "没有可复制的项目")
                return
            
            # 生成所有项目的文本
            items_text = "\n".join(self._output_lines(items_to_copy))
            pyperclip.copy(items_text)
            
            item_type = "文件名和文件夹" if self.show_folders else "文件名"
            messagebox.showinfo("成功", f"已复制 {len(items_to_copy)} 个{item_type}到剪贴板")
            
        except Exception as e:
            messagebox.showerror("错误", f"复制时出错：{str(e)}")
    
    def _export_to_text(self):
        if not self._get_current_directory():
            messagebox.showerror("错误", "请先选择有效的目录")
            return
        
        try:
            # 获取当前显示的项目列表
            items_to_export = self._get_items_to_display()
            
            if not items_to_export:
                messagebox.showinfo("提示", "没有可导出的项目")
                return
            
            # 选择保存文件路径
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*")],
                title="导出文件列表"
            )
            
            if not file_path:
                return  # 用户取消选择
            
            # 写入项目到文件
            # 用 utf-8-sig（带 BOM）：国内用户多用 Excel/WPS 双击打开导出的 txt，
            # 无 BOM 的 UTF-8 会被识别成 ANSI，导致中文文件名乱码
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                for line in self._output_lines(items_to_export):
                    f.write(line + "\n")
            
            item_type = "文件名和文件夹" if self.show_folders else "文件名"
            messagebox.showinfo("成功", f"已成功导出 {len(items_to_export)} 个{item_type}到文件\n{file_path}")
            
        except Exception as e:
            messagebox.showerror("错误", f"导出文件时出错：{str(e)}")
    
    def _on_closing(self):
        if messagebox.askyesno("确认退出", "确定要退出程序吗？"):
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = FileListViewer(root)
    root.mainloop()