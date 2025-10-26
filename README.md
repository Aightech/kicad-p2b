# README.md
# P2B — Place From Schematic

**What it does**  
Maps schematic symbol positions to PCB footprints, keeping parts collision-free. Optional rotation from schematic, selection-only mode, modeless GUI, and a local optimiser to tuck parts as close as possible to their targets without overlap.

**Features**
- Modeless control panel with:
  - Origin/area and scale (auto or slider 1–400 %).
  - “Only selected footprints”.
  - “Consider rotation”.
  - Collision avoidance with clearance and grid step.
  - Optimiser: small position and rotation deltas to reduce target distance.
- Ordering: seed = top-left symbol, then increasing Euclidean distance.
- Hierarchy: parses all sheets recursively.
- Respect locked footprints; skips DNP if you filter them upstream.

**Requirements**
- KiCad 9.x (PCB Editor with Python enabled).
- Linux/macOS/Windows; tested on Ubuntu 22.04+.

**Install (manual)**
1. Create folder:
   - Linux: `~/.local/share/kicad/9.0/pcbnew/plugins/p2b_place_from_schematic/`
   - macOS: `~/Library/Preferences/kicad/9.0/pcbnew/plugins/p2b_place_from_schematic/`
   - Windows: `%APPDATA%\kicad\9.0\pcbnew\plugins\p2b_place_from_schematic\`
2. Copy:
   - `__init__.py` (plugin code)
   - `icon.png` (optional)
   - `VERSION` (e.g., `0.1.0`)
3. Restart PCB Editor, or rescan plugins.
4. Run via **Tools → External Plugins → P2B: Move Footprints from Schematic**.

**Usage**
1. Open your board. Ensure the project’s top-level `.kicad_sch` is present.
2. Open **P2B** (toolbar button or menu).
3. Set area/scale. Tick options as needed.
4. Click **Apply**. The panel stays open; you can keep editing the PCB.

**Notes**
- Coordinates are mapped linearly from schematic mm into the chosen PCB area.
- Rotation is applied before collision tests when enabled.
- For very dense designs, increase grid step a little and/or enable the optimiser.

**Limitations**
- No per-sheet offset rules yet (planned).
- Does not alter board outline or keepouts; only footprint poses.

**Troubleshooting**
- “No .kicad_sch” → ensure the top schematic is in the project folder.
- “No symbols found” → schematic must be KiCad v6+ S-expr format.
- Collisions persisting → raise clearance or grid step; enable optimiser.

**License**
MIT (see `LICENSE`).

**Credits**
Author: Alexis Devillard (`@Aightech`)

