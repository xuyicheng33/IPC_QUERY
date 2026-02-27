# Desktop Validation Checklist (Part 6)

This checklist tracks desktop-first layout validation for the Swiss Spa Precision rebuild.

## Target Desktop Widths

- 1024
- 1280
- 1440
- 1728
- 1920

## Adjustments Completed

- App shell max width expanded to 1360 and horizontal padding made responsive.
- Search filter grid changed to responsive columns (`1 -> 2 -> 5`) to avoid cramped controls.
- Search result text cells constrained with ellipsis to avoid table overflow.
- Detail metadata and hierarchy grids use `md/xl` breakpoints for balanced density.
- DB page switches to two-column split only at `xl`, keeping 1024 width readable.
- Viewer top controls and content container widened and responsive padded.

## Verification Notes

- Type safety: `npm run typecheck` passed.
- Build safety: `vite build` passed.
- Table overflow behavior is constrained by `overflow-x-auto` wrappers and cell truncation rules.

## Known Follow-up (Phase 7)

- Final artifact validation against built `web/` output after full migration build.
- Add optional screenshot-based regression check for desktop widths.
