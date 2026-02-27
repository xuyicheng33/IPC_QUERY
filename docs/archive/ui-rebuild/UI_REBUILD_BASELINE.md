# IPC_QUERY Frontend Rebuild Baseline (Part 0)

This document freezes the functional and interface contracts for the Swiss Spa Precision UI rebuild.
All subsequent frontend changes must preserve these contracts unless explicitly approved.

## 1) Functional Contract Freeze

### 1.1 Page Routes (Must Stay Compatible)

| Public URL | Current Server Mapping | Required Compatibility |
|---|---|---|
| `/` | `web/index.html` | Must remain available |
| `/search` | `web/search.html` | Must remain available |
| `/db` | `web/db.html` | Must remain available |
| `/part/{id}` | `web/part.html` | Must remain available |
| `/viewer.html` | `web/viewer.html` | Must remain available |

Routing alias logic is currently handled by `ipc_query/api/handlers.py::handle_static`.

### 1.2 Query Parameter Matrix (Must Stay Compatible)

Search query state must preserve the following keys and semantics:

| Key | Type | Meaning | Default |
|---|---|---|---|
| `q` | string | search query text | `""` |
| `match` | enum | `pn` / `term` / `all` | `pn` on page init |
| `page` | int | current page index, starts from 1 | `1` |
| `include_notes` | bool flag | include note rows (`1` = true) | `false` |
| `source_dir` | string | relative source directory filter | `""` |
| `source_pdf` | string | relative source PDF filter | `""` |

### 1.3 API Contract Freeze (No Backend Semantic Changes)

The frontend rebuild must continue using existing endpoints:

- `GET /api/search`
- `GET /api/part/{id}`
- `GET /api/docs`
- `GET /api/docs/tree`
- `DELETE /api/docs`
- `POST /api/docs/batch-delete`
- `POST /api/import`
- `GET /api/import/jobs`
- `GET /api/import/{job_id}`
- `POST /api/folders`
- `POST /api/scan`
- `GET /api/scan/{job_id}`
- `GET /render/{pdf}/{page}.png`
- `GET /pdf/{name}`

### 1.4 Local Storage Compatibility

Legacy keys that must be preserved and migrated:

- `ipc_search_history`
- `ipc_favorites`

## 2) Visual Token Baseline

This design token set defines the approved visual direction:
- calm neutral greys
- single glacier teal accent
- thin borders
- small rounded corners
- balanced density
- premium minimalism

### 2.1 Color Tokens

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#F5F7F6` | app background |
| `--surface` | `#FFFFFF` | main panel/card |
| `--surface-soft` | `#F1F4F2` | subtle secondary panel |
| `--border` | `#D8DFDB` | default border |
| `--text` | `#101416` | primary text |
| `--text-muted` | `#5E676D` | secondary text |
| `--accent` | `#2F7A6C` | primary interactive accent |
| `--accent-hover` | `#255F54` | accent hover state |
| `--accent-soft` | `#E7F1EE` | soft accent background |
| `--danger` | `#B45555` | destructive actions only |

### 2.2 Typography Tokens

| Token | Value |
|---|---|
| `--font-sans` | `"Inter", "Noto Sans SC", "PingFang SC", "Segoe UI", system-ui, sans-serif` |
| `--font-mono` | `"JetBrains Mono", "SFMono-Regular", ui-monospace, Menlo, Consolas, monospace` |

### 2.3 Sizing and Rhythm Tokens

| Token | Value |
|---|---|
| `--space-1` | `4px` |
| `--space-2` | `8px` |
| `--space-3` | `12px` |
| `--space-4` | `16px` |
| `--space-5` | `20px` |
| `--space-6` | `24px` |
| `--space-8` | `32px` |
| `--radius-sm` | `8px` |
| `--radius-md` | `10px` |
| `--radius-lg` | `12px` |
| `--table-row-h` | `44px` |

### 2.4 Motion Tokens

| Token | Value |
|---|---|
| `--motion-fast` | `160ms ease-out` |
| `--motion-base` | `200ms ease-out` |

## 3) Icon Policy Freeze

- Emoji must not be used as UI icons.
- Use a single SVG icon set (Lucide) for consistency.
- Replace current emoji indicators:
  - folder/file emoji in DB tree
  - star glyph favorites (replace by icon component)
  - chevron text glyphs in expand/collapse controls

## 4) Breakpoint and Density Freeze (Phase 1)

Phase 1 is desktop-first and must be stable at:

- `1024`
- `1280`
- `1440`
- `1728`
- `1920`

Mobile advanced interactions (e.g. filter drawer) are out of scope for this phase.

## 5) Completion Definition for Each Part

A part is considered complete only when:

1. Code changes for that part are implemented.
2. Relevant regression checks for that part pass.
3. A git commit is created immediately with the agreed message pattern:
   - `feat(ui-partX): <part-name> - <key change>`
4. A short delivery note is provided including:
   - change scope
   - impacted pages
   - regression result
   - known risks (if any)
