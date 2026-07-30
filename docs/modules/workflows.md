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
  `workflows/presets/*.json`

The two root `FULLHD_*` files are legacy assets and are not part of the
fallback/preset contract.

## VAE And Frame Contract

Every fallback/preset workflow uses one `VAEDecodeTiled` node with:

```json
{
  "tile_size": 512,
  "overlap": 64,
  "temporal_size": 16,
  "temporal_overlap": 4
}
```

Every bundled workflow uses
`WanFirstLastFrameToVideo.length=61`. The three Jazz filenames still contain
`6s` for backward compatibility with saved frontend selections, but with RIFE
multiplier 2 and 24 fps their effective duration is about 5 seconds.

Regression test:

```powershell
python -m unittest tests.test_workflow_vae_config -v
```

## Runtime Evidence

- On 2026-07-30, the previous 73-frame fallback completed on GPU1/8188 after
  replacing regular VAE decode with temporally tiled decode.
- During tiled decode, sampled VRAM was about 5.3 GB instead of exhausting the
  32 GB GPU.
- A later 61-frame test coincided with exhaustion of the machine's 64 GB system
  RAM and native-crashed in `ucrtbase.dll` (`0xc0000409`) before producing
  history/output. The supervisor recovered correctly, but this attempt is not
  a successful render validation.
- On 2026-07-30, two fresh-seed 61-frame renders then completed consecutively
  on GPU1 without calling `/free`. The cold job took 351.3 seconds with
  12.22 GB minimum available RAM; the warm job took 290.7 seconds with
  15.71 GB minimum available RAM. Both produced MP4 output, PID `3228` stayed
  unchanged, and the queue returned to empty.

## Invariants

- Do not replace tiled decode with regular `VAEDecode` for Wan video presets.
- Do not raise bundled frame count above 61 without a measured RAM/VRAM test.
- Keep fallback and same-named preset as separate source files; both must be
  updated and tested.
- Preserve workflow API node IDs and existing links unless a migration is
  explicitly planned.
- Preserve ComfyUI's warm model cache between normal consecutive jobs; do not
  call `/free` after every completion.
