# OpenCode 会话管理器

[![Tests](https://github.com/Onlyaiyancc/opencode-session-manager/actions/workflows/tests.yml/badge.svg)](https://github.com/Onlyaiyancc/opencode-session-manager/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

轻量、本机运行的中文 OpenCode 会话管理网页。搜索、预览和整理对话历史，避免把大型附件和完整事件历史加载进浏览器。

当前写操作适配 **Windows 上的 OpenCode Desktop 1.19.5**。这是独立的社区工具，运行时复用本机已安装的 OpenCode，不附带其程序或用户数据。

| 环境 | 要求 |
| --- | --- |
| 完整管理功能 | Windows，已安装 OpenCode Desktop 1.19.5 |
| Python | 3.12+，内置 SQLite 3.43+ |
| 网页依赖 | 无外部 JS、CSS、字体或前端构建依赖 |
| Python 第三方依赖 | 无，仅使用标准库 |
| 普通测试 | 不需要安装 OpenCode，可在 Windows/Linux 运行 |

OpenCode 桌面端未来版本可能改变内部模块或数据库结构；其他版本暂未验证。

## 启动

克隆仓库，或从 GitHub 下载 ZIP 后解压：

```powershell
git clone https://github.com/Onlyaiyancc/opencode-session-manager.git
cd opencode-session-manager
```

双击同目录的 **启动会话管理.cmd**，浏览器将打开 **http://127.0.0.1:8787**。如果管理器已运行，再次启动会直接打开现有页面。

使用时保持启动窗口运行。右上角关闭按钮或启动窗口中的 Ctrl+C 可以停止管理器。

也可以运行：

```powershell
python server.py --open
```

需要 Python 3.12 或更新版本，以及当前已安装的 OpenCode 桌面端。无需 npm install，也无需新增 Python 包。本机启动脚本会优先使用现有的 Anaconda Python。

## 管理功能

- 按会话标题、项目路径搜索，按目录、归档状态和更新时间筛选。
- 显示或隐藏子会话，分页浏览会话和消息。
- 重命名、归档和取消归档。
- 删除单个或批量选中的会话。先列出完整影响范围（含子会话），再输入「删除 N」确认；会话有变化时必须重新预览。
- 导出可读的 Markdown 对话文本。大型分块、嵌入附件和超出预览长度的内容会明确省略，**导出文本不是完整备份**。

浏览列表和预览为只读操作。**修改会话前请关闭 OpenCode 桌面端**，避免另一个进程同时在会话里执行任务。管理器会按需复用已安装 OpenCode 的服务模块进行修改，保持事件和会话数据一致。页面启动本身不会修改会话。

日期筛选使用北京时间当天 00:00，严格早于该时刻；「超过一个月未更新」减去一个日历月，并自动处理月末日期。删除会话不会自动收缩数据库文件；不要在 OpenCode 或本管理器运行时手动执行 VACUUM。

## 配置

默认数据库：`%USERPROFILE%\.local\share\opencode\opencode.db`。

可通过环境变量 `OPENCODE_DB` 或参数 `--db` 指定其他数据库。端口被其他程序占用时，可改用：

```powershell
python server.py --port 8788 --open
```

默认安装目录：`%LOCALAPPDATA%\Programs\@opencode-aidesktop`，可通过 `OPENCODE_DESKTOP_DIR` 覆盖。当前支持旧版 session/message/part/event_sequence 结构；未来版本结构不兼容时会明确提示。

运行日志位于 `%LOCALAPPDATA%\OpenCodeSessionManager`。服务凭证随机生成并仅保存在进程内存中，不返回网页。页面仅监听本机回环地址，检查 Host、Origin 和防跨站令牌；对话文本不会作为 HTML 执行，前端不加载远程脚本、字体或图片。

## 验证

普通测试不依赖 OpenCode，CI 在 Windows/Linux、Python 3.12/3.13 上运行：

```powershell
python -m unittest discover -v
```

本机已安装受支持的 OpenCode 时，可显式开启集成测试：

```powershell
$env:OPENCODE_RUN_INTEGRATION = '1'
python -m unittest -v test_official
Remove-Item Env:\OPENCODE_RUN_INTEGRATION
```

集成测试只在新建的临时数据库里验证创建、重命名、归档、取消归档和包含子会话的删除，不修改真实会话。其他测试覆盖筛选边界、大内容预览、导出截断标记、删除范围变化、跨站请求和中文页面元素绑定。

## 项目结构

```text
server.py             本机 HTTP 服务、操作入口和删除确认
store.py              只读查询、分页预览和文本导出
bridge.py             后台服务生命周期、认证和接口调用
official-server.cjs   加载已安装 OpenCode 的服务模块
static/               中文 HTML、CSS、JavaScript 和图标
test_*.py             单元、HTTP 和可选集成测试
.github/workflows/    自动化检查
```

数据库、凭据、运行日志、导出和备份均不属于项目源码，并通过 `.gitignore` 排除。请勿将真实对话或含私人标题的截图提交到公开仓库。

## 许可与兼容性

本项目采用 [MIT 许可证](LICENSE)。OpenCode 属于其原作者，运行时依赖遵循上游许可证。

接口依据：[OpenCode 1.19.5 会话接口源码](https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/server/routes/instance/httpapi/groups/session.ts)。
