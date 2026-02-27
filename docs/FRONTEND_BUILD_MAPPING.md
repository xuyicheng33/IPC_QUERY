# Frontend Build Mapping (Part 1)

This file documents the Vite multi-entry mapping used for static hosting compatibility.

## Input to Output Mapping

| Vite Input | Built HTML Output | Public URL |
|---|---|---|
| `frontend/index.html` | `web/index.html` | `/` |
| `frontend/search.html` | `web/search.html` | `/search` |
| `frontend/part.html` | `web/part.html` | `/part/{id}` |
| `frontend/db.html` | `web/db.html` | `/db` |
| `frontend/viewer.html` | `web/viewer.html` | `/viewer.html` |

## Notes

- Static alias routing remains on Python server side (`ipc_query/api/handlers.py`).
- Build output directory is configured as `../web` in `frontend/vite.config.ts`.
- `emptyOutDir=false` is used to avoid accidental deletion of legacy files during staged migration.
