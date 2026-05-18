# -*- coding: utf-8 -*-

import math
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget
from language_manager import get_language
from ui_localization import translate_text

HAS_MATPLOTLIB = True
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle
    import numpy as np
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
except Exception:
    HAS_MATPLOTLIB = False
    FigureCanvas = None
    NavigationToolbar = None
    Figure = None
    Rectangle = None
    np = None
    Poly3DCollection = None


class LiveView(QWidget):
    """Split live view with independent left/right canvases."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(3, 3, 3, 3)
        root.setSpacing(2)

        if not HAS_MATPLOTLIB:
            return

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(5)
        root.addWidget(self.splitter)

        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(2, 2, 2, 2)
        self.left_fig = Figure(figsize=(3.8, 4.4), tight_layout=True)
        self.left_canvas = FigureCanvas(self.left_fig)
        self.left_layout.addWidget(self.left_canvas)
        self.left_panel.setMinimumWidth(240)
        self.splitter.addWidget(self.left_panel)

        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(2, 2, 2, 2)
        self.right_fig = Figure(figsize=(4.2, 4.4), tight_layout=True)
        self.right_canvas = FigureCanvas(self.right_fig)
        self.toolbar = NavigationToolbar(self.right_canvas, self.right_panel)
        self.right_layout.addWidget(self.toolbar)
        self.right_layout.addWidget(self.right_canvas)
        self.right_panel.setMinimumWidth(300)
        self.splitter.addWidget(self.right_panel)

        self.splitter.setChildrenCollapsible(False)
        self._gizmo_motion_cid = None
        self._gizmo_release_cid = None
        self._gizmo_scroll_cid = None
        self._gizmo_axes = None
        self._apply_split_ratio()

        self.render_title_only()

    def _apply_split_ratio(self):
        self.splitter.setStretchFactor(0, 47)
        self.splitter.setStretchFactor(1, 53)
        total = max(self.width(), 1000)
        self.splitter.setSizes([int(total * 0.47), int(total * 0.53)])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if HAS_MATPLOTLIB and hasattr(self, "splitter"):
            self._apply_split_ratio()

    def _default_palette(self) -> Dict[str, str]:
        return {
            "API Sand": "#f7e7a8",
            "API Clay": "#e8c7cf",
            "Drilled Sand": "#fde2b8",
            "Drilled Clay": "#d9cde8",
            "Elastic": "#cfe6e8",
            "Sand": "#fde2b8",
            "Soft Clay Soil": "#e8c7cf",
            "API Method for Sand": "#f7e7a8",
            "Submerged Stiff Clay": "#d9cde8",
            "Dry Stiff Clay": "#d6e8cf",
            "Modified Stiff Clay without Free Water": "#cfe1e8",
            "Weak Rock": "#dcd6cf",
        }

    @staticmethod
    def _tr(text: str) -> str:
        return str(translate_text(text, get_language()))

    def _material_color(self, layer: Dict, mat_map: Dict[str, Dict]) -> str:
        mat_name = str(layer.get("material_name", ""))
        m = mat_map.get(mat_name, {})
        color = str(m.get("bg_color", "")).strip() or str(layer.get("bg_color", "")).strip()
        if color:
            return color
        axial = m.get("axial", {}) if isinstance(m.get("axial"), dict) else {}
        lateral = m.get("lateral", {}) if isinstance(m.get("lateral"), dict) else {}
        soil_type = str(
            m.get("soil_type", "")
            or m.get("axial_type", "")
            or m.get("lateral_type", "")
            or axial.get("soil_type", "")
            or lateral.get("soil_type", "")
            or layer.get("soil_type", "")
        )
        return self._default_palette().get(soil_type, "#dfe8d8")

    def _material_alpha(self, layer: Dict, mat_map: Dict[str, Dict], default_alpha: float = 0.28) -> float:
        mat_name = str(layer.get("material_name", ""))
        m = mat_map.get(mat_name, {})
        try:
            return float(m.get("bg_alpha", layer.get("bg_alpha", default_alpha)))
        except Exception:
            return default_alpha

    def _layer_ranges(self, payload: Dict) -> List[Dict]:
        layers = []
        for row in payload.get("layers", []):
            if not isinstance(row, dict):
                continue
            z_top = abs(float(row.get("z_top", 0.0)))
            z_bottom = abs(float(row.get("z_bottom", 0.0)))
            layers.append(
                {
                    "z_top": min(z_top, z_bottom),
                    "z_bottom": max(z_top, z_bottom),
                    "material_name": str(row.get("material_name", "")),
                    "soil_type": str(row.get("soil_type", "")),
                }
            )
        layers.sort(key=lambda x: x["z_top"])
        return layers

    def _disconnect_gizmo_events(self):
        for cid_name in ("_gizmo_motion_cid", "_gizmo_release_cid", "_gizmo_scroll_cid"):
            cid = getattr(self, cid_name, None)
            if cid is not None:
                try:
                    self.right_canvas.mpl_disconnect(cid)
                except Exception:
                    pass
                setattr(self, cid_name, None)

    def _add_orientation_gizmo(self, ax_main):
        self._disconnect_gizmo_events()
        gizmo = self.right_fig.add_axes([0.03, 0.03, 0.14, 0.14], projection="3d")
        self._gizmo_axes = gizmo
        gizmo.set_axis_off()
        try:
            gizmo.set_box_aspect((1.0, 1.0, 1.0))
        except Exception:
            pass
        gizmo.set_xlim(0.0, 1.0)
        gizmo.set_ylim(0.0, 1.0)
        gizmo.set_zlim(0.0, 1.0)
        gizmo.quiver(0, 0, 0, 0.75, 0, 0, color="r", arrow_length_ratio=0.18, linewidth=1.5)
        gizmo.quiver(0, 0, 0, 0, 0.75, 0, color="b", arrow_length_ratio=0.18, linewidth=1.5)
        gizmo.quiver(0, 0, 0, 0, 0, 0.75, color="g", arrow_length_ratio=0.18, linewidth=1.5)
        gizmo.text(0.84, 0, 0, "X", color="r", fontsize=9)
        gizmo.text(0, 0.84, 0, "Y", color="b", fontsize=9)
        gizmo.text(0, 0, 0.84, "Z", color="g", fontsize=9)
        gizmo.view_init(elev=ax_main.elev, azim=ax_main.azim)

        def _sync_gizmo(_event=None):
            if self._gizmo_axes is not gizmo:
                return
            try:
                gizmo.view_init(elev=ax_main.elev, azim=ax_main.azim)
                self.right_canvas.draw_idle()
            except Exception:
                pass

        self._gizmo_motion_cid = self.right_canvas.mpl_connect(
            "motion_notify_event",
            lambda event: _sync_gizmo() if event.inaxes == ax_main else None,
        )
        self._gizmo_release_cid = self.right_canvas.mpl_connect("button_release_event", _sync_gizmo)
        self._gizmo_scroll_cid = self.right_canvas.mpl_connect("scroll_event", _sync_gizmo)

    def _prepare_axes(self):
        if not HAS_MATPLOTLIB:
            return None, None

        self._disconnect_gizmo_events()
        self._gizmo_axes = None
        self.left_fig.clear()
        ax_left = self.left_fig.add_subplot(111)
        self.right_fig.clear()
        ax_right = self.right_fig.add_subplot(111, projection="3d")
        return ax_left, ax_right

    def render_title_only(self):
        if not HAS_MATPLOTLIB:
            return
        self._disconnect_gizmo_events()
        self._gizmo_axes = None

        self.left_fig.clear()
        ax_left = self.left_fig.add_subplot(111)
        ax_left.set_title(self._tr("Soil Layer Column"))
        ax_left.set_axis_off()
        self.left_canvas.draw_idle()

        self.right_fig.clear()
        ax_right = self.right_fig.add_subplot(111)
        ax_right.set_title(self._tr("3D Pile and Layered Soil"))
        ax_right.set_axis_off()
        self.right_canvas.draw_idle()

    def render_axial(self, payload: Dict):
        if not HAS_MATPLOTLIB:
            return
        if not payload or not payload.get("layers"):
            self.render_title_only()
            return

        layers = self._layer_ranges(payload)
        materials = payload.get("soil_materials")
        if not isinstance(materials, list):
            materials = payload.get("materials", [])
        mat_map = {str(m.get("name", "")): m for m in materials if isinstance(m, dict)}
        pile_top_z = float(payload.get("pile_top_z_m", 0.0))
        pile_bottom_z = float(payload.get("pile_bottom_z_m", pile_top_z - float(payload.get("pile_length_m", 1.0))))
        pile_len = max(abs(pile_top_z - pile_bottom_z), 1.0e-8)
        pile_d = float(payload.get("pile_diameter_m", 0.5))

        ax_left, ax_3d = self._prepare_axes()
        if ax_left is None:
            return

        x0, width = 0.2, 0.55
        for layer in layers:
            zt, zb = layer["z_top"], layer["z_bottom"]
            color = self._material_color(layer, mat_map)
            alpha = self._material_alpha(layer, mat_map, 0.65)
            ax_left.add_patch(
                Rectangle((x0, zt), width, max(zb - zt, 0.0), facecolor=color, alpha=alpha, edgecolor="#333333", linewidth=0.8)
            )
        max_depth = max(max((l["z_bottom"] for l in layers), default=1.0), max(-pile_bottom_z, 0.0))
        key_ticks = [0.0]
        for layer in layers:
            zb = float(layer["z_bottom"])
            if zb not in key_ticks:
                key_ticks.append(zb)
        if max_depth not in key_ticks:
            key_ticks.append(max_depth)
        ax_left.set_xlim(0.0, 1.0)
        ax_left.set_ylim(max_depth, 0.0)
        ax_left.set_xticks([])
        ax_left.set_yticks(sorted(set(key_ticks)))
        ax_left.set_ylabel(self._tr("Depth From Ground Line (m)"))
        ax_left.set_title(self._tr("Soil Layer Column"))
        ax_left.grid(False)
        self.left_canvas.draw_idle()

        box_half = max(1.5, pile_d * 6.0)
        for layer in layers:
            zt = -layer["z_top"]
            zb = -layer["z_bottom"]
            color = self._material_color(layer, mat_map)
            alpha = self._material_alpha(layer, mat_map, 0.20)
            faces = [[(-box_half, -box_half, zb), (box_half, -box_half, zb), (box_half, box_half, zb), (-box_half, box_half, zb)]]
            if abs(zt) > 1.0e-8:
                faces.append([(-box_half, -box_half, zt), (box_half, -box_half, zt), (box_half, box_half, zt), (-box_half, box_half, zt)])
            side_faces = [
                [(-box_half, -box_half, zt), (box_half, -box_half, zt), (box_half, -box_half, zb), (-box_half, -box_half, zb)],
                [(box_half, -box_half, zt), (box_half, box_half, zt), (box_half, box_half, zb), (box_half, -box_half, zb)],
                [(box_half, box_half, zt), (-box_half, box_half, zt), (-box_half, box_half, zb), (box_half, box_half, zb)],
                [(-box_half, box_half, zt), (-box_half, -box_half, zt), (-box_half, -box_half, zb), (-box_half, box_half, zb)],
            ]
            ax_3d.add_collection3d(
                Poly3DCollection(side_faces + faces, facecolors=color, alpha=alpha, edgecolors="#994444", linewidths=0.35)
            )

        radius = max(pile_d * 0.28, 0.03)
        theta = [2.0 * math.pi * i / 39.0 for i in range(40)]
        xs, ys, zs = [], [], []
        for z in [pile_top_z, pile_bottom_z]:
            xs.append([radius * math.cos(t) for t in theta])
            ys.append([radius * math.sin(t) for t in theta])
            zs.append([z for _ in theta])
        ax_3d.plot_surface(np.array(xs), np.array(ys), np.array(zs), color="#e8bcbc", alpha=0.95, linewidth=0, shade=True)

        depth_limit = max(max((l["z_bottom"] for l in layers), default=pile_len), max(-pile_bottom_z, 0.0))
        top_limit = max(pile_top_z + max(1.0, pile_d * 1.2), 0.0)
        ax_3d.set_xlim(-box_half, box_half)
        ax_3d.set_ylim(-box_half, box_half)
        ax_3d.set_zlim(-depth_limit, top_limit)
        try:
            ax_3d.set_box_aspect((box_half * 2.0, box_half * 2.0, depth_limit + top_limit))
        except Exception:
            pass
        ax_3d.set_xticks([])
        ax_3d.set_yticks([])
        ax_3d.set_zticks([])
        ax_3d.set_title(self._tr("3D Pile and Layered Soil"), pad=4)
        ax_3d.view_init(elev=20, azim=-56)
        ax_3d.grid(False)
        ax_3d.set_axis_off()
        self._add_orientation_gizmo(ax_3d)
        self.right_canvas.draw_idle()

    def render_group(self, payload: Dict):
        if not HAS_MATPLOTLIB:
            return
        if not payload or not payload.get("layers"):
            self.render_title_only()
            return

        layers = self._layer_ranges(payload)
        materials = payload.get("materials", [])
        mat_map = {str(m.get("name", "")): m for m in materials if isinstance(m, dict)}

        ax_left, ax_3d = self._prepare_axes()
        if ax_left is None:
            return

        x0, width = 0.2, 0.55
        max_depth = max(abs(float(layer.get("z_bottom", 0.0))) for layer in layers) if layers else 1.0
        for layer in layers:
            zt = abs(float(layer["z_top"]))
            zb = abs(float(layer["z_bottom"]))
            color = self._material_color(layer, mat_map)
            alpha = self._material_alpha(layer, mat_map, 0.65)
            ax_left.add_patch(
                Rectangle((x0, zt), width, max(zb - zt, 0.0), facecolor=color, alpha=alpha, edgecolor="#333333", linewidth=0.8)
            )
        ax_left.set_xlim(0.0, 1.0)
        ax_left.set_ylim(max_depth, 0.0)
        ax_left.set_xticks([])
        key_ticks = [0.0]
        for layer in layers:
            zb = abs(float(layer["z_bottom"]))
            if zb not in key_ticks:
                key_ticks.append(zb)
        ax_left.set_yticks(sorted(set(key_ticks)))
        ax_left.set_ylabel(self._tr("Depth From Ground Line (m)"))
        ax_left.set_title(self._tr("Soil Layer Column"))
        ax_left.grid(False)
        self.left_canvas.draw_idle()

        cap = payload.get("cap", {})
        pile_layout = payload.get("pile_layout", [])
        pile_types = {str(p.get("name", "")): p for p in payload.get("pile_types", []) if isinstance(p, dict)}

        cap_lx = float(cap.get("length_x_m", 6.0))
        cap_ly = float(cap.get("length_y_m", 6.0))
        cap_h = float(cap.get("height_m", 1.0))
        cap_center_z = float(cap.get("center_z_m", cap_h * 0.5))
        cap_top = cap_center_z + cap_h * 0.5
        cap_bottom = cap_center_z - cap_h * 0.5
        pile_tops = []
        pile_bottoms = []
        for row in pile_layout:
            if not isinstance(row, dict):
                continue
            pile_type = pile_types.get(str(row.get("pile_type_name", "")), {})
            pile_tops.append(float(row.get("top_z_m", pile_type.get("pile_top_z_m", 0.0))))
            pile_bottoms.append(float(row.get("bottom_z_m", pile_type.get("pile_bottom_z_m", -1.0))))

        box_half_x = max(cap_lx * 0.56, max([abs(float(r.get("x_m", 0.0))) for r in pile_layout] + [0.0]) + 1.2, 2.5)
        box_half_y = max(cap_ly * 0.56, max([abs(float(r.get("y_m", 0.0))) for r in pile_layout] + [0.0]) + 1.2, 2.5)
        depth_limit = max(
            [abs(float(layer.get("z_bottom", 0.0))) for layer in layers] + [abs(cap_bottom)] + [abs(v) for v in pile_bottoms] + [1.0]
        )
        top_limit = max([0.0, cap_top] + pile_tops + [1.0])

        for layer in layers:
            z_top_plot = -float(layer["z_top"])
            z_bot_plot = -float(layer["z_bottom"])
            color = self._material_color(layer, mat_map)
            alpha = self._material_alpha(layer, mat_map, 0.18)
            faces = [
                [(-box_half_x, -box_half_y, z_bot_plot), (box_half_x, -box_half_y, z_bot_plot), (box_half_x, box_half_y, z_bot_plot), (-box_half_x, box_half_y, z_bot_plot)],
                [(-box_half_x, -box_half_y, z_top_plot), (box_half_x, -box_half_y, z_top_plot), (box_half_x, -box_half_y, z_bot_plot), (-box_half_x, -box_half_y, z_bot_plot)],
                [(box_half_x, -box_half_y, z_top_plot), (box_half_x, box_half_y, z_top_plot), (box_half_x, box_half_y, z_bot_plot), (box_half_x, -box_half_y, z_bot_plot)],
                [(box_half_x, box_half_y, z_top_plot), (-box_half_x, box_half_y, z_top_plot), (-box_half_x, box_half_y, z_bot_plot), (box_half_x, box_half_y, z_bot_plot)],
                [(-box_half_x, box_half_y, z_top_plot), (-box_half_x, -box_half_y, z_top_plot), (-box_half_x, -box_half_y, z_bot_plot), (-box_half_x, box_half_y, z_bot_plot)],
            ]
            if abs(z_top_plot) > 1.0e-8:
                faces.insert(
                    0,
                    [(-box_half_x, -box_half_y, z_top_plot), (box_half_x, -box_half_y, z_top_plot), (box_half_x, box_half_y, z_top_plot), (-box_half_x, box_half_y, z_top_plot)],
                )
            ax_3d.add_collection3d(Poly3DCollection(faces, facecolors=color, alpha=alpha, edgecolors="#994444", linewidths=0.35))

        cap_faces = [
            [(-cap_lx / 2, -cap_ly / 2, cap_top), (cap_lx / 2, -cap_ly / 2, cap_top), (cap_lx / 2, cap_ly / 2, cap_top), (-cap_lx / 2, cap_ly / 2, cap_top)],
            [(-cap_lx / 2, -cap_ly / 2, cap_bottom), (cap_lx / 2, -cap_ly / 2, cap_bottom), (cap_lx / 2, cap_ly / 2, cap_bottom), (-cap_lx / 2, cap_ly / 2, cap_bottom)],
            [(-cap_lx / 2, -cap_ly / 2, cap_top), (cap_lx / 2, -cap_ly / 2, cap_top), (cap_lx / 2, -cap_ly / 2, cap_bottom), (-cap_lx / 2, -cap_ly / 2, cap_bottom)],
            [(cap_lx / 2, -cap_ly / 2, cap_top), (cap_lx / 2, cap_ly / 2, cap_top), (cap_lx / 2, cap_ly / 2, cap_bottom), (cap_lx / 2, -cap_ly / 2, cap_bottom)],
            [(cap_lx / 2, cap_ly / 2, cap_top), (-cap_lx / 2, cap_ly / 2, cap_top), (-cap_lx / 2, cap_ly / 2, cap_bottom), (cap_lx / 2, cap_ly / 2, cap_bottom)],
            [(-cap_lx / 2, cap_ly / 2, cap_top), (-cap_lx / 2, -cap_ly / 2, cap_top), (-cap_lx / 2, -cap_ly / 2, cap_bottom), (-cap_lx / 2, cap_ly / 2, cap_bottom)],
        ]
        ax_3d.add_collection3d(Poly3DCollection(cap_faces, facecolors="#d7d2c8", alpha=0.95, edgecolors="#666666", linewidths=0.7))

        theta = [2.0 * math.pi * i / 31.0 for i in range(32)]
        for row in pile_layout:
            if not isinstance(row, dict):
                continue
            pile_type = pile_types.get(str(row.get("pile_type_name", "")), {})
            x0 = float(row.get("x_m", 0.0))
            y0 = float(row.get("y_m", 0.0))
            top_z = float(row.get("top_z_m", pile_type.get("pile_top_z_m", 0.0)))
            bottom_z = float(row.get("bottom_z_m", pile_type.get("pile_bottom_z_m", -1.0)))
            diameter = float(pile_type.get("pile_diameter_m", 1.0))
            radius = max(diameter * 0.28, 0.03)
            xs, ys, zs = [], [], []
            for z in [top_z, bottom_z]:
                xs.append([x0 + radius * math.cos(t) for t in theta])
                ys.append([y0 + radius * math.sin(t) for t in theta])
                zs.append([z for _ in theta])
            ax_3d.plot_surface(np.array(xs), np.array(ys), np.array(zs), color="#e8bcbc", alpha=0.95, linewidth=0, shade=True)

        z_upper = max(top_limit + max(cap_h, 1.0) * 0.5, 0.8)
        ax_3d.set_xlim(-box_half_x, box_half_x)
        ax_3d.set_ylim(-box_half_y, box_half_y)
        ax_3d.set_zlim(-depth_limit, z_upper)
        try:
            ax_3d.set_box_aspect((box_half_x * 2.0, box_half_y * 2.0, depth_limit + z_upper))
        except Exception:
            pass
        ax_3d.set_xticks([])
        ax_3d.set_yticks([])
        ax_3d.set_zticks([])
        ax_3d.set_title(self._tr("3D Cap and Pile Group"), pad=4)
        ax_3d.view_init(elev=20, azim=-56)
        ax_3d.grid(False)
        ax_3d.set_axis_off()
        self._add_orientation_gizmo(ax_3d)
        self.right_canvas.draw_idle()
