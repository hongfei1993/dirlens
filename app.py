import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import pyperclip

# 导入ScrolledText组件
from tkinter.scrolledtext import ScrolledText

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
        self.filenames = []  # 存储纯文件名列表
        self.folder_names = []  # 存储文件夹名列表
        self.all_items = []  # 存储所有项目（文件和文件夹）
        self.file_extensions = []  # 存储文件扩展名列表
        self.show_folders = False  # 是否显示文件夹
        
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
        self.style.theme_use("clam")
        
        # 统一按钮样式
        self.style.configure("TButton",
                            padding=(10, 5),
                            relief=tk.RAISED,
                            font=("Microsoft YaHei UI", 10))
        
        # 为不同状态添加更美观的样式
        self.style.map("TButton",
                      foreground=[('pressed', 'black'), ('active', 'blue')],
                      background=[('pressed', '!disabled', '#d9d9d9'), ('active', '#e6e6e6')])
    
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
        list_frame = ttk.LabelFrame(self.main_frame, text="文件列表", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5, ipady=5)
        
        # 创建滚动文本框 - 使用更现代的样式
        self.file_list_text = ScrolledText(list_frame, 
                                          font=("Microsoft YaHei UI", 10), 
                                          wrap=tk.NONE,
                                          bg="white",
                                          bd=1,
                                          relief=tk.SUNKEN,
                                          highlightthickness=1,
                                          highlightbackground="#CCCCCC",
                                          insertbackground="#000000")
        self.file_list_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.file_list_text.config(state=tk.DISABLED)
        
        
        
        # 添加状态标签
        status_label = ttk.Label(self.main_frame, 
                                textvariable=self.status_var, 
                                relief=tk.FLAT,
                                anchor=tk.W,
                                padding=(10, 5),
                                background="#E0E0E0",
                                font=("Microsoft YaHei UI", 9))
        status_label.pack(fill=tk.X, pady=(5, 0))
    
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
        
        # 过滤功能
        ttk.Label(buttons_frame, text="文件类型:", font=('Microsoft YaHei UI', 10)).pack(side=tk.LEFT, padx=5)
        self.filter_var = tk.StringVar(value="所有文件")
        self.filter_combo = ttk.Combobox(buttons_frame, textvariable=self.filter_var, width=12, state="readonly")
        self.filter_combo.pack(side=tk.LEFT, padx=5)
        self.filter_combo.bind("<<ComboboxSelected>>", lambda event: self._apply_filter())
        
        # 排序功能
        ttk.Label(buttons_frame, text="排序:", font=('Microsoft YaHei UI', 10)).pack(side=tk.LEFT, padx=5)
        self.sort_var = tk.StringVar(value="升序")
        sort_combo = ttk.Combobox(buttons_frame, textvariable=self.sort_var, values=["升序", "降序"], width=6, state="readonly")
        sort_combo.pack(side=tk.LEFT, padx=5)
        sort_combo.bind("<<ComboboxSelected>>", lambda event: self._refresh_file_list())
        
        # 显示文件夹选项
        self.folders_var = tk.BooleanVar(value=False)
        folders_checkbox = ttk.Checkbutton(buttons_frame, text="显示文件夹", variable=self.folders_var, command=self._toggle_folders)
        folders_checkbox.pack(side=tk.LEFT, padx=15)
    
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
            # 获取目录内容
            items = os.listdir(directory)
            
            # 清空列表
            self.filenames = []
            self.folder_names = []
            self.file_extensions = set()
            
            # 分类存储文件和文件夹
            for item in items:
                item_path = os.path.join(directory, item)
                if os.path.isfile(item_path):
                    self.filenames.append(item)
                    # 获取文件扩展名
                    _, ext = os.path.splitext(item)
                    if ext:
                        self.file_extensions.add(ext[1:])  # 去掉点号
                elif os.path.isdir(item_path):
                    self.folder_names.append(item)
            
            # 更新文件类型下拉菜单
            if hasattr(self, 'filter_combo'):
                extensions = sorted(self.file_extensions)
                filter_options = ["所有文件"] + extensions
                self.filter_combo['values'] = filter_options
                # 如果当前选择的扩展名不在列表中，重置为"所有文件"
                current_filter = self.filter_var.get()
                if current_filter != "所有文件" and current_filter not in extensions:
                    self.filter_var.set("所有文件")
            
            # 获取需要显示的项目
            items_to_display = self._get_items_to_display()
            
            # 清空文本框
            self.file_list_text.config(state=tk.NORMAL)
            self.file_list_text.delete(1.0, tk.END)
            
            # 显示项目
            if items_to_display:
                for item in items_to_display:
                    self.file_list_text.insert(tk.END, item + "\n")
                # 更新状态
                total_count = len(self.filenames) + (len(self.folder_names) if self.show_folders else 0)
                self.status_var.set(f"找到 {total_count} 个项目")
            else:
                self.file_list_text.insert(tk.END, "没有找到符合条件的项目")
                total_count = len(self.filenames) + (len(self.folder_names) if self.show_folders else 0)
                self.status_var.set(f"找到 {total_count} 个项目，过滤后显示 0 个")
            
            self.file_list_text.config(state=tk.DISABLED)
            
        except Exception as e:
            messagebox.showerror("错误", f"加载文件列表时出错：{str(e)}")
            self.status_var.set("加载失败")
    
    def _get_items_to_display(self):
        """获取需要显示的项目列表"""
        # 获取排序顺序
        sort_order = self.sort_var.get() if hasattr(self, 'sort_var') else "升序"
        reverse = (sort_order == "降序")
        
        # 应用文件类型过滤
        filtered_files = self._filter_by_extension(self.filenames)
        
        # 排序
        filtered_files.sort(reverse=reverse)
        
        # 如果需要显示文件夹
        if self.show_folders:
            # 排序文件夹
            sorted_folders = sorted(self.folder_names, reverse=reverse)
            # 文件夹和文件分开显示
            return sorted_folders + filtered_files
        else:
            return filtered_files
    
    def _filter_by_extension(self, filenames):
        """根据文件类型过滤文件"""
        if not hasattr(self, 'filter_var'):
            return filenames
            
        selected_type = self.filter_var.get()
        if selected_type == "所有文件":
            return filenames
            
        # 过滤特定扩展名的文件
        return [filename for filename in filenames 
                if os.path.splitext(filename)[1].lower() == f".{selected_type.lower()}"]
    
    def _apply_filter(self):
        """应用过滤条件"""
        directory = self.directory_var.get().strip()
        if directory and os.path.isdir(directory):
            self._load_file_list(directory)
    
    def _toggle_folders(self):
        """切换是否显示文件夹"""
        self.show_folders = self.folders_var.get()
        directory = self.directory_var.get().strip()
        if directory and os.path.isdir(directory):
            self._load_file_list(directory)
    
    def _copy_all_filenames(self):
        try:
            if not self.current_directory or not os.path.isdir(self.current_directory):
                messagebox.showerror("错误", "请先选择有效的目录")
                return
            
            # 获取当前显示的项目列表
            items_to_copy = self._get_items_to_display()
            
            if not items_to_copy:
                messagebox.showinfo("提示", "没有可复制的项目")
                return
            
            # 生成所有项目的文本
            items_text = "\n".join(items_to_copy)
            pyperclip.copy(items_text)
            
            item_type = "文件名和文件夹" if self.show_folders else "文件名"
            messagebox.showinfo("成功", f"已复制 {len(items_to_copy)} 个{item_type}到剪贴板")
            
        except Exception as e:
            messagebox.showerror("错误", f"复制时出错：{str(e)}")
    
    def _export_to_text(self):
        if not self.current_directory or not os.path.isdir(self.current_directory):
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
            with open(file_path, 'w', encoding='utf-8') as f:
                for item in items_to_export:
                    f.write(item + "\n")
            
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