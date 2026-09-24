# UI System

## Current Shape

- Dark operational dashboard with fixed left sidebar, topbar, upload panel, and queue panel.
- Account Settings uses one bordered split workspace: password controls on the left and admin account management on the right; do not nest cards inside either section.
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
- Image sources in the creator panel are exclusive: choosing a local image
  disables the Drive link input; entering a Drive link disables the drop zone.
- The Drive input uses the compact `.creator-input` shape and a clear icon; the
  link must be shared with anyone who has the link.
- Modals should use a simple backdrop, centered panel, and direct controls.
- Settings and account-modal inputs use the login form shape: 46px height, 12px radius, charcoal fill, gray border, and green focus ring.
- Vietnamese UI text must remain UTF-8 and avoid all-caps transformations for long strings.
- Display worker names as `Máy 1` and `Máy 2`; keep `gpu1` and `gpu2` as
  backend/runtime identifiers only.
