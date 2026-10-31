# OpenCode Session Manager

**English** | [简体中文](README.zh-CN.md)

[![Tests](https://github.com/Onlyaiyancc/opencode-session-manager/actions/workflows/tests.yml/badge.svg)](https://github.com/Onlyaiyancc/opencode-session-manager/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-blue.svg)](#requirements)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A lightweight, local web interface for managing OpenCode conversations. Search and preview sessions, filter by project or last update, rename conversations, archive them, and delete selected sessions in bulk.

Built with the Python standard library and plain HTML/CSS/JavaScript. No third-party Python packages or frontend build dependencies are required.

> An independent community tool. Full management functionality is currently tested with **OpenCode Desktop 1.19.5 on Windows**. It reuses your locally installed OpenCode runtime and does not bundle OpenCode or user data. Other versions have not been verified.

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [Project structure](#project-structure)
- [Development and testing](#development-and-testing)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Chinese-language interface:** Chinese navigation, filters, dates, status messages, and operation confirmations.
- **Session organization:** Search titles and project paths; filter by archive status, directory, update date, and sub-session visibility.
- **Lightweight previews:** Paginated sessions and messages, with oversized parts and embedded attachments excluded. Long text is explicitly marked as truncated.
- **Common operations:** Rename, archive, and unarchive sessions through OpenCode's own API.
- **Bulk deletion:** Review the complete scope, including child sessions, then type `删除 N` (delete N) to confirm. The selection is checked again before deletion.
- **Text export:** Download readable Markdown transcripts with explicit omission and truncation notices.
- **Local interface:** The service listens only on loopback. The frontend loads no remote scripts, fonts, or images.

## Requirements

| Component | Requirement |
| --- | --- |
| Operating system | Windows for full management functionality |
| OpenCode | OpenCode Desktop 1.19.5 installed locally |
| Python | Python 3.12+ with SQLite 3.43+ |
| Browser | A browser supporting modern JavaScript |
| Unit tests | Run on Windows/Linux without OpenCode installed |

Future OpenCode versions may change internal modules or the database schema. Verify compatibility before upgrading.

## Quick start

### 1. Get the project

Clone the repository, or download and extract its ZIP from GitHub:

```powershell
git clone https://github.com/Onlyaiyancc/opencode-session-manager.git
cd opencode-session-manager
```

### 2. Start the manager

On Windows, double-click [启动会话管理.cmd](启动会话管理.cmd) in the project root. The launcher prefers an existing Anaconda Python installation and otherwise uses `python` from your system.

Alternatively, run:

```powershell
python main.py --open
```

Your browser opens **[http://127.0.0.1:8787](http://127.0.0.1:8787)**. Starting the launcher again reuses the manager already running on that port.

### 3. Stop the manager

Keep the launcher window open while using the application. Click the close button in the page's top-right corner, or press `Ctrl+C` in the launcher window, to stop the service.

## Usage

1. Choose a session view or project in the sidebar. Narrow the list with search and the update-date filter.
2. Select a session to preview its messages, rename it, archive it, or export readable text.
3. For bulk deletion, select sessions, review the full list and child-session count, then enter the displayed confirmation text.

**Close OpenCode Desktop before editing sessions** so another process cannot run tasks in the same conversations. Browsing and previews are read-only; the management service starts only when needed.

- Date filters use **00:00 Beijing time**, matching sessions updated strictly before the selected cutoff.
- The “older than a month” filter subtracts one calendar month and clamps month-end dates to the previous month's last day.
- Deleting a parent session includes its child sessions. Review the confirmation list for the exact scope.
- Markdown exports omit oversized parts, embedded attachments, and content beyond preview limits. **They are not full backups.**
- Deleting records does not automatically shrink the database file. Do not run `VACUUM` while OpenCode or this manager is running.

## Configuration

The default database is `%USERPROFILE%\.local\share\opencode\opencode.db`.

| Option or environment variable | Default / purpose |
| --- | --- |
| `--db` / `OPENCODE_DB` | Select the OpenCode database; `--db` takes precedence |
| `--port` | Web server port; defaults to `8787` |
| `--open` | Open the browser after startup |
| `OPENCODE_DESKTOP_DIR` | Desktop installation directory; defaults to `%LOCALAPPDATA%\Programs\@opencode-aidesktop` |
| `LOCALAPPDATA` | Runtime logs default to its `OpenCodeSessionManager` subdirectory |

For example, use another port:

```powershell
python main.py --port 8788 --open
```

Service credentials are generated randomly, kept in process memory, and never returned to the page. Requests are checked against Host, Origin, and an anti-CSRF token. Conversation content is rendered as text, never executed as HTML.

## Project structure

```text
opencode-session-manager/
├── main.py                 # Command-line entry point
├── 启动会话管理.cmd          # Windows launcher
├── README.md               # Default English documentation
├── README.zh-CN.md         # Simplified Chinese documentation
├── LICENSE
├── app/                    # Application and frontend assets
│   ├── server.py           # Local HTTP service and management operations
│   ├── store.py            # Read-only queries, previews, and exports
│   ├── bridge.py           # OpenCode service lifecycle and authentication
│   ├── official-server.cjs # Loads the installed OpenCode modules
│   └── static/             # HTML, CSS, JavaScript, and icons
├── tests/                  # Unit, HTTP, and optional integration tests
├── docs/                   # Architecture notes and changelog
└── .github/workflows/      # Automated checks
```

See the [architecture guide](docs/ARCHITECTURE.md) and [changelog](docs/CHANGELOG.md) for more details. These additional documents are currently in Chinese.

## Development and testing

Run the default test suite from the project root:

```powershell
python -m unittest discover -v
```

Unit tests do not require OpenCode. GitHub Actions runs them on Windows/Linux with Python 3.12/3.13 and checks frontend JavaScript syntax. Checking JavaScript locally requires Node.js:

```powershell
node --check app/static/app.js
```

If a supported OpenCode installation is available locally, explicitly enable integration tests:

```powershell
$env:OPENCODE_RUN_INTEGRATION = '1'
python -m unittest -v tests.test_official
Remove-Item Env:\OPENCODE_RUN_INTEGRATION
```

Integration tests use a new temporary database to verify renaming, archiving, and deletion with child sessions. They do not modify your real conversations. Unit tests cover filtering boundaries, bounded previews, export notices, changed deletion selections, cross-origin protections, and page-element bindings.

## FAQ

### The page opens, but editing fails. What should I check?

Close OpenCode Desktop and try again. Check that the supported version is installed. If its installation path differs, set `OPENCODE_DESKTOP_DIR`. Runtime logs are available under `%LOCALAPPDATA%\OpenCodeSessionManager`.

### What if the port is already in use?

Stop the previous manager, or select another port with `--port 8788`.

### Can I use a newer OpenCode version?

Only Desktop 1.19.5's internal service and legacy `session/message/part/event_sequence` schema have been verified. Compatibility with other versions is not guaranteed and requires separate testing.

## Contributing

Bug reports, suggestions, and pull requests are welcome. Open an [issue](https://github.com/Onlyaiyancc/opencode-session-manager/issues), run the relevant tests after making changes, and update both README language versions when behavior or setup instructions change.

Databases, credentials, logs, exports, and backups are excluded through `.gitignore`. Remove real conversations, account information, secrets, and screenshots containing private titles before submitting issues or code.

## License

This project is licensed under the [MIT License](LICENSE). OpenCode and its runtime components belong to their upstream authors and retain their respective licenses.

The implementation references the [OpenCode 1.19.5 session API source](https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/server/routes/instance/httpapi/groups/session.ts).
