# Bundled Workflows

## Responsibility

- `config.WORKFLOW_PATH` supplies the fallback workflow when a user does not
  choose a preset.
- `config.WORKFLOW_PRESET_DIR` supplies the five bundled presets in production.
- Historical job workflows in `/data/workflows` are immutable runtime records
  and are not rewritten when bundled workflows change.

## Canonical Files

- Fallback:
  `workflows/Jazz & lofi 6s Khong Loop.json`
- Presets:
  - `Jazz & lofi 6s Co Loop.json`
  - `Jazz & lofi 6s Khong Loop.json`
  - `Kling Animation 5s Co Loop.json`
  - `Kling Animation 5s Khong Loop.json`
  - `Livewallpaper 5s Khong Loop.json`

The two root `FULLHD_*` files are legacy assets and are not part of the
fallback/preset contract.

## VAE And Frame Contract

- Every fallback/preset workflow uses exactly one regular `VAEDecode` node.
- Jazz fallback/presets use `WanFirstLastFrameToVideo.length=73` and are named
  `6s`.
- Kling and Livewallpaper presets use `length=61` and remain named `5s`.
- Web, Telegram and `build_prompt` preserve valid positive integer lengths at
  or below 73. Values above 73 are capped at 73; missing or invalid values
  default to 73.
- The two temporary Jazz `5s` names remain hidden aliases to the canonical
  `6s` files.

Regression test:

```powershell
python -m unittest tests.test_workflow_vae_config tests.test_workflow_guard -v
```

## Runtime Evidence

- A controlled GPU2 comparison used the same 73-frame latent, input and seed.
  `VAEDecodeTiled` produced brightness-delta p95 `5.4399`, while regular
  `VAEDecode` produced `0.2368`; the tiled result was about 23 times more
  variable and visibly flickered.
- Regular VAE completed successfully on GPU2 after the machine was upgraded to
  128 GB RAM. During the isolated decode validation, minimum available RAM was
  75.886 GiB, ComfyUI private memory peaked at 86.039 GiB, PID stayed stable and
  no OOM/native crash occurred.
- The 128 GB cold/warm 61-frame tests also retained at least 69.708 GiB
  available RAM. This confirms the earlier 64 GB failures were primarily
  system-RAM pressure during model/decode transitions.
- Preserve ComfyUI's warm model cache between normal consecutive jobs; do not
  call `/free` after every completion.

## Invariants

- Do not use `VAEDecodeTiled` in bundled video workflows while its temporal
  brightness discontinuity remains reproducible.
- Do not force a 5-second 61-frame workflow to 73 frames.
- Never accept more than 73 source frames through Web, Telegram or
  `build_prompt`.
- Keep fallback and same-named preset as separate source files; both must be
  updated and tested.
- Preserve workflow API node IDs and existing links unless a migration is
  explicitly planned.
- GPU workers intended for regular VAE production require 128 GB system RAM or
  equivalent measured headroom.
