# DirLens · 文件列表查看器

> 一键读取、复制、导出当前目录下的文件名 —— 面向 Windows 的轻量文件清单工具。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-lightgrey.svg)]()
[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg)]()

<!-- 建议在此处插入界面截图或 5 秒 GIF：选文件夹 → 点复制 → 粘贴到记事本。
     这是整个 README 转化率最高的位置，有图的项目下载量会明显更高。 -->

---

## 这是什么

Windows 原生并没有「把当前文件夹里的文件名一次性导出成清单」的能力：

- 全选后 `Shift + 右键 → 复制文件路径`，拿到的是**带完整路径**的一长串，还要手工清洗；
- 用 `dir /b` 或 PowerShell 也能做到，但对不熟悉命令行的同学门槛太高；
- 想把文件清单导成表格，得绕好几个弯。

**DirLens 只做这一件事**：打开 → 选文件夹 → 复制或导出。

## 功能

- 读取指定文件夹下的文件列表
- **一键复制**全部文件名到剪贴板
- **导出**清单到文本文件
- **按文件类型过滤**（例如只保留 `.pdf`、`.jpg`）
- 支持**升序 / 降序**排序
- 可切换是否显示子文件夹
- 纯本地运行，**不联网、不上传任何数据**

## 下载

到 [Releases](../../releases/latest) 页面下载 `DirLens-*-win-x64.exe`，双击即可运行。

**免安装，无需 Python 环境。**

> 首次运行若出现 Windows SmartScreen 提示，点击「更多信息 → 仍要运行」即可。
> 这是所有未做代码签名的程序的通用提示，并非病毒告警。

## 快速使用

1. 双击 `DirLens.exe`
2. 点击「浏览...」选择目标文件夹
3. 点击「复制」或「导出」
4. 粘贴到 Excel / WPS / 文档 / 聊天窗口

## 与其他方案对比

| 方案 | 局限 |
|------|------|
| `Shift + 右键 → 复制文件路径` | 只给路径，需要手工清洗 |
| `dir /b` / PowerShell | 需要命令行基础 |
| 在线文件名提取网站 | 文件信息要上传到第三方服务器 |
| **DirLens** | 本地运行、一键完成、可过滤、免安装 |

## 从源码运行

```bash
git clone <你的仓库地址>
cd dirlens
pip install -r requirements.txt
python app.py
```

环境要求：Python 3.12（64 位）。

## 自行打包

```bash
pip install -r requirements.txt
pyinstaller --clean --noconfirm dirlens.spec
```

产物：`dist/DirLens.exe`

## 常见场景

| 场景 | 说明 |
|------|------|
| 整理归档 | 给一堆文件生成一份可对账的清单 |
| 资产盘点 / 审计 | 导出文件夹明细用于交付 |
| 报销 / 材料提交 | 把清单直接贴进表格 |
| 开发辅助 | 快速拿到一批文件名，拼脚本或批量处理 |

## 系统要求

- Windows 10 / 11（64 位）
- 无需安装 Python

## 后续计划

当前功能已满足设计目标，**暂不计划新增导出格式（CSV / Excel）与字段扩展**。

如果你有具体的使用场景没有被覆盖，欢迎提 [Issues](../../issues) 说明你的需求和使用环境，我会评估。

## 贡献与反馈

欢迎通过 [Issues](../../issues) 反馈问题或提出建议。

## 许可

[MIT](LICENSE) © 2025-2026 liuhongfei
