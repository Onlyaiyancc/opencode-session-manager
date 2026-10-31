# OpenCode 会话管理器

[![Tests](https://github.com/Onlyaiyancc/opencode-session-manager/actions/workflows/tests.yml/badge.svg)](https://github.com/Onlyaiyancc/opencode-session-manager/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-blue.svg)](#环境要求)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

轻量、本机运行的中文 OpenCode 会话管理网页。搜索和预览对话，按项目、更新时间整理历史，支持重命名、归档及批量删除。

使用 Python 标准库与原生 HTML/CSS/JavaScript，无需安装第三方 Python 包或前端构建依赖。

> 独立社区工具，目前完整管理功能适配 **Windows 上的 OpenCode Desktop 1.19.5**。运行时复用本机已安装的 OpenCode，不附带其程序或用户数据；其他版本尚未验证。

## 目录

- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [使用说明](#使用说明)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [开发与测试](#开发与测试)
- [常见问题](#常见问题)
- [参与贡献](#参与贡献)
- [许可证](#许可证)

## 功能特性

- **中文界面**：导航、筛选、日期、状态和操作确认均使用中文。
- **会话整理**：搜索标题和项目路径，筛选归档状态、目录、更新时间及子会话。
- **轻量预览**：会话与消息分页加载，排除大型分块和嵌入附件，长文本明确标记截断。
- **常用管理**：重命名、归档和取消归档，通过 OpenCode 自身接口保存修改。
- **批量删除**：先列出包含子会话的完整范围，再输入「删除 N」确认；执行前重新检查范围是否变化。
- **文本导出**：导出可读的 Markdown 对话文本，明确标记省略和截断内容。
- **本机运行**：服务仅监听回环地址，前端不加载远程脚本、字体或图片。

## 环境要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | 完整管理功能需要 Windows |
| OpenCode | 已安装 OpenCode Desktop 1.19.5 |
| Python | 3.12 或更新版本，内置 SQLite 3.43 或更新版本 |
| 浏览器 | 支持现代 JavaScript 的浏览器 |
| 普通测试 | 无需安装 OpenCode，可在 Windows/Linux 运行 |

未来 OpenCode 版本可能调整内部模块或数据库结构，升级后请先确认兼容性。

## 快速开始

### 1. 获取项目

克隆仓库，或从 GitHub 下载 ZIP 后解压：

```powershell
git clone https://github.com/Onlyaiyancc/opencode-session-manager.git
cd opencode-session-manager
```

### 2. 启动管理器

Windows 用户可双击根目录的 **启动会话管理.cmd**。脚本优先使用现有 Anaconda Python，否则使用系统的 `python`。

也可以在终端运行：

```powershell
python main.py --open
```

浏览器将打开 **[http://127.0.0.1:8787](http://127.0.0.1:8787)**。再次启动时，会复用该端口上已运行的管理器。

### 3. 关闭管理器

使用期间保持启动窗口运行。点击网页右上角的关闭按钮，或在启动窗口按 `Ctrl+C`，即可停止服务。

## 使用说明

1. 在左侧选择会话视图或项目，使用搜索框和日期条件缩小范围。
2. 点击会话查看分页预览，并按需重命名、归档或导出。
3. 批量删除时勾选会话，核对完整清单和子会话数量，再输入对应确认文字。

**修改会话前，请先关闭 OpenCode 桌面端**，避免另一个进程同时在会话中执行任务。浏览和预览是只读操作，管理服务仅在需要时启动。

- 日期筛选使用**北京时间当天 00:00**，仅匹配严格早于该时刻的更新时间。
- 「超过一个月未更新」减去一个日历月，月末自动收敛到上个月最后一天。
- 删除父会话会包含其子会话，实际影响范围以确认清单为准。
- Markdown 导出会省略大型分块、嵌入附件以及超出预览限额的内容，**不能作为完整备份**。
- 删除记录不会自动收缩数据库文件。不要在 OpenCode 或管理器运行时手动执行 `VACUUM`。

## 配置说明

默认数据库为 `%USERPROFILE%\.local\share\opencode\opencode.db`。

| 参数或环境变量 | 默认值 / 用途 |
| --- | --- |
| `--db` / `OPENCODE_DB` | 指定 OpenCode 数据库；`--db` 优先 |
| `--port` | 网页端口，默认 `8787` |
| `--open` | 启动后打开浏览器 |
| `OPENCODE_DESKTOP_DIR` | 桌面端安装目录，默认 `%LOCALAPPDATA%\Programs\@opencode-aidesktop` |
| `LOCALAPPDATA` | 运行日志默认位于其下的 `OpenCodeSessionManager` 目录 |

例如，使用其他端口：

```powershell
python main.py --port 8788 --open
```

程序凭证随机生成，仅保存在进程内存中，不返回网页。请求经过 Host、Origin 和防跨站令牌检查；会话文本按文本渲染，不作为 HTML 执行。

## 项目结构

```text
opencode-session-manager/
├── main.py                 # 命令行启动入口
├── 启动会话管理.cmd          # Windows 双击启动
├── README.md
├── LICENSE
├── app/                    # 应用实现与网页资源
│   ├── server.py           # 本机 HTTP 服务和管理操作
│   ├── store.py            # 只读查询、分页预览和导出
│   ├── bridge.py           # OpenCode 后台服务与认证
│   ├── official-server.cjs # 加载已安装的 OpenCode 模块
│   └── static/             # HTML、CSS、JavaScript 和图标
├── tests/                  # 单元、HTTP 和可选集成测试
├── docs/                   # 架构说明与更新记录
└── .github/workflows/      # 自动化检查
```

更多设计说明见 [架构文档](docs/ARCHITECTURE.md)，历史变更见 [更新记录](docs/CHANGELOG.md)。

## 开发与测试

从项目根目录运行普通测试：

```powershell
python -m unittest discover -v
```

普通测试不依赖 OpenCode。GitHub Actions 覆盖 Windows/Linux 与 Python 3.12/3.13，并检查前端 JavaScript 语法；本机检查前端语法需要 Node.js：

```powershell
node --check app/static/app.js
```

本机安装了受支持的 OpenCode 后，可显式启用集成测试：

```powershell
$env:OPENCODE_RUN_INTEGRATION = '1'
python -m unittest -v tests.test_official
Remove-Item Env:\OPENCODE_RUN_INTEGRATION
```

集成测试在新建的临时数据库中验证重命名、归档和包含子会话的删除，不修改真实会话。普通测试覆盖筛选边界、受限预览、导出标记、删除范围变化、跨站防护和页面元素绑定。

## 常见问题

### 页面能打开，但修改失败？

先关闭 OpenCode 桌面端，再重试。确认已安装受支持版本；如果安装目录不同，设置 `OPENCODE_DESKTOP_DIR`。详细运行日志位于 `%LOCALAPPDATA%\OpenCodeSessionManager`。

### 端口被占用？

关闭之前的管理器，或用 `--port 8788` 指定其他端口。

### 新版 OpenCode 可以直接使用吗？

目前仅验证了 Desktop 1.19.5 的内部服务和旧版 `session/message/part/event_sequence` 数据结构。其他版本需要单独验证，不保证兼容。

## 参与贡献

欢迎通过 [Issues](https://github.com/Onlyaiyancc/opencode-session-manager/issues) 反馈问题或提出改进，也欢迎提交 Pull Request。修改后请运行相关测试，并同步更新使用说明。

数据库、凭据、日志、导出和备份已通过 `.gitignore` 排除。提交 Issue 或代码时，请去除真实对话、账号信息、密钥和含私人标题的截图。

## 许可证

本项目采用 [MIT 许可证](LICENSE)。OpenCode 及其运行时组件属于上游作者，遵循各自许可证。

接口实现参考 [OpenCode 1.19.5 会话接口源码](https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/server/routes/instance/httpapi/groups/session.ts)。
