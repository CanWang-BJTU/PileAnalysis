                      
                                                                         
                               
               
                    
                                                                         

from __future__ import annotations
import io
import math
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union, TYPE_CHECKING

CURRENT_DIR = Path(__file__).resolve().parent
MMETHOD_ROOT = CURRENT_DIR.parent
PROJECT_ROOT = MMETHOD_ROOT.parent
for extra_dir in (
    PROJECT_ROOT,
    PROJECT_ROOT / "language_settings",
):
    extra_path = str(extra_dir)
    if extra_dir.exists() and extra_path not in sys.path:
        sys.path.insert(0, extra_path)

try:
    from language_manager import get_language
except Exception:
    def get_language():
        return "en"

logger = logging.getLogger(__name__)


def _plot_text(text: str) -> str:
    if get_language() != "en" or not isinstance(text, str):
        return text

    mapping = {
        "桩基平面布置图": "Pile Foundation Plan Layout",
        "平面布置图": "Plan Layout",
        "桩位布置": "Pile Layout",
        "X-纵向 (m)": "X-Longitudinal (m)",
        "Y-横向 (m)": "Y-Transverse (m)",
        "轴力 Nz (kN)": "Axial Force Nz (kN)",
        "深度 Z (m)": "Depth Z (m)",
        "轴力分布": "Axial Force Distribution",
        "剪力 Nx (kN)": "Shear Force Nx (kN)",
        "X方向剪力分布": "X-Direction Shear Distribution",
        "剪力 Ny (kN)": "Shear Force Ny (kN)",
        "Y方向剪力分布": "Y-Direction Shear Distribution",
        "弯矩 Mx (kN·m)": "Bending Moment Mx (kN·m)",
        "X方向弯矩分布": "X-Direction Bending-Moment Distribution",
        "弯矩 My (kN·m)": "Bending Moment My (kN·m)",
        "Y方向弯矩分布": "Y-Direction Bending-Moment Distribution",
        "位移 (mm)": "Displacement (mm)",
        "水平位移": "Lateral Displacement",
        "轴力 (kN)": "Axial Force (kN)",
        "弯矩 (kN·m)": "Bending Moment (kN·m)",
        "弯矩分布": "Bending-Moment Distribution",
        "水平位移 (m)": "Lateral Displacement (m)",
        "水平位移分布": "Lateral Displacement Distribution",
        "转角 (rad)": "Rotation (rad)",
        "转角分布": "Rotation Distribution",
        "无桩身位移数据": "No pile-displacement data are available",
        "无桩身轴力数据": "No pile axial-force data are available",
        "无桩身弯矩数据": "No pile bending-moment data are available",
    }
    if text in mapping:
        return mapping[text]

    if text.startswith("第 ") and " 号桩 - " in text:
        converted = text.replace("第 ", "Pile ").replace(" 号桩 - ", " - ")
        converted = converted.replace("桩身内力分布图", "Pile Internal-Force Distribution")
        converted = converted.replace("桩身弯矩分布图", "Pile Bending-Moment Distribution")
        converted = converted.replace("桩身位移分布图", "Pile Displacement Distribution")
        return converted

    if text.startswith("桩 "):
        converted = text.replace("桩 ", "Pile ")
        converted = converted.replace(" - 位移分布", " - Displacement Distribution")
        converted = converted.replace(" - 轴力", " - Axial Force")
        converted = converted.replace(" - 弯矩", " - Bending Moment")
        converted = converted.replace(" [最不利]", " [Critical]")
        return converted

    text = text.replace("æœ€å¤§", " Max")
    text = text.replace("å·æ¡©", " Pile")
    text = text.replace("最大", " Max")
    text = text.replace("号桩", " Pile")
    return text

                                   
try:
    import matplotlib
    matplotlib.use('Agg')               
    import matplotlib.ticker as ticker
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Circle, Arc, FancyArrowPatch, Polygon
    import matplotlib.patheffects as PathEffects
    from matplotlib.collections import PatchCollection
    from matplotlib.lines import Line2D
    import matplotlib.colors as mcolors
    from matplotlib.figure import Figure
    from matplotlib.axes import Axes
    
           
    from mpl_toolkits.mplot3d import Axes3D
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    
    import numpy as np
    
    HAS_MATPLOTLIB = True
except ImportError as e:
    logger.warning(f"matplotlib 未安装: {e}")
    HAS_MATPLOTLIB = False
    np = None

            
try:
    from PySide6.QtGui import QPixmap, QImage
    from PySide6.QtCore import QByteArray
    HAS_PYSIDE = True
except ImportError:
    HAS_PYSIDE = False
    QPixmap = None
    QImage = None

                
if TYPE_CHECKING:
    from result_parser import PileResult, PileBodyPoint


def bytesio_to_qpixmap(buf: io.BytesIO) -> 'QPixmap':
    if not HAS_PYSIDE:
        raise ImportError("PySide6 未安装，无法转换图像")
    
    buf.seek(0)
    data = buf.read()
    
    if not data:
        raise ValueError("图像缓冲区为空")
    
    qimage = QImage()
    success = qimage.loadFromData(data)
    
    if not success:
        raise ValueError("无法加载图像数据")
    
    return QPixmap.fromImage(qimage)


def check_matplotlib() -> None:
    if not HAS_MATPLOTLIB:
        raise ImportError(
            "matplotlib 未安装，无法使用绘图功能。\n"
            "请运行: pip install matplotlib numpy"
        )


                                                                         
      
                                                                         
class PlotStyle:

    
          
    COLORS = {
        'pile': '#8B4513',                 
        'cap': '#A9A9A9',                  
        'cap_edge': '#2F4F4F',               
        'force_x': '#DC143C',                
        'force_y': '#4169E1',                
        'force_z': '#228B22',                
        'moment': '#FF8C00',               
        'moment_x': '#FF6347',               
        'moment_y': '#FF8C00',              
        'displacement': '#9932CC',          
        'soil_stress': '#DAA520',           
        'ground': '#8FBC8F',                
        'grid': '#E0E0E0',                 
        'stiffness': '#20B2AA',
        'max_point_x': '#FFD700',                   
        'max_point_y': '#32CD32',                   
        'max_point_z': '#1E90FF',            
    }
    
                      
    PILE_TYPE_COLORS = [
        '#3498DB',       
        '#E74C3C',       
        '#27AE60',       
        '#9B59B6',       
        '#F39C12',       
        '#1ABC9C',       
        '#E91E63',       
        '#00BCD4',      
    ]
    
          
    FONT_CONFIG = {
        'family_zh': ['SimHei', 'Microsoft YaHei', 'DejaVu Sans', 'sans-serif'],
        'family_en': ['Times New Roman', 'Times', 'DejaVu Serif', 'serif'],
        'size': 10,
        'title_size': 12,
        'label_size': 9,
    }
    
    @classmethod
    def apply_chinese_font(cls) -> None:

        if HAS_MATPLOTLIB:
            if get_language() == "en":
                plt.rcParams['font.family'] = cls.FONT_CONFIG['family_en']
                plt.rcParams['font.serif'] = cls.FONT_CONFIG['family_en']
            else:
                plt.rcParams['font.family'] = 'sans-serif'
                plt.rcParams['font.sans-serif'] = cls.FONT_CONFIG['family_zh']
            plt.rcParams['axes.unicode_minus'] = False
            plt.rcParams['font.size'] = cls.FONT_CONFIG['size']


                                                                         
       
                                                                         
class PilePlotter:

    
    def __init__(self):
        check_matplotlib()
        PlotStyle.apply_chinese_font()
    
    def _create_figure(
        self,
        figsize: Tuple[float, float] = (10, 8),
        dpi: int = 150
    ) -> Tuple[Figure, Union[Axes, Axes3D]]:

        fig = plt.figure(figsize=figsize, dpi=dpi)
        return fig
    
    def _save_to_buffer(self, fig: Figure, dpi: int = 150) -> io.BytesIO:

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        plt.close(fig)
        buf.seek(0)
        return buf
    
    def plot_pile_layout(
        self,
        piles: List[Dict],
        loads: Optional[Dict] = None,
        title: str = "桩基平面布置图",
        figsize: Tuple[float, float] = (10, 8),
        show_pile_numbers: bool = True,
        show_coordinates: bool = True,
        pile_radius: Optional[float] = None,
        highlight_pile_no: Optional[Union[str, int]] = None,
        return_fig: bool = False,
        simulated_piles: Optional[List[Dict]] = None,
        pile_types_data: Optional[Dict] = None
    ) -> Union[io.BytesIO, Figure]:
        fig, ax = plt.subplots(figsize=figsize)
        
        if not piles:
            ax.text(0.5, 0.5, "无桩位数据", ha='center', va='center', 
                   fontsize=16, transform=ax.transAxes)
            ax.set_xlim(-1, 1)
            ax.set_ylim(-1, 1)
            return self._save_to_buffer(fig)
        
              
        xs = [float(p.get('x', 0)) for p in piles]
        ys = [float(p.get('y', 0)) for p in piles]
        
              
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        
                   
        x_range = max(x_max - x_min, 2.0)
        y_range = max(y_max - y_min, 2.0)
        
                     
        if pile_radius is None:
                      
            pile_radius = min(x_range, y_range) * 0.08                  
            pile_radius = max(pile_radius, 0.25)                        
            pile_radius = min(pile_radius, 1.2)                       
        
                            
        x_min_all, x_max_all = x_min, x_max
        y_min_all, y_max_all = y_min, y_max
        
                    
        if simulated_piles:
            for sp in simulated_piles:
                sx = float(sp.get('x', sp.get('col2', 0)))
                sy = float(sp.get('y', sp.get('col4', 0)))
                x_min_all = min(x_min_all, sx)
                x_max_all = max(x_max_all, sx)
                y_min_all = min(y_min_all, sy)
                y_max_all = max(y_max_all, sy)

        x_range_all = max(x_max_all - x_min_all, 2.0)
        y_range_all = max(y_max_all - y_min_all, 2.0)
        
                        
                               
        view_margin = max(x_range_all, y_range_all) * 0.35
        view_x_min = x_min_all - view_margin
        view_x_max = x_max_all + view_margin
        view_y_min = y_min_all - view_margin
        view_y_max = y_max_all + view_margin
        
                         
        cap_rect = Rectangle(
            (view_x_min, view_y_min),
            view_x_max - view_x_min,
            view_y_max - view_y_min,
            fill=True,
            facecolor='#D3D3D3',            
            edgecolor=PlotStyle.COLORS['cap_edge'],
            linewidth=2,
            zorder=1
        )
        ax.add_patch(cap_rect)
        
                         
        unique_types = sorted(list(set(p.get('type', 'default') for p in piles)))
        type_color_map = {}
        type_shape_map = {}              
        
        for i, tname in enumerate(unique_types):
            type_color_map[tname] = PlotStyle.PILE_TYPE_COLORS[i % len(PlotStyle.PILE_TYPE_COLORS)]
                                      
            if pile_types_data and tname in pile_types_data:
                type_shape_map[tname] = pile_types_data[tname].get('ksh', 0)
            else:
                type_shape_map[tname] = 0        
        
        for pile in piles:
            x, y = float(pile.get('x', 0)), float(pile.get('y', 0))
            pile_type = pile.get('type', 'default')
            pile_no = pile.get('no', '')
            
                             
                             
            color = '#F4A460'              
            shape_code = type_shape_map.get(pile_type, 0)
            
                      
            is_highlighted = (highlight_pile_no is not None and 
                              str(pile_no) == str(highlight_pile_no))
            
                        
            if is_highlighted:
                face_color = '#FFD700'        
                edge_color = '#FF4500'         
                edge_width = 3.0
                pile_zorder = 10                        
            else:
                face_color = color
                edge_color = 'black'
                edge_width = 1.2
                pile_zorder = 3
            
                              
            if shape_code == 1:
                      
                half_side = pile_radius * 0.9             
                rect = Rectangle(
                    (x - half_side, y - half_side),
                    half_side * 2, half_side * 2,
                    facecolor=face_color,
                    edgecolor=edge_color,
                    linewidth=edge_width,
                    zorder=pile_zorder
                )
                ax.add_patch(rect)
            else:
                      
                circle = Circle(
                    (x, y), pile_radius,
                    facecolor=face_color,
                    edgecolor=edge_color,
                    linewidth=edge_width,
                    zorder=pile_zorder
                )
                ax.add_patch(circle)
            
                  
            if show_pile_numbers:
                ax.text(
                    x, y, str(pile_no),
                    ha='center', va='center',
                    fontsize=PlotStyle.FONT_CONFIG['label_size'],
                    fontweight='bold',
                    color='black',            
                    zorder=pile_zorder + 1
                )
        
                                 
        if simulated_piles:
            simu_color = '#1E90FF'                      
            
            for i, simu_pile in enumerate(simulated_piles):
                sx = float(simu_pile.get('x', simu_pile.get('col2', 0)))
                sy = float(simu_pile.get('y', simu_pile.get('col4', 0)))
                
                            
                ax.plot(sx, sy, 'o', 
                       markersize=12,
                       color=simu_color,
                       markeredgecolor='white',
                       markeredgewidth=1.5,
                       zorder=10)       
                
                           
                marker_offset = pile_radius * 3.0                      
                txt = ax.text(
                    sx, sy - marker_offset, f"SIMU{i+1}",
                    ha='center', va='top',
                    fontsize=PlotStyle.FONT_CONFIG['label_size'],
                    fontweight='bold',
                    color='white',
                    zorder=11
                )
                                     
                txt.set_path_effects([PathEffects.withStroke(linewidth=1, foreground='#555555', alpha=0.5)])

                                   
                pass

                
        if loads:
            self._draw_loads_2d(ax, loads, x_min, x_max, y_min, y_max)
        
                            
        ax.set_xlim(view_x_min, view_x_max)
        ax.set_ylim(view_y_min, view_y_max)
        ax.set_aspect('equal')
        ax.set_xlabel(_plot_text('X-纵向 (m)'), fontsize=PlotStyle.FONT_CONFIG['size'])
        ax.set_ylabel(_plot_text('Y-横向 (m)'), fontsize=PlotStyle.FONT_CONFIG['size'])
        ax.set_title(_plot_text(title), fontsize=PlotStyle.FONT_CONFIG['title_size'], 
                    fontweight='bold')
        ax.invert_yaxis()
        if show_coordinates:
            ax.grid(True, linestyle='--', alpha=0.5, color=PlotStyle.COLORS['grid'])
        
                
        self._draw_north_arrow(ax)
        
                       
        plt.subplots_adjust(top=0.92, bottom=0.10, left=0.08, right=0.95, hspace=0.200, wspace=0.200)
        if return_fig:
            return fig
        return self._save_to_buffer(fig)
    
    def _draw_loads_2d(
        self,
        ax: Axes,
        loads: Union[Dict, List[Dict]],
        x_min: float, x_max: float,
        y_min: float, y_max: float
    ) -> None:

        x_range = max(x_max - x_min, 2.0)
        y_range = max(y_max - y_min, 2.0)
                
        arrow_scale = max(x_range, y_range) * 0.15
        
                    
        if isinstance(loads, dict):
            loads_list = [loads]
        else:
            loads_list = loads
        
        for load_data in loads_list:
                                    
            center_x = float(load_data.get('cx', (x_min + x_max) / 2))
            center_y = float(load_data.get('cy', (y_min + y_max) / 2))
            
                          
            load_name = load_data.get('name', '')
            
            self._draw_single_load_2d(ax, load_data, center_x, center_y, arrow_scale, load_name)
    
    def _draw_single_load_2d(
        self,
        ax: Axes,
        loads: Dict,
        center_x: float,
        center_y: float,
        arrow_scale: float,
        load_name: str = ''
    ) -> None:
        
        label_stack = []                  
                 
        nx = float(loads.get('nx', 0))
        if abs(nx) > 1e-10:
            direction = 1 if nx > 0 else -1
            ax.annotate(
                '', 
                xy=(center_x + direction * arrow_scale, center_y),
                xytext=(center_x, center_y),
                arrowprops=dict(
                    arrowstyle='->', 
                    color=PlotStyle.COLORS['force_x'],
                    lw=1.0,     
                    mutation_scale=8       
                ),
                zorder=20         
            )
                           
            label_stack.append((f'Nx={nx:.1f}kN', PlotStyle.COLORS['force_x']))
        
                 
        ny = float(loads.get('ny', 0))
        if abs(ny) > 1e-10:
            direction = 1 if ny > 0 else -1
            ax.annotate(
                '',
                xy=(center_x, center_y + direction * arrow_scale),
                xytext=(center_x, center_y),
                arrowprops=dict(
                    arrowstyle='->',
                    color=PlotStyle.COLORS['force_y'],
                    lw=1.0,     
                    mutation_scale=8       
                ),
                zorder=20
            )
            label_stack.append((f'Ny={ny:.1f}kN', PlotStyle.COLORS['force_y']))
        
                        
        nz = float(loads.get('nz', 0))
        if abs(nz) > 1e-10:
                                                        
                                                 
            marker = 'x' if nz > 0 else '.'
            marker_size = 10 if nz > 0 else 16                 
            
            ax.plot(center_x, center_y, marker, 
                   markersize=marker_size,
                   color=PlotStyle.COLORS['force_z'],
                   markeredgewidth=2,
                   zorder=20)
            label_stack.append((f'Nz={nz:.1f}kN', PlotStyle.COLORS['force_z']))
        
                   
        mx = float(loads.get('mx', 0))
        if abs(mx) > 1e-10:
                             
            self._draw_moment_arc(ax, center_x, center_y, arrow_scale * 0.8,
                                 mx, 'x', PlotStyle.COLORS['force_x'])
            label_stack.append((f'Mx={mx:.1f}kN·m', PlotStyle.COLORS['force_x']))
        
        my = float(loads.get('my', 0))
        if abs(my) > 1e-10:
                      
            self._draw_moment_arc(ax, center_x, center_y, arrow_scale * 1.1,
                                 my, 'y', PlotStyle.COLORS['force_y'])
            label_stack.append((f'My={my:.1f}kN·m', PlotStyle.COLORS['force_y']))

                
        if label_stack:
            self._draw_grouped_labels(ax, center_x, center_y, label_stack, arrow_scale)
    
    def _draw_moment_arc(
        self,
        ax: Axes,
        cx: float, cy: float,
        radius: float,
        moment: float,
        axis: str,
        color: str
    ) -> None:
                         
        if axis == 'x':
            theta1, theta2 = (45, 135) if moment > 0 else (225, 315)
        else:
            theta1, theta2 = (135, 225) if moment > 0 else (-45, 45)
        
              
        arc = Arc((cx, cy), radius * 2, radius * 2,
                 angle=0, theta1=theta1, theta2=theta2,
                 color=color, linewidth=1.0, zorder=20)     
        ax.add_patch(arc)
        
                 
                
        import math
        end_rad = math.radians(theta2)
        end_x = cx + radius * math.cos(end_rad)
        end_y = cy + radius * math.sin(end_rad)
        
                              
                          
        dx = -math.sin(end_rad)
        dy = math.cos(end_rad)
        
                            
        ax.annotate(
            '',
            xy=(end_x + dx * radius * 0.1, end_y + dy * radius * 0.1),             
            xytext=(end_x, end_y),
            arrowprops=dict(
                arrowstyle='->', 
                color=color, 
                lw=1.0,     
                shrinkA=0, shrinkB=0
            ),
            zorder=20
        )
        
                            
        label = f'M{axis}={moment:.1f}kN·m'
                                                 
                                          
        pass

    def _draw_grouped_labels(self, ax, center_x, center_y, labels, radius):
        if not labels:
            return
            
                    
        text_x = center_x + radius * 1.5
        text_y = center_y + radius * 1.5
        line_height = radius * 0.5        
        
        for i, (text, color) in enumerate(labels):
            y_pos = text_y - i * line_height
            t = ax.text(text_x, y_pos, text, 
                       color=color, fontsize=8, fontweight='bold',
                       ha='left', va='center', zorder=25)
                        
            t.set_path_effects([PathEffects.withStroke(linewidth=2, foreground='white', alpha=0.8)])
    
    def _draw_north_arrow(self, ax: Axes) -> None:

                 
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        
                
        x_pos = xlim[1] - (xlim[1] - xlim[0]) * 0.08
        y_pos = ylim[1] - (ylim[1] - ylim[0]) * 0.08
        arrow_len = (ylim[1] - ylim[0]) * 0.06
        
        ax.annotate(
            'N',
            xy=(x_pos, y_pos),
            xytext=(x_pos, y_pos - arrow_len),
            fontsize=10, fontweight='bold', ha='center',
            arrowprops=dict(arrowstyle='->', color='black', lw=1.5)
        )
    
    def plot_pile_3d(
        self,
        piles: List[Dict],
        loads: Optional[Dict] = None,
        pile_depth: float = 15.0,
        cap_margin: float = 1.5,
        cap_thickness: float = 1.0,
        pile_radius: float = 0.4,
        title: str = "桩基三维布置图",
        figsize: Tuple[float, float] = (20, 16),            
        dpi: int = 150,
        elev: float = 25,
        azim: float = -60,
        show_loads: bool = False,
        show_pile_numbers: bool = True,
        return_fig: bool = False,
        pile_types_data: Optional[Dict] = None
    ) -> Union[io.BytesIO, Figure]:
        fig = plt.figure(figsize=figsize, dpi=dpi)
        ax = fig.add_subplot(111, projection='3d')
        
        if not piles:
            ax.text(0, 0, 0, "无桩位数据", fontsize=16)
            return self._save_to_buffer(fig, dpi=dpi)
        
              
        xs = [float(p.get('x', 0)) for p in piles]
        ys = [float(p.get('y', 0)) for p in piles]
        
        x_min, x_max = min(xs) - cap_margin, max(xs) + cap_margin
        y_min, y_max = min(ys) - cap_margin, max(ys) + cap_margin
        
                            
        x_span = max(xs) - min(xs) if len(xs) > 1 else 2.0
        y_span = max(ys) - min(ys) if len(ys) > 1 else 2.0
        avg_span = max(x_span, y_span, 2.0)
        
                                   
        adaptive_pile_radius = min(avg_span * 0.08, pile_radius * 1.0)
        adaptive_pile_radius = max(adaptive_pile_radius, 0.2)            
        
                  
        cap_top = 0.0
        cap_bottom = -cap_thickness

              
        self._draw_3d_box(
            ax, x_min, x_max, y_min, y_max, cap_bottom, cap_top,
            facecolor=PlotStyle.COLORS['cap'],
            edgecolor=PlotStyle.COLORS['cap_edge'],
            alpha=0.3
        )
        
                                        
        cap_center_x = (x_min + x_max) / 2
        cap_center_y = (y_min + y_max) / 2
                         
                                                
                                                
                                
        len_x = (y_max - y_min) / 2 * 1.3
        len_y = (x_max - x_min) / 2 * 1.3
        len_z = pile_depth * 1.1
        
        self._draw_coordinate_system_3d_new(
            ax, 
            origin=(cap_center_x, cap_center_y, cap_bottom), 
            len_x=len_x,
            len_y=len_y,
            len_z=len_z
        )
        
                                           
        unique_types = sorted(list(set(p.get('type', 'Default') for p in piles)))
        type_shape_map = {}              
        
        for tname in unique_types:
                                      
            if pile_types_data and tname in pile_types_data:
                type_data = pile_types_data[tname]
                type_shape_map[tname] = type_data.get('ksh', 0)
            else:
                type_shape_map[tname] = 0

              
        pile_color = '#8B4513'                    
        
              
        for pile in piles:
            x, y = float(pile.get('x', 0)), float(pile.get('y', 0))
            angle_deg = float(pile.get('angle', 0))
            type_name = pile.get('type', 'Default')
            
                  
            shape_code = type_shape_map.get(type_name, 0)
            
                                   
            visual_radius = adaptive_pile_radius * 1.0
            
            if shape_code == 1:
                             
                if abs(angle_deg) < 0.5:
                    self._draw_3d_prism(
                        ax, x, y, cap_bottom, -pile_depth,
                        width=visual_radius * 2, depth=visual_radius * 2,
                        facecolor=pile_color, edgecolor='#5D3A1A', alpha=0.9
                    )
                else:
                         
                    self._draw_3d_inclined_cylinder(
                        ax, x, y, cap_bottom, pile_depth, visual_radius, angle_deg,
                        n_sides=4,        
                        facecolor=pile_color, edgecolor='#5D3A1A', alpha=0.9
                    )
            else:
                               
                if abs(angle_deg) < 0.5:
                    self._draw_3d_cylinder(
                        ax, x, y, cap_bottom, -pile_depth,
                        radius=visual_radius,
                        n_sides=24,
                        facecolor=pile_color, edgecolor='#5D3A1A', alpha=0.9
                    )
                else:
                    self._draw_3d_inclined_cylinder(
                        ax, x, y, cap_bottom, pile_depth, visual_radius, angle_deg,
                        n_sides=24,
                        facecolor=pile_color, edgecolor='#5D3A1A', alpha=0.9
                    )

                
        if show_loads and loads:
             self._draw_loads_3d(ax, loads, x_min, x_max, y_min, y_max, cap_top)

                 
        ax.set_axis_off()
                    
        ax.view_init(elev=elev, azim=azim)
        
               
        max_range = max(x_max - x_min, y_max - y_min, pile_depth * 1.2)
        mid_x = (x_max + x_min) * 0.5
        mid_y = (y_max + y_min) * 0.5
        mid_z = -pile_depth * 0.5
        
        ax.set_xlim(mid_x - max_range*0.5, mid_x + max_range*0.5)
        ax.set_ylim(mid_y - max_range*0.5, mid_y + max_range*0.5)
        ax.set_zlim(mid_z - max_range*0.5, mid_z + max_range*0.6)

                        
        plt.subplots_adjust(top=0.98, bottom=0.01, left=0.01, right=0.99)
        plt.tight_layout(pad=0.5)
        if return_fig:
            return fig
        return self._save_to_buffer(fig, dpi=dpi)
    
    def _draw_coordinate_system_3d_new(
        self, ax: Axes3D, origin=(0,0,0), len_x=3.0, len_y=3.0, len_z=3.0
    ) -> None:

        ox, oy, oz = origin
        
                          
        ax.quiver(ox, oy, oz, 0, len_x, 0, color='red', arrow_length_ratio=0.08, 
                 linewidth=0.8, alpha=0.6)
        ax.text(ox, oy + len_x * 1.1, oz, "X", color='red', fontsize=10, 
               fontweight='bold', ha='center', alpha=0.85)
        
                            
        ax.quiver(ox, oy, oz, len_y, 0, 0, color='green', arrow_length_ratio=0.08, 
                 linewidth=0.8, alpha=0.6)
        ax.text(ox + len_y * 1.1, oy, oz, "Y", color='green', fontsize=10, 
               fontweight='bold', ha='center', alpha=0.85)
        
                          
        ax.quiver(ox, oy, oz, 0, 0, -len_z, color='blue', arrow_length_ratio=0.08, 
                 linewidth=0.8, alpha=0.6)
        ax.text(ox, oy, oz - len_z * 1.1, "Z", color='blue', fontsize=10, 
               fontweight='bold', ha='center', alpha=0.85)
        
                   
        ax.scatter([ox], [oy], [oz], color='black', s=15, zorder=10, alpha=0.5)


    def _draw_3d_box(
        self,
        ax: Axes3D,
        x_min: float, x_max: float,
        y_min: float, y_max: float,
        z_min: float, z_max: float,
        facecolor: str = 'gray',
        edgecolor: str = 'black',
        alpha: float = 0.5
    ) -> None:

               
        vertices = [
            [x_min, y_min, z_min], [x_max, y_min, z_min],
            [x_max, y_max, z_min], [x_min, y_max, z_min],
            [x_min, y_min, z_max], [x_max, y_min, z_max],
            [x_max, y_max, z_max], [x_min, y_max, z_max]
        ]
        
              
        faces = [
            [vertices[0], vertices[1], vertices[5], vertices[4]],     
            [vertices[2], vertices[3], vertices[7], vertices[6]],     
            [vertices[0], vertices[3], vertices[7], vertices[4]],     
            [vertices[1], vertices[2], vertices[6], vertices[5]],     
            [vertices[0], vertices[1], vertices[2], vertices[3]],     
            [vertices[4], vertices[5], vertices[6], vertices[7]],     
        ]
        
        collection = Poly3DCollection(
            faces,
            facecolors=facecolor,
            edgecolors=edgecolor,
            linewidths=0.5,
            alpha=alpha
        )
        ax.add_collection3d(collection)
    
    def _draw_3d_prism(
        self, ax: Axes3D, cx: float, cy: float, z_top: float, z_bottom: float,
        width: float, depth: float,
        facecolor='brown', edgecolor='black', alpha=0.9
    ) -> None:

        dx = width / 2
        dy = depth / 2
        
        x_min, x_max = cx - dx, cx + dx
        y_min, y_max = cy - dy, cy + dy
        
                                                             
        vertices = [
            [x_min, y_min, z_bottom], [x_max, y_min, z_bottom],
            [x_max, y_max, z_bottom], [x_min, y_max, z_bottom],
            [x_min, y_min, z_top], [x_max, y_min, z_top],
            [x_max, y_max, z_top], [x_min, y_max, z_top]
        ]
        
        faces = [
            [vertices[0], vertices[1], vertices[5], vertices[4]],         
            [vertices[2], vertices[3], vertices[7], vertices[6]],        
            [vertices[0], vertices[3], vertices[7], vertices[4]],        
            [vertices[1], vertices[2], vertices[6], vertices[5]],         
            [vertices[0], vertices[1], vertices[2], vertices[3]],          
            [vertices[4], vertices[5], vertices[6], vertices[7]],       
        ]
        
        collection = Poly3DCollection(
            faces, facecolors=facecolor, edgecolors=edgecolor,
            linewidths=0.5, alpha=alpha
        )
        ax.add_collection3d(collection)


    def _draw_3d_cylinder(
        self,
        ax: Axes3D,
        cx: float, cy: float,
        z_top: float, z_bottom: float,
        radius: float,
        n_sides: int = 20,
        facecolor: str = 'brown',
        edgecolor: str = 'black',
        alpha: float = 0.9
    ) -> None:
        theta = np.linspace(0, 2 * np.pi, n_sides + 1)
        
        circle_x = cx + radius * np.cos(theta)
        circle_y = cy + radius * np.sin(theta)
        
               
        top_verts = [[circle_x[i], circle_y[i], z_top] for i in range(n_sides)]
        bottom_verts = [[circle_x[i], circle_y[i], z_bottom] for i in range(n_sides)]
        
            
        faces = [top_verts, bottom_verts]
        for i in range(n_sides):
            next_i = (i + 1) % n_sides
            face = [
                bottom_verts[i], bottom_verts[next_i],
                top_verts[next_i], top_verts[i]
            ]
            faces.append(face)
        
        collection = Poly3DCollection(
            faces,
            facecolors=facecolor,
            edgecolors=edgecolor,
            linewidths=0.2,
            alpha=alpha
        )
        ax.add_collection3d(collection)
    
    def _draw_3d_inclined_cylinder(
        self,
        ax: Axes3D,
        cx: float, cy: float,
        z_top: float,
        pile_length: float,
        radius: float,
        angle_deg: float,
        n_sides: int = 20,
        facecolor: str = 'brown',
        edgecolor: str = 'black',
        alpha: float = 0.9
    ) -> None:
                  
        angle_rad = np.radians(angle_deg)
        
                           
                         
                                         
                                         
        horizontal_offset = pile_length * np.sin(angle_rad)
        vertical_depth = pile_length * np.cos(angle_rad)
        
                      
        dist_from_origin = np.sqrt(cx**2 + cy**2)
        if dist_from_origin > 0.01:
                           
            dir_x = cx / dist_from_origin
            dir_y = cy / dist_from_origin
        else:
                              
            dir_x, dir_y = 1.0, 0.0
        
                
        bottom_cx = cx + dir_x * horizontal_offset
        bottom_cy = cy + dir_y * horizontal_offset
        z_bottom = z_top - vertical_depth
        
                    
        theta = np.linspace(0, 2 * np.pi, n_sides + 1)
        
                         
        top_circle_x = cx + radius * np.cos(theta)
        top_circle_y = cy + radius * np.sin(theta)
        top_verts = [[top_circle_x[i], top_circle_y[i], z_top] for i in range(n_sides)]
        
                                  
        bottom_circle_x = bottom_cx + radius * np.cos(theta)
        bottom_circle_y = bottom_cy + radius * np.sin(theta)
        bottom_verts = [[bottom_circle_x[i], bottom_circle_y[i], z_bottom] for i in range(n_sides)]
        
               
        faces = [top_verts, bottom_verts]
        
            
        for i in range(n_sides):
            next_i = (i + 1) % n_sides
            face = [
                bottom_verts[i], bottom_verts[next_i],
                top_verts[next_i], top_verts[i]
            ]
            faces.append(face)
        
        collection = Poly3DCollection(
            faces,
            facecolors=facecolor,
            edgecolors=edgecolor,
            linewidths=0.2,
            alpha=alpha
        )
        ax.add_collection3d(collection)

    def plot_stiffness_matrix(
        self,
        stiffness_matrix: np.ndarray,
        title: str = "刚度矩阵可视化",
        matrix_type: str = "foundation",
        figsize: Tuple[float, float] = (14, 10)
    ) -> io.BytesIO:
                                                                
        pass                                            

    def _draw_loads_3d(
        self,
        ax: Axes3D,
        loads: Dict,
        x_min: float, x_max: float,
        y_min: float, y_max: float,
        z_top: float
    ) -> None:
        cx = (x_min + x_max) / 2
        cy = (y_min + y_max) / 2
        cz = z_top
        
        arrow_len = max(x_max - x_min, y_max - y_min) * 0.35
        
                
        nz = float(loads.get('nz', 0))
        if abs(nz) > 1e-10:
            direction = -1 if nz > 0 else 1
            ax.quiver(
                cx, cy, cz + abs(direction) * arrow_len * 0.6,
                0, 0, direction * arrow_len * 0.5,
                color=PlotStyle.COLORS['force_z'],
                arrow_length_ratio=0.2, linewidth=2.5
            )
            ax.text(cx + 0.3, cy, cz + arrow_len * 0.7,
                   f'Nz={nz:.0f}kN',
                   color=PlotStyle.COLORS['force_z'], fontsize=9)
        
                
        nx = float(loads.get('nx', 0))
        if abs(nx) > 1e-10:
            direction = 1 if nx > 0 else -1
            ax.quiver(
                cx - direction * arrow_len * 0.3, cy, cz + 0.3,
                direction * arrow_len * 0.5, 0, 0,
                color=PlotStyle.COLORS['force_x'],
                arrow_length_ratio=0.2, linewidth=2.5
            )
            ax.text(cx + direction * arrow_len * 0.3, cy, cz + 0.5,
                   f'Nx={nx:.0f}kN',
                   color=PlotStyle.COLORS['force_x'], fontsize=9)
        
                
        ny = float(loads.get('ny', 0))
        if abs(ny) > 1e-10:
            direction = 1 if ny > 0 else -1
            ax.quiver(
                cx, cy - direction * arrow_len * 0.3, cz + 0.3,
                0, direction * arrow_len * 0.5, 0,
                color=PlotStyle.COLORS['force_y'],
                arrow_length_ratio=0.2, linewidth=2.5
            )
            ax.text(cx, cy + direction * arrow_len * 0.3, cz + 0.5,
                   f'Ny={ny:.0f}kN',
                   color=PlotStyle.COLORS['force_y'], fontsize=9)
    
    def plot_pile_results(
        self,
        pile_result: 'PileResult',
        plot_type: str = 'all',
        figsize: Tuple[float, float] = (14, 10)
    ) -> io.BytesIO:
        if plot_type == 'forces':
            return self.plot_pile_forces(pile_result, figsize)
        elif plot_type == 'displacements':
            return self.plot_pile_displacements(pile_result, figsize)
        elif plot_type == 'moments':
            return self.plot_pile_moments(pile_result, figsize)
        else:
            return self.plot_pile_all(pile_result, figsize)
    
    def plot_pile_forces(
        self,
        pile_result: 'PileResult',
        figsize: Tuple[float, float] = (14, 8)
    ) -> io.BytesIO:
        fig, axes = plt.subplots(1, 3, figsize=figsize, sharey=True)
        
        z = pile_result.get_z_values()
        nx_list, ny_list, nz_list = pile_result.get_forces()
        
        pile_no = pile_result.pile_no
        
             
        ax1 = axes[0]
        if nz_list:
            ax1.plot(nz_list, z, '-', linewidth=2, 
                    color=PlotStyle.COLORS['force_z'], label='轴力 Nz')
        ax1.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax1.set_xlabel(_plot_text('轴力 Nz (kN)'), fontsize=10)
        ax1.set_ylabel(_plot_text('深度 Z (m)'), fontsize=10)
        ax1.set_title(_plot_text('轴力分布'), fontsize=11, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.invert_yaxis()
        leg1 = ax1.legend(loc='lower right', fontsize=PlotStyle.FONT_CONFIG['size'],
               markerscale=1.0, handlelength=2, handletextpad=0.4)
        
                 
        ax2 = axes[1]
        if nx_list:
            ax2.plot(nx_list, z, '-', linewidth=2,
                    color=PlotStyle.COLORS['force_x'], label='剪力 Nx')
        ax2.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax2.set_xlabel(_plot_text('剪力 Nx (kN)'), fontsize=10)
        ax2.set_title(_plot_text('X方向剪力分布'), fontsize=11, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        leg2 = ax2.legend(loc='lower right', fontsize=PlotStyle.FONT_CONFIG['size'],
               markerscale=1.0, handlelength=2, handletextpad=0.4)
        
                 
        ax3 = axes[2]
        if ny_list:
            ax3.plot(ny_list, z, '-', linewidth=2,
                    color=PlotStyle.COLORS['force_y'], label='剪力 Ny')
        ax3.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax3.set_xlabel(_plot_text('剪力 Ny (kN)'), fontsize=10)
        ax3.set_title(_plot_text('Y方向剪力分布'), fontsize=11, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc='lower right')
        
        fig.suptitle(_plot_text(f'第 {pile_no} 号桩 - 桩身内力分布图'), 
                    fontsize=14, fontweight='bold')
        plt.subplots_adjust(top=0.90, bottom=0.10, left=0.08, right=0.95, wspace=0.25)
        
        return self._save_to_buffer(fig)
    
    def plot_pile_moments(
        self,
        pile_result: 'PileResult',
        figsize: Tuple[float, float] = (12, 8)
    ) -> io.BytesIO:
        fig, axes = plt.subplots(1, 2, figsize=figsize, sharey=True)
        
        z = pile_result.get_z_values()
        mx_list, my_list = pile_result.get_moments()
        pile_no = pile_result.pile_no
        
                
        ax1 = axes[0]
        if mx_list:
            ax1.plot(mx_list, z, '-', linewidth=2,
                    color=PlotStyle.COLORS['force_x'], label='弯矩 Mx')
        ax1.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax1.set_xlabel(_plot_text('弯矩 Mx (kN·m)'), fontsize=10)
        ax1.set_ylabel(_plot_text('深度 Z (m)'), fontsize=10)
        ax1.set_title(_plot_text('X方向弯矩分布'), fontsize=11, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.invert_yaxis()
        leg1 = ax1.legend(loc='lower right', fontsize=7)
        if leg1 is not None:
            for t in leg1.get_texts():
                t.set_fontsize(7)
        
                
        ax2 = axes[1]
        if my_list:
            ax2.plot(my_list, z, '-', linewidth=2,
                    color=PlotStyle.COLORS['force_y'], label='弯矩 My')
        ax2.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax2.set_xlabel(_plot_text('弯矩 My (kN·m)'), fontsize=10)
        ax2.set_title(_plot_text('Y方向弯矩分布'), fontsize=11, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        leg2 = ax2.legend(loc='lower right', fontsize=7)
        if leg2 is not None:
            for t in leg2.get_texts():
                t.set_fontsize(7)
        
        fig.suptitle(_plot_text(f'第 {pile_no} 号桩 - 桩身弯矩分布图'),
                    fontsize=14, fontweight='bold')
        plt.subplots_adjust(top=0.90, bottom=0.10, left=0.08, right=0.95, wspace=0.25)
        
        return self._save_to_buffer(fig)
    
    def plot_pile_force_displacement(
        self,
        pile_result: 'PileResult',
        piles: List[Dict] = None,
        figsize: Tuple[float, float] = (9, 3.5),
        dpi: int = 150,
        is_critical: bool = False
    ) -> io.BytesIO:
        fig, axes = plt.subplots(1, 2, figsize=figsize, dpi=dpi)
        
        pile_no = pile_result.pile_no
        z = pile_result.get_z_values()
        ux_list, uy_list = pile_result.get_displacements()
        
               
        ux_mm = [v * 1000 for v in ux_list] if ux_list else []
        uy_mm = [v * 1000 for v in uy_list] if uy_list else []
        
                    
        ax0 = axes[0]
        self._draw_layout_subplot(ax0, piles, pile_no)
        
                                
        ax1 = axes[1]
        has_data = False
        max_info = []           
        
        if z and ux_mm and any(v != 0 for v in ux_mm):
            ax1.plot(ux_mm, z, '-', linewidth=1.2, markersize=2, marker='o',
                    color=PlotStyle.COLORS['force_x'], label='Ux')
                      
            max_idx = max(range(len(ux_mm)), key=lambda i: abs(ux_mm[i]))
            max_val, max_z = ux_mm[max_idx], z[max_idx]
            ax1.plot(max_val, max_z, 'o', color=PlotStyle.COLORS['max_point_x'], 
                    markersize=5, markeredgecolor='black', markeredgewidth=0.5)
            max_info.append(f'Ux最大: {max_val:.2f}mm @ Z={max_z:.2f}m')
            has_data = True
        if z and uy_mm and any(v != 0 for v in uy_mm):
            ax1.plot(uy_mm, z, '-', linewidth=1.2, markersize=2, marker='s',
                    color=PlotStyle.COLORS['force_y'], label='Uy')
                      
            max_idx = max(range(len(uy_mm)), key=lambda i: abs(uy_mm[i]))
            max_val, max_z = uy_mm[max_idx], z[max_idx]
            ax1.plot(max_val, max_z, 's', color=PlotStyle.COLORS['max_point_y'], 
                    markersize=5, markeredgecolor='black', markeredgewidth=0.5)
            max_info.append(f'Uy最大: {max_val:.2f}mm @ Z={max_z:.2f}m')
            has_data = True
        
        if not has_data:
            ax1.text(0.5, 0.5, _plot_text('无桩身位移数据'), ha='center', va='center',
                    fontsize=12, color='#888', transform=ax1.transAxes)
        ax1.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax1.set_xlabel(_plot_text('位移 (mm)'), fontsize=9)
        ax1.set_ylabel(_plot_text('深度 Z (m)'), fontsize=9)
        ax1.set_title(_plot_text('水平位移'), fontsize=10, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.invert_yaxis()        
        if has_data:
                                            
            ax1.legend(loc='lower right')
            if max_info:
                info_text = _plot_text('\n'.join(max_info))
                fig.text(0.40, 0.01, info_text, fontsize=8, ha='left', va='bottom',
                         color='red')
        
                   
        title = f'桩 {pile_no} - 位移分布'
        if is_critical:
            title += ' [最不利]'
        fig.suptitle(_plot_text(title), fontsize=11, fontweight='bold', 
                    color='red' if is_critical else 'black')
        plt.subplots_adjust(top=0.880, bottom=0.145, left=0.080, right=0.950, hspace=0.200, wspace=0.250)
        
        return self._save_to_buffer(fig, dpi=dpi)
    
    def _draw_layout_subplot(self, ax, piles: List[Dict], highlight_pile_no):
        ax.set_aspect('equal')
        ax.set_title(_plot_text('桩位布置'), fontsize=11, fontweight='bold')
        
        if not piles:
            ax.text(0.5, 0.5, '无桩位数据', ha='center', va='center', 
                   fontsize=10, transform=ax.transAxes)
            ax.set_xlim(-1, 1)
            ax.set_ylim(-1, 1)
            return
        
        xs = [float(p.get('x', 0)) for p in piles]
        ys = [float(p.get('y', 0)) for p in piles]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        x_range = max(x_max - x_min, 2.0)
        y_range = max(y_max - y_min, 2.0)
        
        pile_radius = min(x_range, y_range) * 0.06
        pile_radius = max(pile_radius, 0.15)
        
        for pile in piles:
            x, y = float(pile.get('x', 0)), float(pile.get('y', 0))
            p_no = pile.get('no', '')
            is_highlight = str(p_no) == str(highlight_pile_no)
            
            if is_highlight:
                circle = Circle((x, y), pile_radius, 
                               facecolor='#FFD700', edgecolor='#FF4500', 
                               linewidth=2, zorder=10)
            else:
                circle = Circle((x, y), pile_radius,
                               facecolor='#87CEEB', edgecolor='#333',
                               linewidth=1, zorder=3)
            ax.add_patch(circle)
            ax.text(x, y, str(p_no), ha='center', va='center', 
                   fontsize=8, fontweight='bold', zorder=11)
        
        margin = max(x_range, y_range) * 0.15
        ax.set_xlim(x_min - margin, x_max + margin)
        ax.set_ylim(y_min - margin, y_max + margin)
        ax.set_xlabel(_plot_text('X-纵向 (m)'), fontsize=9)
        ax.set_ylabel(_plot_text('Y-横向 (m)'), fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.invert_yaxis()

    def plot_pile_axial_force(
        self,
        pile_result: 'PileResult',
        piles: List[Dict] = None,
        figsize: Tuple[float, float] = (9, 3.5),
        dpi: int = 150,
        is_critical: bool = False
    ) -> io.BytesIO:
        fig, axes = plt.subplots(1, 2, figsize=figsize, dpi=dpi)
        
        pile_no = pile_result.pile_no
        z = pile_result.get_z_values()
        nx_list, ny_list, nz_list = pile_result.get_forces()
        
                    
        ax0 = axes[0]
        self._draw_layout_subplot(ax0, piles, pile_no)
        
                              
        ax1 = axes[1]
        has_data = False
        max_info = []           
        
        if z and nz_list and any(v != 0 for v in nz_list):
            ax1.plot(nz_list, z, '-', linewidth=1.2, markersize=2, marker='o',
                    color=PlotStyle.COLORS['force_z'], label='Nz')
                      
            max_idx = max(range(len(nz_list)), key=lambda i: abs(nz_list[i]))
            max_val, max_z = nz_list[max_idx], z[max_idx]
            ax1.plot(max_val, max_z, 'o', color=PlotStyle.COLORS['force_z'], 
                    markersize=5, markeredgecolor='black', markeredgewidth=0.5)
            max_info.append(f'Nz最大: {max_val:.2f}kN @ Z={max_z:.2f}m')
            has_data = True
        
        if not has_data:
            ax1.text(0.5, 0.5, _plot_text('无桩身轴力数据'), ha='center', va='center',
                    fontsize=12, color='#888', transform=ax1.transAxes)
        ax1.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax1.set_xlabel(_plot_text('轴力 (kN)'), fontsize=9)
        ax1.set_ylabel(_plot_text('深度 Z (m)'), fontsize=9)
        ax1.set_title(_plot_text('轴力分布'), fontsize=10, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.invert_yaxis()        
        if has_data:
            ax1.legend(loc='lower right')
            if max_info:
                info_text = _plot_text('\n'.join(max_info))
                fig.text(0.40, 0.01, info_text, fontsize=8, ha='left', va='bottom',
                         color='red')
        
                   
        title = f'桩 {pile_no} - 轴力'
        if is_critical:
            title += ' [最不利]'
        fig.suptitle(_plot_text(title), fontsize=11, fontweight='bold',
                    color='red' if is_critical else 'black')
        plt.subplots_adjust(top=0.880, bottom=0.145, left=0.080, right=0.950, hspace=0.200, wspace=0.250)
        
        return self._save_to_buffer(fig, dpi=dpi)
    
    def plot_pile_moment(
        self,
        pile_result: 'PileResult',
        piles: List[Dict] = None,
        figsize: Tuple[float, float] = (9, 3.5),
        dpi: int = 150,
        is_critical: bool = False
    ) -> io.BytesIO:
        fig, axes = plt.subplots(1, 2, figsize=figsize, dpi=dpi)
        
        pile_no = pile_result.pile_no
        z = pile_result.get_z_values()
        mx_list, my_list = pile_result.get_moments()
        
                    
        ax0 = axes[0]
        self._draw_layout_subplot(ax0, piles, pile_no)
        
                              
        ax1 = axes[1]
        has_data = False
        max_info = []           
        
        if z and mx_list and any(v != 0 for v in mx_list):
            ax1.plot(mx_list, z, '-', linewidth=1.2, markersize=2, marker='o',
                    color=PlotStyle.COLORS['force_x'], label='Mx')
                      
            max_idx = max(range(len(mx_list)), key=lambda i: abs(mx_list[i]))
            max_val, max_z = mx_list[max_idx], z[max_idx]
            ax1.plot(max_val, max_z, 'o', color=PlotStyle.COLORS['force_x'], 
                    markersize=5, markeredgecolor='black', markeredgewidth=0.5)
            max_info.append(f'Mx最大: {max_val:.2f}kN·m @ Z={max_z:.2f}m')
            has_data = True
        if z and my_list and any(v != 0 for v in my_list):
            ax1.plot(my_list, z, '-', linewidth=1.2, markersize=2, marker='s',
                    color=PlotStyle.COLORS['force_y'], label='My')
                      
            max_idx = max(range(len(my_list)), key=lambda i: abs(my_list[i]))
            max_val, max_z = my_list[max_idx], z[max_idx]
            ax1.plot(max_val, max_z, 's', color=PlotStyle.COLORS['force_y'], 
                    markersize=5, markeredgecolor='black', markeredgewidth=0.5)
            max_info.append(f'My最大: {max_val:.2f}kN·m @ Z={max_z:.2f}m')
            has_data = True
        
        if not has_data:
            ax1.text(0.5, 0.5, _plot_text('无桩身弯矩数据'), ha='center', va='center',
                    fontsize=12, color='#888', transform=ax1.transAxes)
        ax1.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax1.set_xlabel(_plot_text('弯矩 (kN·m)'), fontsize=9)
        ax1.set_ylabel(_plot_text('深度 Z (m)'), fontsize=9)
        ax1.set_title(_plot_text('弯矩分布'), fontsize=10, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.invert_yaxis()        
        if has_data:
            leg = ax1.legend(loc='lower right', fontsize=7)
            if leg is not None:
                for t in leg.get_texts():
                    t.set_fontsize(7)
            if max_info:
                info_text = _plot_text('\n'.join(max_info))
                fig.text(0.38, 0.01, info_text, fontsize=8, ha='left', va='bottom',
                         color='red')
        
                   
        title = f'桩 {pile_no} - 弯矩'
        if is_critical:
            title += ' [最不利]'
        fig.suptitle(_plot_text(title), fontsize=11, fontweight='bold',
                    color='red' if is_critical else 'black')
        plt.subplots_adjust(top=0.880, bottom=0.145, left=0.080, right=0.950, hspace=0.200, wspace=0.250)
        
        return self._save_to_buffer(fig, dpi=dpi)

    def create_pile_force_displacement_figure(
        self,
        pile_result: 'PileResult',
        piles: List[Dict] = None,
        figsize: Tuple[float, float] = (9, 3.5),
        is_critical: bool = False
    ) -> Figure:
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        pile_no = pile_result.pile_no
        z = pile_result.get_z_values()
        ux_list, uy_list = pile_result.get_displacements()
        
               
        ux_mm = [v * 1000 for v in ux_list] if ux_list else []
        uy_mm = [v * 1000 for v in uy_list] if uy_list else []
        
                    
        ax0 = axes[0]
        self._draw_layout_subplot(ax0, piles, pile_no)
        
                                
        ax1 = axes[1]
        has_data = False
        max_info = []
        
                        
        if z and ux_mm and any(v != 0 for v in ux_mm):
            ax1.plot(ux_mm, z, '-', linewidth=1.2, markersize=2, marker='o',
                color='blue', label='Ux')
            max_idx = max(range(len(ux_mm)), key=lambda i: abs(ux_mm[i]))
            max_val, max_z = ux_mm[max_idx], z[max_idx]
            ax1.plot(max_val, max_z, 'o', color='green', 
                markersize=5, markeredgecolor='black', markeredgewidth=1.2)
            max_info.append(f'Ux最大: {max_val:.2f}mm @ Z={max_z:.2f}m')
            has_data = True
                        
        if z and uy_mm and any(v != 0 for v in uy_mm):
            ax1.plot(uy_mm, z, '-', linewidth=1.2, markersize=2, marker='s',
                color='red', label='Uy')
            max_idx = max(range(len(uy_mm)), key=lambda i: abs(uy_mm[i]))
            max_val, max_z = uy_mm[max_idx], z[max_idx]
            ax1.plot(max_val, max_z, 's', color='yellow', 
                markersize=5, markeredgecolor='black', markeredgewidth=1.2)
            max_info.append(f'Uy最大: {max_val:.2f}mm @ Z={max_z:.2f}m')
            has_data = True
        
        if not has_data:
            ax1.text(0.5, 0.5, _plot_text('无桩身位移数据'), ha='center', va='center',
                    fontsize=12, color='#888', transform=ax1.transAxes)
        ax1.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax1.set_xlabel(_plot_text('位移 (mm)'), fontsize=9)
        ax1.set_ylabel(_plot_text('深度 Z (m)'), fontsize=9)
        ax1.set_title(_plot_text('水平位移'), fontsize=10, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.invert_yaxis()
        if has_data:
            ax1.legend(loc='lower right', fontsize=7)
            if max_info:
                info_text = _plot_text('\n'.join(max_info))
                fig.text(0.40, 0.01, info_text, fontsize=8, ha='left', va='bottom',
                         color='red')
        
        title = f'桩 {pile_no} - 位移分布'
        if is_critical:
            title += ' [最不利]'
        fig.suptitle(_plot_text(title), fontsize=11, fontweight='bold',
                    color='red' if is_critical else 'black')
        fig.subplots_adjust(top=0.880, bottom=0.145, left=0.080, right=0.950, hspace=0.200, wspace=0.250)
        
        return fig

    def create_pile_axial_force_figure(
        self,
        pile_result: 'PileResult',
        piles: List[Dict] = None,
        figsize: Tuple[float, float] = (9, 3.5),
        is_critical: bool = False
    ) -> Figure:
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        pile_no = pile_result.pile_no
        z = pile_result.get_z_values()
        nx_list, ny_list, nz_list = pile_result.get_forces()
        
                    
        ax0 = axes[0]
        self._draw_layout_subplot(ax0, piles, pile_no)
        
                              
        ax1 = axes[1]
        has_data = False
        max_info = []
        
                        
        if z and nz_list and any(v != 0 for v in nz_list):
            ax1.plot(nz_list, z, '-', linewidth=1.2, markersize=2, marker='o',
                color='green', label='Nz')
            max_idx = max(range(len(nz_list)), key=lambda i: abs(nz_list[i]))
            max_val, max_z = nz_list[max_idx], z[max_idx]
            ax1.plot(max_val, max_z, 'o', color='blue', 
                markersize=5, markeredgecolor='black', markeredgewidth=1.2)
            max_info.append(f'Nz最大: {max_val:.2f}kN @ Z={max_z:.2f}m')
            has_data = True
        
        if not has_data:
            ax1.text(0.5, 0.5, _plot_text('无桩身轴力数据'), ha='center', va='center',
                    fontsize=12, color='#888', transform=ax1.transAxes)
        ax1.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax1.set_xlabel(_plot_text('轴力 (kN)'), fontsize=9)
        ax1.set_ylabel(_plot_text('深度 Z (m)'), fontsize=9)
        ax1.set_title(_plot_text('轴力分布'), fontsize=10, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.invert_yaxis()
        if has_data:
            ax1.legend(loc='lower right', fontsize=7)
            if max_info:
                info_text = _plot_text('\n'.join(max_info))
                fig.text(0.40, 0.01, info_text, fontsize=8, ha='left', va='bottom',
                         color='red')
        
        title = f'桩 {pile_no} - 轴力'
        if is_critical:
            title += ' [最不利]'
        fig.suptitle(_plot_text(title), fontsize=11, fontweight='bold',
                    color='red' if is_critical else 'black')
        fig.subplots_adjust(top=0.880, bottom=0.145, left=0.080, right=0.950, hspace=0.200, wspace=0.250)
        
        return fig

    def create_pile_moment_figure(
        self,
        pile_result: 'PileResult',
        piles: List[Dict] = None,
        figsize: Tuple[float, float] = (9, 3.5),
        is_critical: bool = False
    ) -> Figure:
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        pile_no = pile_result.pile_no
        z = pile_result.get_z_values()
        mx_list, my_list = pile_result.get_moments()
        
                    
        ax0 = axes[0]
        self._draw_layout_subplot(ax0, piles, pile_no)
        
                              
        ax1 = axes[1]
        has_data = False
        max_info = []
        
        if z and mx_list and any(v != 0 for v in mx_list):
            ax1.plot(mx_list, z, '-', linewidth=1.2, markersize=2, marker='o',
                    color=PlotStyle.COLORS['force_x'], label='Mx')
            max_idx = max(range(len(mx_list)), key=lambda i: abs(mx_list[i]))
            max_val, max_z = mx_list[max_idx], z[max_idx]
            ax1.plot(max_val, max_z, 'o', color='#FFD700', 
                    markersize=5, markeredgecolor='black', markeredgewidth=0.5)
            max_info.append(f'Mx最大: {max_val:.2f}kN·m @ Z={max_z:.2f}m')
            has_data = True
        if z and my_list and any(v != 0 for v in my_list):
            ax1.plot(my_list, z, '-', linewidth=1.2, markersize=2, marker='s',
                    color=PlotStyle.COLORS['force_y'], label='My')
            max_idx = max(range(len(my_list)), key=lambda i: abs(my_list[i]))
            max_val, max_z = my_list[max_idx], z[max_idx]
            ax1.plot(max_val, max_z, 's', color='#32CD32', 
                    markersize=5, markeredgecolor='black', markeredgewidth=0.5)
            max_info.append(f'My最大: {max_val:.2f}kN·m @ Z={max_z:.2f}m')
            has_data = True
        
        if not has_data:
            ax1.text(0.5, 0.5, _plot_text('无桩身弯矩数据'), ha='center', va='center',
                    fontsize=12, color='#888', transform=ax1.transAxes)
        ax1.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax1.set_xlabel(_plot_text('弯矩 (kN·m)'), fontsize=9)
        ax1.set_ylabel(_plot_text('深度 Z (m)'), fontsize=9)
        ax1.set_title(_plot_text('弯矩分布'), fontsize=10, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.invert_yaxis()
        if has_data:
            leg = ax1.legend(loc='lower right', fontsize=7)
            if leg is not None:
                for t in leg.get_texts():
                    t.set_fontsize(7)
            if max_info:
                info_text = _plot_text('\n'.join(max_info))
                fig.text(0.48, 0.01, info_text, fontsize=8, ha='center', va='bottom',
                         color='red')
        
        title = f'桩 {pile_no} - 弯矩'
        if is_critical:
            title += ' [最不利]'
        fig.suptitle(_plot_text(title), fontsize=11, fontweight='bold',
                    color='red' if is_critical else 'black')
        fig.subplots_adjust(top=0.880, bottom=0.145, left=0.080, right=0.950, hspace=0.200, wspace=0.250)
        
        return fig

    def plot_pile_displacements(
        self,
        pile_result: 'PileResult',
        figsize: Tuple[float, float] = (12, 8)
    ) -> io.BytesIO:
        fig, axes = plt.subplots(1, 2, figsize=figsize, sharey=True)
        
        z = pile_result.get_z_values()
        ux_list, uy_list = pile_result.get_displacements()
        pile_no = pile_result.pile_no
        
              
        ax1 = axes[0]
        if ux_list:
            ax1.plot(ux_list, z, '-', linewidth=2,
                    color=PlotStyle.COLORS['force_x'], label='位移 Ux')
        if uy_list:
            ax1.plot(uy_list, z, '-', linewidth=2,
                    color=PlotStyle.COLORS['force_y'], label='位移 Uy')
        ax1.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax1.set_xlabel(_plot_text('水平位移 (m)'), fontsize=10)
        ax1.set_ylabel(_plot_text('深度 Z (m)'), fontsize=10)
        ax1.set_title(_plot_text('水平位移分布'), fontsize=11, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.invert_yaxis()
        ax1.legend(loc='best')
        
            
        ax2 = axes[1]
        sx_list = [p.sx for p in pile_result.body]
        sy_list = [p.sy for p in pile_result.body]
        
        if sx_list:
            ax2.plot(sx_list, z, '-', linewidth=2,
                    color=PlotStyle.COLORS['force_x'], label='转角 θx')
        if sy_list:
            ax2.plot(sy_list, z, '-', linewidth=2,
                    color=PlotStyle.COLORS['force_y'], label='转角 θy')
        ax2.axvline(x=0, color='gray', linestyle='--', linewidth=0.8)
        ax2.set_xlabel(_plot_text('转角 (rad)'), fontsize=10)
        ax2.set_title(_plot_text('转角分布'), fontsize=11, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='best')
        
        fig.suptitle(_plot_text(f'第 {pile_no} 号桩 - 桩身位移分布图'),
                    fontsize=14, fontweight='bold')
        plt.subplots_adjust(top=0.90, bottom=0.10, left=0.08, right=0.95, wspace=0.25)
        
        return self._save_to_buffer(fig)
    
   
