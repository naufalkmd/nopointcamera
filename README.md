# nopointcam

A see-through, Game Boy-style camera. Every shot is the same photo run through a random "camera setting", and the result prints on a paper frame.

Live design canvas: https://claude.ai/artifact/RhG4uLpNcWfXdtE1xg4fLm

## Folders

| Folder | What's in it |
| --- | --- |
| `design/` | The screens from the design canvas: `CameraBuilt` (the camera), `Print`, `MockupCompare` (on an iPhone), `Frame` (the print), `Photo` (the 8 looks), `SharePost`, `ShareStory`, `Treatments`, plus `canvas.json` (board layout). |
| `assets/` | Every image the screens use. |
| `assets/parts/` | Each 3D part as its own transparent PNG with its shadow, plus `manifest.json` giving its position on the 390×844 screen in CSS px. Use these if you want the board as separate layers in the real app. |
| `scripts/` | The code that makes every asset except the sample photo. |

The `design/` files are written for the claude.ai design canvas: they load its runtime (`support.js`), so they won't render if opened directly in a browser. Read them as the spec for layout, sizes, colours, animations and interactions. Their image paths point at `../assets/`; `design/artifact-asset-ids.json` maps each file back to its upload id on the canvas.

## Assets

| File | Used on | Notes |
| --- | --- | --- |
| `board.webp` / `board.png` | Camera | Circuit board with all the 3D parts, 410×864 CSS px (10px bleed on every side), 2× resolution |
| `dpad.png` | Camera | D-pad, shadow included |
| `button-ab.png` | Camera, Print | A/B button, shadow included |
| `button-select-start.png` | Camera, Print | SELECT/START pill, shadow included |
| `fan-blades.png` | Camera | Spins on top of the fan (CSS `rotate`), centred on the hub |
| `paper-texture.png` | Print frame | Paper grain, blended soft-light |
| `wall-texture.png` | Print, share images, mockup | Background wall, tiled at 512px |
| `grain.png` | Photo looks | Film grain overlay |
| `sample-photo.jpg` | Photo looks | Stand-in for the live camera feed. This is the only AI-generated image (made with Replicate). |

The stickers, the shell, the bezel and the speaker are inline SVG/CSS in `design/CameraBuilt.dc.html`. The logo font (Bagel Fat One) loads from Google Fonts.

## Regenerating

Needs Python 3 with `numpy` and `pillow`. The printed labels on the parts use macOS system fonts. Output goes to `scripts/out/`.

```sh
cd scripts
python3 make_textures.py         # paper, wall, grain         -> out/textures/
python3 parts2.py controls       # d-pad, A/B, SELECT/START   -> out/parts/
python3 parts2.py layout         # every board part + manifest -> out/parts/
python3 compose_board.py         # the full board             -> out/np-board.png / .webp
python3 mock.py                  # rough layout preview       -> out/mock-lower.png
```

To move, resize or turn a part, edit `PLACES` in `parts2.py`: name, centre x, centre y, px per unit, yaw in degrees. Materials, labels and lighting are in `parts2.py` and `render2.py`. If you move the fan, the googly eyes or the disco ball, also update the fan-blade, pupil and sparkle positions in `CameraBuilt.dc.html`; `parts2.py layout` prints the new fan and pupil positions into the manifest.
