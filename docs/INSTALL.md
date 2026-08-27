# 安装指南

## 系统要求

- **操作系统**：Windows 10+ / macOS 11+ / Linux（Ubuntu 20.04+、Debian 11+、CentOS 8+）
- **Python**：3.13.4 或更高版本（源码运行需要）
- **网络**：需要能访问数据源网站

## 方法一：用 Release 包（推荐）

去 [GitHub Releases](https://github.com/cdlongbow/mdcx-diy/releases) 下载最新版：

| 系统 | 下载什么 |
|------|---------|
| Windows 10/11（64 位） | `MDCx-...-windows-x86_64-....exe`（单文件，直接运行）|
| macOS（Apple Silicon）| `MDCx-...-macos-aarch64-....dmg` |

Linux 和 Intel 芯片 Mac 没有预编译包，请从下文的源码方式运行。

## 方法二：从源码运行

```bash
# 1. 装 Python 3.13+
# 去 https://www.python.org/downloads/ 下载安装
# Windows 安装时记得勾 "Add Python to PATH"

# 2. 装 uv（Python 包管理器）
# Windows:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. 下载代码
git clone https://github.com/cdlongbow/mdcx-diy.git
cd mdcx-diy

# 4. 安装依赖
uv sync --dev

# 5. 启动
uv run python main.py
```

### Linux 额外步骤

```bash
# 装系统图形库，否则界面可能花屏
sudo apt install libxcb-xinerama0 libxcb-cursor0
```

## 遇到问题

- 界面太大或太小：设置 → 高级 → 高分屏缩放
- 网络不通：设置 → 网络 → 配置代理；左侧导航「检测网络」页可批量测试站点连通性
- 其他：看 [USER_GUIDE.md](USER_GUIDE.md) 的常见问题部分