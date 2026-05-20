# UI System

## Current Shape

- Dark operational dashboard with fixed left sidebar, topbar, upload panel, and queue panel.
- Static frontend lives in `static/index.html`, `static/style.css`, and `static/app.js`.
- Tailwind is loaded, but most app-specific UI is plain CSS custom properties.

## Tokens

- Backgrounds: `--surface-0` through `--surface-4`.
- Borders: `--stroke-soft`, `--stroke-mid`, `--stroke-strong`.
- Text: `--text-main`, `--text-muted`, `--text-subtle`.
- Primary accent: `--primary` green.
- Radii: `--radius-sm`, `--radius-md`, `--radius-lg`.

## Interaction Notes

- Keep controls compact and dense; avoid oversized decorative dashboard patterns.
- Buttons use existing `.btn`, `.btn-ghost`, `.btn-sm`, and `.btn-accent` styles.
- Modals should use a simple backdrop, centered panel, and direct controls.
- Vietnamese UI text must remain UTF-8 and avoid all-caps transformations for long strings.

