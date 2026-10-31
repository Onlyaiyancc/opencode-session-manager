# OpenCode Session Manager

Local-only desktop companion. No cloud deployment or uploaded conversation data.

All interface labels, date formatting, status messages, and typed deletion confirmations use Simplified Chinese. Preserve original conversation titles and content.

## Experience

Three panes: project/time/archive filters, searchable paginated session rows, and a bounded conversation preview. A blue-gray workspace, white reading surface, Segoe UI Variable typography, cobalt selection, amber attachment notices, and restrained motion. Palette: canvas #f3f5f9, sidebar #e9edf5, surface #ffffff, ink #17233b, accent #345cdb, muted #5d6b83. Compact rows with readable 14–16 px content; no decorative charts or hero section.

Search titles and directories; filter archived sessions, nested sessions, and last-update dates; rename, archive/unarchive, export a readable Markdown transcript, and delete selected sessions with a descendant preview and typed confirmation. Exports are readable transcripts, not full backups: oversized parts and embedded attachment bytes are omitted explicitly.

## Architecture

Python standard-library HTTP server on loopback, static HTML/CSS/JS, read-only SQLite queries for lists and bounded previews. No npm installation or hosted service. Mutations use the installed OpenCode 1.19.5 server bundle in its own Electron Node runtime, started lazily with a random password kept in process memory. This preserves OpenCode event/projector behavior. Support the installed legacy session/part schema explicitly; fail clearly on unsupported schema changes.

Do not fetch large attachments into the browser. Query JSON byte lengths before selecting preview payloads. Pagination and response size limits apply. Render conversation content with textContent, never HTML. HTTP Host/Origin validation, process-scoped anti-CSRF token, restricted static file routes, and no credential-bearing configuration responses.

## Verification plan

1. Write failing fixture tests for search/date/archive boundaries, nested deletion planning, SQL parameterization, oversized-preview limits, and stale deletion plans.
2. Implement Store, lazy official-server bridge, scoped HTTP endpoints, and a one-command Windows launcher.
3. Implement the responsive three-pane interface and real loading/error/empty states.
4. Test rename/archive/unarchive/recursive deletion using only a temporary OpenCode database and the actual installed server.
5. Inspect desktop/mobile screenshots and keyboard/dialog behavior in a browser; use the real database only for read-only page verification.
6. Deliver a running localhost URL, source files, launcher, and concise usage instructions. Do not exercise write actions on real conversations during development.
