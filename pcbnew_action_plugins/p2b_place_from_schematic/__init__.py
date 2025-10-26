import os
import re
import pcbnew
import wx
import math

# Keep a single modeless dialog instance alive
_DLG = None

# ============================ GUI ============================================

class P2BDialog(wx.Dialog):
    """Modeless control panel for placement."""

    def __init__(self, parent):
        wx.Dialog.__init__(
            self,
            parent,
            id=wx.ID_ANY,
            title="P2B placement",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
        )

        self.on_apply = None  # set by plugin

        root = wx.BoxSizer(wx.VERTICAL)
        pnl = wx.Panel(self)
        content = wx.BoxSizer(wx.VERTICAL)

        grid = wx.FlexGridSizer(rows=0, cols=2, vgap=6, hgap=10)
        grid.AddGrowableCol(1, 1)

        # Inputs
        self.t_x0   = wx.TextCtrl(pnl, value="50.0")
        self.t_y0   = wx.TextCtrl(pnl, value="50.0")
        self.t_w    = wx.TextCtrl(pnl, value="100.0")
        self.t_h    = wx.TextCtrl(pnl, value="80.0")

        # Scale: auto + slider 1..400 %
        self.cb_auto_scale = wx.CheckBox(pnl, label="Auto scale to fit")
        self.cb_auto_scale.SetValue(True)
        self.s_scale = wx.Slider(pnl, minValue=1, maxValue=100, value=30,
                                 style=wx.SL_HORIZONTAL | wx.SL_MIN_MAX_LABELS)
        self.s_scale.Enable(False)
        self.st_scale = wx.StaticText(pnl, label="Scale: 100 %")

        # Rotation consideration
        self.cb_use_rot = wx.CheckBox(pnl, label="Consider rotation from schematic")
        self.cb_use_rot.SetValue(False)

        # Selection + collisions
        self.cb_only_sel = wx.CheckBox(pnl, label="Only selected footprints")
        self.cb_avoid_col = wx.CheckBox(pnl, label="Avoid collisions")
        self.cb_avoid_col.SetValue(True)
        self.t_clearance = wx.TextCtrl(pnl, value="0.05")  # mm
        self.t_step      = wx.TextCtrl(pnl, value="1.0")  # mm (grid step)

        def row(lbl, ctrl):
            grid.Add(wx.StaticText(pnl, label=lbl), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND)

        row("Origin X (mm):", self.t_x0)
        row("Origin Y (mm):", self.t_y0)
        row("Area width (mm):", self.t_w)
        row("Area height (mm):", self.t_h)

        # Scale row: auto + slider + label
        hsc = wx.BoxSizer(wx.HORIZONTAL)
        hsc.Add(self.cb_auto_scale, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        hsc.Add(self.s_scale, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        hsc.Add(self.st_scale, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(pnl, label="Scale:"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(hsc, 1, wx.EXPAND)

        # Rotation row
        grid.Add(wx.StaticText(pnl, label="Orientation:"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.cb_use_rot, 0, wx.ALIGN_LEFT)

        # Selection + collisions row
        selcol = wx.BoxSizer(wx.HORIZONTAL)
        selcol.Add(self.cb_only_sel, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 16)
        selcol.Add(self.cb_avoid_col, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(pnl, label="Scope / collisions:"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(selcol, 0, wx.ALIGN_LEFT | wx.EXPAND)

        # Optimiser: try small dθ/dpos locally on collision
        self.cb_opt = wx.CheckBox(pnl, label="Optimiser (local search)")
        self.cb_opt.SetValue(False)
        self.t_rotstep = wx.TextCtrl(pnl, value="0")  # degrees for ±dθ
        optrow = wx.BoxSizer(wx.HORIZONTAL)
        optrow.Add(self.cb_opt, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 16)
        optrow.Add(wx.StaticText(pnl, label="Δθ (deg):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        optrow.Add(self.t_rotstep, 0)
        grid.Add(wx.StaticText(pnl, label="Optimiser:"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(optrow, 0, wx.ALIGN_LEFT)


        # Collision parameters
        colp = wx.BoxSizer(wx.HORIZONTAL)
        colp.Add(wx.StaticText(pnl, label="Clearance (mm):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        colp.Add(self.t_clearance, 0, wx.RIGHT, 16)
        colp.Add(wx.StaticText(pnl, label="Grid step (mm):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        colp.Add(self.t_step, 0)
        grid.Add(wx.StaticText(pnl, label="Placement grid:"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(colp, 0, wx.ALIGN_LEFT)

        content.Add(grid, 0, wx.ALL | wx.EXPAND, 12)

        # Buttons: Apply + Close
        btnrow = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_apply = wx.Button(pnl, wx.ID_APPLY, "Apply")
        self.btn_close = wx.Button(pnl, wx.ID_CLOSE, "Close")
        btnrow.AddStretchSpacer(1)
        btnrow.Add(self.btn_apply, 0, wx.RIGHT, 8)
        btnrow.Add(self.btn_close, 0)
        content.Add(btnrow, 0, wx.ALL | wx.EXPAND, 10)

        pnl.SetSizer(content)
        root.Add(pnl, 1, wx.ALL | wx.EXPAND, 0)
        self.SetSizer(root)
        self.SetInitialSize(wx.Size(580, 420))
        self.SetMinSize(wx.Size(520, 360))
        self.Layout()
        self.CentreOnParent()

        # Events
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.btn_close.Bind(wx.EVT_BUTTON, self._on_close)
        self.btn_apply.Bind(wx.EVT_BUTTON, self._on_apply_clicked)
        self.cb_auto_scale.Bind(wx.EVT_CHECKBOX, self._on_auto_scale)
        self.s_scale.Bind(wx.EVT_SLIDER, self._on_scale_changed)

    def _on_close(self, evt=None):
        global _DLG
        _DLG = None
        try:
            self.Destroy()
        except Exception:
            pass

    def _on_auto_scale(self, evt):
        auto = self.cb_auto_scale.GetValue()
        self.s_scale.Enable(not auto)
        self._on_scale_changed(None)

    def _on_scale_changed(self, evt):
        self.st_scale.SetLabel(f"Scale: {self.s_scale.GetValue()} %")
        self._on_apply_clicked(None)

    def _on_apply_clicked(self, evt):
        if callable(self.on_apply):
            self.on_apply(self.params())

    def params(self):
        def f(x): return float(x.strip())
        x0 = f(self.t_x0.GetValue())
        y0 = f(self.t_y0.GetValue())
        w  = f(self.t_w.GetValue())
        h  = f(self.t_h.GetValue())
        auto_scale = self.cb_auto_scale.GetValue()
        scale = None if auto_scale else (self.s_scale.GetValue() / 100.0)
        only_sel = self.cb_only_sel.GetValue()
        avoid_col = self.cb_avoid_col.GetValue()
        clr = f(self.t_clearance.GetValue())
        step = f(self.t_step.GetValue())
        use_rot = self.cb_use_rot.GetValue()
        use_rot = self.cb_use_rot.GetValue()
        optimise = self.cb_opt.GetValue()
        rot_step_deg = float(self.t_rotstep.GetValue().strip())
        return dict(
            x0=x0, y0=y0, w=w, h=h,
            scale=scale, auto_scale=auto_scale,
            only_selected=only_sel,
            avoid_collisions=avoid_col,
            clearance_mm=clr, step_mm=step,
            use_rotation=use_rot,
            optimise=optimise,
            rot_step_deg=rot_step_deg
        )

# ===================== Schematic parsing (unchanged logic) ===================

_AT_RE = re.compile(r'\(at\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(?:\s+(-?\d+(?:\.\d+)?))?\s*\)')
_REF_PROP_RE = re.compile(r'\(property\s+"Reference"\s+"([^"]+)"')
_SHEETFILE_PROP_RE = re.compile(r'\(property\s+"Sheet\s*file"\s+"([^"]+)"\)|\(property\s+"Sheetfile"\s+"([^"]+)"\)')

def _iter_blocks(contents: str, head: str):
    n = len(contents); i = 0; in_quote = False
    while i < n:
        c = contents[i]
        if c == '"':
            in_quote = not in_quote; i += 1; continue
        if not in_quote and c == '(':
            if contents.startswith(head, i+1) and (i+1+len(head) < n and contents[i+1+len(head)] in " \n\t\r)"):
                depth = 0; j = i; k = i
                while k < n:
                    ch = contents[k]
                    if ch == '"':
                        k += 1
                        while k < n:
                            ch2 = contents[k]
                            if ch2 == '"' and contents[k-1] != '\\': break
                            k += 1
                        k += 1; continue
                    if ch == '(': depth += 1
                    elif ch == ')':
                        depth -= 1
                        if depth == 0:
                            j = k + 1
                            yield (i, j, contents[i:j]); break
                    k += 1
                i = j; continue
        i += 1

def _extract_sheet_files(block: str):
    out = []
    for m in _SHEETFILE_PROP_RE.finditer(block):
        fname = m.group(1) or m.group(2)
        if fname: out.append(fname)
    return out

def _extract_symbol_ref_at(block: str):
    rm = _REF_PROP_RE.search(block)
    am = _AT_RE.search(block)
    if not (rm and am): return None
    ref = rm.group(1).strip()
    x = float(am.group(1)); y = float(am.group(2))
    rot = am.group(3); rot = float(rot) if rot is not None else None
    return (ref, x, y, rot)

def _read_schematic_symbols(root_sch_path: str):
    out = {}; visited = set()
    def visit(path: str):
        ap = os.path.abspath(path)
        if ap in visited or not os.path.exists(ap): return
        visited.add(ap)
        with open(ap, "r", encoding="utf-8") as f: contents = f.read()
        for _, _, blk in _iter_blocks(contents, "symbol"):
            rec = _extract_symbol_ref_at(blk)
            if rec:
                ref, x, y, rot = rec
                out[ref] = (x, y, rot)
        this_dir = os.path.dirname(ap)
        for _, _, sblk in _iter_blocks(contents, "sheet"):
            for child in _extract_sheet_files(sblk):
                visit(os.path.join(this_dir, child))
    visit(root_sch_path)
    return out

# ===================== Placement core =======================================

def _bbox_with_clearance(fp, clr_nm):
    try:
        bb = fp.GetBoundingBox(False)  # axis-aligned, accounts for rotation
    except:
        bb = fp.GetFootprintRect()
    bb.Inflate(clr_nm, clr_nm)
    return bb

def _grid_pack_without_overlap(fp, target_nm, placed_rects, clr_nm, step_nm, area_rect):
    """
    Place 'fp' starting near target_nm, scanning a grid inside 'area_rect':
    left->right in 'step_nm' increments; wrap to next row on overflow.
    Returns True if placed; False otherwise.
    """
    # Grid origin and limits
    ax0, ay0 = area_rect.GetPosition().x, area_rect.GetPosition().y
    ax1, ay1 = area_rect.GetEnd().x,       area_rect.GetEnd().y

    # Snap target to grid
    def snap(v, base):
        if step_nm <= 0: return v
        off = (v - base) % step_nm
        return v - off

    start_x = max(ax0, snap(target_nm.x, ax0))
    start_y = max(ay0, snap(target_nm.y, ay0))

    y = start_y
    max_rows = max(1, int((ay1 - ay0) // max(step_nm, 1)))
    max_cols = max(1, int((ax1 - ax0) // max(step_nm, 1)))

    rows_tried = 0
    while y <= ay1 and rows_tried <= max_rows:
        x = start_x
        cols_tried = 0
        while x <= ax1 and cols_tried <= max_cols:
            fp.SetPosition(pcbnew.VECTOR2I(x, y))
            bb = _bbox_with_clearance(fp, clr_nm)
            # Fully inside area?
            if not (area_rect.Contains(bb.GetPosition()) and area_rect.Contains(bb.GetEnd())):
                x += step_nm; cols_tried += 1
                continue
            # Check overlaps
            collide = any(bb.Intersects(other) for other in placed_rects)
            if not collide:
                placed_rects.append(bb)
                return True
            x += step_nm; cols_tried += 1
        y += step_nm; rows_tried += 1

    return False


def _place_ok(fp, pos_nm, clr_nm, area_rect, placed_rects):
    """Return expanded bbox if inside area and no intersection; else None."""
    fp.SetPosition(pos_nm)
    bb = _bbox_with_clearance(fp, clr_nm)
    if not (area_rect.Contains(bb.GetPosition()) and area_rect.Contains(bb.GetEnd())):
        return None
    if any(bb.Intersects(o) for o in placed_rects):
        return None
    return bb

def _closest_nonoverlap_place(fp, target_nm, placed_rects, clr_nm, step_nm, area_rect,
                              optimise=False, rot_step_deg=10.0):
    """
    Try target; on collision, expand search radius and pick the nearest feasible position.
    If 'optimise' is True, also test small ±Δθ rotations and sub-step offsets locally and
    choose the candidate minimising distance to target.
    """
    # Save original orientation to avoid accumulating failed tries
    try:
        orig_deg = fp.GetOrientationDegrees()
    except Exception:
        orig_deg = None

    # 1) try target as-is
    bb = _place_ok(fp, target_nm, clr_nm, area_rect, placed_rects)
    if bb:
        placed_rects.append(bb)
        return True

    # Spiral/ring search: radius grows in 'step_nm'; sample 8 directions per ring
    ax0, ay0 = area_rect.GetPosition().x, area_rect.GetPosition().y
    ax1, ay1 = area_rect.GetEnd().x,       area_rect.GetEnd().y

    def dist2(v):
        dx = v.x - target_nm.x
        dy = v.y - target_nm.y
        return dx*dx + dy*dy

    # Candidate accumulator when optimiser=True (we pick best of local tries)
    best = None  # (dist2, pos_nm, bbox, chosen_deg)

    # reasonable cap to avoid UI stalls
    max_radius = int(max(ax1-ax0, ay1-ay0) // max(step_nm, 1)) + 1
    max_radius = min(max_radius, 1000)

    for r in range(1, max_radius+1):
        # Generate ring points (8-cardinal + diagonals) at radius r*step_nm
        delta = r * step_nm
        ring = [
            pcbnew.VECTOR2I(target_nm.x - delta, target_nm.y),     # W
            pcbnew.VECTOR2I(target_nm.x + delta, target_nm.y),     # E
            pcbnew.VECTOR2I(target_nm.x,         target_nm.y - delta), # N
            pcbnew.VECTOR2I(target_nm.x,         target_nm.y + delta), # S
            pcbnew.VECTOR2I(target_nm.x - delta, target_nm.y - delta), # NW
            pcbnew.VECTOR2I(target_nm.x + delta, target_nm.y - delta), # NE
            pcbnew.VECTOR2I(target_nm.x - delta, target_nm.y + delta), # SW
            pcbnew.VECTOR2I(target_nm.x + delta, target_nm.y + delta), # SE
        ]

        # Fast path: no optimiser → accept first feasible (closest by construction)
        if not optimise:
            for pos in ring:
                # keep original orientation for bbox consistency
                if orig_deg is not None:
                    try: fp.SetOrientationDegrees(orig_deg)
                    except Exception: pass
                bb = _place_ok(fp, pos, clr_nm, area_rect, placed_rects)
                if bb:
                    placed_rects.append(bb)
                    return True
            continue

        # Optimiser: for each ring point, also try ±Δθ and tiny sub-step nudges
        for pos in ring:
            # try orientation variants
            for ddeg in (0.0, +rot_step_deg, -rot_step_deg):
                if orig_deg is not None:
                    try: fp.SetOrientationDegrees(orig_deg + ddeg)
                    except Exception: pass

                # micro nudges at half-step in 4 dirs to densify packing
                half = max(1, step_nm // 2)
                for dx, dy in ((0,0), (half,0), (-half,0), (0,half), (0,-half)):
                    cand = pcbnew.VECTOR2I(pos.x + dx, pos.y + dy)
                    bb = _place_ok(fp, cand, clr_nm, area_rect, placed_rects)
                    if bb:
                        d2 = dist2(cand)
                        if (best is None) or (d2 < best[0]):
                            best = (d2, cand, bb, (orig_deg + ddeg) if orig_deg is not None else None)

        # If we found something at this radius, apply and stop (closest ring)
        if best is not None:
            _, cand_pos, cand_bb, chosen_deg = best
            if chosen_deg is not None:
                try: fp.SetOrientationDegrees(chosen_deg)
                except Exception: pass
            fp.SetPosition(cand_pos)
            placed_rects.append(cand_bb)
            return True

    # Restore orientation on failure
    if orig_deg is not None:
        try: fp.SetOrientationDegrees(orig_deg)
        except Exception: pass
    return False
# ===================== Action plugin ========================================

class P2B(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "P2B: Move Footprints from Schematic"
        self.category = "Place/Move"
        self.description = "Map symbol positions to PCB (scale/offset, selection, rotation, collision)"
        self.show_toolbar_button = True
        self.icon_file_name = ""

    def Run(self):
        board = pcbnew.GetBoard()
        if not board:
            return

        # Find schematic
        brd_path = board.GetFileName()
        prj_dir = os.path.dirname(brd_path)
        prj_name = os.path.splitext(os.path.basename(brd_path))[0]
        sch_path = os.path.join(prj_dir, f"{prj_name}.kicad_sch")
        if not os.path.exists(sch_path):
            cands = [p for p in os.listdir(prj_dir) if p.endswith(".kicad_sch")]
            if not cands:
                wx.MessageBox("No .kicad_sch in project dir.", "P2B"); return
            sch_path = os.path.join(prj_dir, cands[0])

        sympos = _read_schematic_symbols(sch_path)
        if not sympos:
            wx.MessageBox("No symbols found.", "P2B"); return

        # Parent for DPI/ownership
        parent = wx.GetTopLevelParent(pcbnew.GetBoardFrame()) if hasattr(pcbnew, "GetBoardFrame") else None

        global _DLG
        if _DLG and _DLG.IsShown():
            _DLG.Raise(); _DLG.SetFocus()
            return

        _DLG = P2BDialog(parent)
        _DLG.on_apply = lambda params: self._apply_placement(board, sympos, params)
        _DLG.CentreOnParent()
        _DLG.Show()  # modeless

    # ---------------------- placement apply ---------------------------------

    def _apply_placement(self, board, sympos, P):
        # ---- schematic bbox for (auto) scale -----------------------------------
        xs = [p[0] for p in sympos.values()]
        ys = [p[1] for p in sympos.values()]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        width  = max(1e-6, maxx - minx)
        height = max(1e-6, maxy - miny)

        scale = (min(P["w"] / width, P["h"] / height)) if P["scale"] is None else P["scale"]

        # ---- board + candidates -------------------------------------------------
        fps = list(board.GetFootprints())
        ref_to_fp = {fp.GetReference(): fp for fp in fps}
        allowed = {fp.GetReference() for fp in fps if fp.IsSelected()} if P["only_selected"] else None

        # prefilter candidates that exist on board and are not locked (+ selection)
        candidates = []
        for ref, (sxmm, symm, rot) in sympos.items():
            if allowed is not None and ref not in allowed:
                continue
            fp = ref_to_fp.get(ref)
            if not fp or fp.IsLocked():
                continue
            candidates.append((ref, sxmm, symm, rot))

        if not candidates:
            wx.LogMessage("P2B: no eligible footprints to place."); return

        # ---- ordering: seed = top-left (min y, then min x); others by distance ---
        seed = min(candidates, key=lambda t: (t[2], t[1], t[0]))  # (ref, x, y, rot)
        sx0, sy0 = seed[1], seed[2]

        def dist(t):
            dx = t[1] - sx0
            dy = t[2] - sy0
            return math.hypot(dx, dy)

        ordered = [seed] + sorted([t for t in candidates if t[0] != seed[0]], key=lambda t: (dist(t), t[0]))

        # ---- geometry & area ----------------------------------------------------
        x0_nm = pcbnew.FromMM(P["x0"])
        y0_nm = pcbnew.FromMM(P["y0"])
        w_nm  = pcbnew.FromMM(P["w"])
        h_nm  = pcbnew.FromMM(P["h"])
        clr_nm  = pcbnew.FromMM(P["clearance_mm"])
        step_nm = max(1, pcbnew.FromMM(P["step_mm"]))  # avoid zero

        area = pcbnew.BOX2I(
            pcbnew.VECTOR2I(x0_nm, y0_nm),
            pcbnew.VECTOR2I(x0_nm + w_nm, y0_nm + h_nm)
        )

        placed_rects = []
        placed = 0
        skipped = 0

        # ---- placement loop (seed-first, then by distance) ----------------------
        for ref, sxmm, symm, rot in ordered:
            fp = ref_to_fp.get(ref)
            if not fp:
                skipped += 1; continue

            # rotation first (affects bbox), if requested and present
            if P["use_rotation"] and rot is not None:
                try:
                    fp.SetOrientationDegrees(rot)
                except Exception:
                    pass

            # map normalised schematic coords into PCB area
            nx_mm = (sxmm - minx) * scale
            ny_mm = (symm - miny) * scale
            tx_nm = pcbnew.FromMM(P["x0"] + nx_mm)
            ty_nm = pcbnew.FromMM(P["y0"] + ny_mm)
            target = pcbnew.VECTOR2I(tx_nm, ty_nm)

            if P["avoid_collisions"]:
                ok = _closest_nonoverlap_place(
                    fp=fp,
                    target_nm=target,
                    placed_rects=placed_rects,
                    clr_nm=clr_nm,
                    step_nm=step_nm,
                    area_rect=area,
                    optimise=P.get("optimise", True),
                    rot_step_deg=P.get("rot_step_deg", 10.0)
                )
                if ok:
                    placed += 1
                else:
                    skipped += 1
            else:
                fp.SetPosition(target)
                placed += 1


        pcbnew.Refresh()
        # wx.LogMessage(f"P2B: placed {placed}, skipped {skipped}.")
        if skipped:
            wx.Bell()

# Register plugin
P2B().register()
