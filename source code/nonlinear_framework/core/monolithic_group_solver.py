# -*- coding: UTF-8 -*-
import numpy as np
import openseespy.opensees as ops

try:
    from .py_model import (py_api_method_for_sand, py_sand, py_soft_clay_soil,
                           py_submerged_stiff_clay, py_dry_stiff_clay,
                           py_weak_rock, py_elastic, generate_py_curve,
                           stiff_clay_with_water_A,
                           generate_reese_sand_py_points)
    from .tz_model import (tz_sand_api, tz_clay_api, tz_drilled_sand,
                           tz_drilled_clay, tz_elastic, generate_tz_curve)
    from .qz_model import (qz_sand_api, qz_clay_api, qz_drilled_sand,
                           qz_drilled_clay, qz_elastic, generate_qz_curve)
except Exception:
    from py_model import (py_api_method_for_sand, py_sand, py_soft_clay_soil,
                          py_submerged_stiff_clay, py_dry_stiff_clay,
                          py_weak_rock, py_elastic, generate_py_curve,
                          stiff_clay_with_water_A,
                          generate_reese_sand_py_points)
    from tz_model import (tz_sand_api, tz_clay_api, tz_drilled_sand,
                          tz_drilled_clay, tz_elastic, generate_tz_curve)
    from qz_model import (qz_sand_api, qz_clay_api, qz_drilled_sand,
                          qz_drilled_clay, qz_elastic, generate_qz_curve)


class MonolithicGroupPileSolver:

    def __init__(self, ele_size=None, spring_model_mode='multilinear'):
        self.piles = []
        self.lat_layers = []           
        self.ax_layers = []            
        self.tip_soil = None            
        self.ele_size = ele_size
        self.spring_model_mode = str(spring_model_mode or 'multilinear').lower()
        self.results = None
        self._mat_tag = 1
        self._ele_tag = 1
        self._node_tag = 2000000
        self._node_tag = 2000000
        self.explicit_coupling = None

    @staticmethod
    def _normalize_head_connectivity(head_connectivity):
        """Normalize pile-cap connectivity labels to a small supported set."""
        if head_connectivity is None:
            return 'fixed'

        key = str(head_connectivity).strip().lower().replace('-', '_')
        aliases = {
            'fixed': 'fixed',
            'rigid': 'fixed',
            'beam': 'fixed',
            'pinned': 'pinned',
            'pin': 'pinned',
            'hinged': 'pinned',
            'hinge': 'pinned',
            'restrained': 'restrained',
            'partial': 'restrained',
            'partial_fixity': 'restrained',
        }
        if key not in aliases:
            raise ValueError(f"Unsupported head_connectivity: {head_connectivity}")
        return aliases[key]

    @staticmethod
    def _rotation_matrix_about_axis(axis, angle_deg):
        """Rodrigues rotation about a unit axis."""
        angle_rad = np.radians(angle_deg)
        axis = np.asarray(axis, dtype=float)
        axis_norm = np.linalg.norm(axis)
        if axis_norm < 1e-12 or abs(angle_rad) < 1e-12:
            return np.eye(3)
        axis = axis / axis_norm
        x, y, z = axis
        c = np.cos(angle_rad)
        s = np.sin(angle_rad)
        C = 1.0 - c
        return np.array([
            [c + x * x * C, x * y * C - z * s, x * z * C + y * s],
            [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
            [z * x * C - y * s, z * y * C + x * s, c + z * z * C],
        ])

    @classmethod
    def _build_rspile_axes(cls, alpha_deg, beta_from_horiz_deg, rotation_angle_deg):
        """
        Build RSPile-style local axes.

        Official convention:
        - Alpha: clockwise from global +Y about global Z
        - Beta: angle from horizontal plane to pile axis z'
        - Rotation Angle: counterclockwise rotation about z'
        """
        alpha_rad = np.radians(alpha_deg)
        beta_rad = np.radians(beta_from_horiz_deg)

        trend = np.array([np.sin(alpha_rad), np.cos(alpha_rad), 0.0])
        z_rspile = np.array([
            np.cos(beta_rad) * np.sin(alpha_rad),
            np.cos(beta_rad) * np.cos(alpha_rad),
            -np.sin(beta_rad),
        ])
        z_rspile = z_rspile / np.linalg.norm(z_rspile)

        # Theta = 0: Y' lies in the trend plane.
        y0 = trend - np.dot(trend, z_rspile) * z_rspile
        if np.linalg.norm(y0) < 1e-12:
            ref = np.array([0.0, 1.0, 0.0])
            y0 = ref - np.dot(ref, z_rspile) * z_rspile
        y0 = y0 / np.linalg.norm(y0)

        # Right-handed local frame: x' = y' x z'
        x0 = np.cross(y0, z_rspile)
        x0 = x0 / np.linalg.norm(x0)

        rot = cls._rotation_matrix_about_axis(z_rspile, rotation_angle_deg)
        x_rspile = rot @ x0
        y_rspile = rot @ y0
        x_rspile = x_rspile / np.linalg.norm(x_rspile)
        y_rspile = y_rspile / np.linalg.norm(y_rspile)
        return x_rspile, y_rspile, z_rspile

    # =================================================================
          
    # =================================================================
    def add_pile(self, x, y, pile_length, pile_diameter, E_pile,
                 I_pile=None, A_pile=None,
                 alpha_deg=0.0, beta_from_horiz_deg=90.0,
                 rotation_angle_deg=0.0,
                 free_length=0.0, head_elevation=0.0, p_multiplier=1.0,
                 y_multiplier=1.0,
                 mesh_positions=None,
                 head_connectivity='fixed',
                 rotational_stiffness=None,
                 section_mode='elastic',
                 fiber_section_library=None,
                 fiber_section_segments=None,
                 tip_area_m2=None):
        alpha_rad = np.radians(alpha_deg)
        beta_rad = np.radians(beta_from_horiz_deg)

        D = pile_diameter
        if I_pile is None:
            I_pile = np.pi * D**4 / 64
        if A_pile is None:
            A_pile = np.pi * D**2 / 4

        rspile_x, rspile_y, rspile_z = self._build_rspile_axes(
            alpha_deg, beta_from_horiz_deg, rotation_angle_deg
        )
        axis = rspile_z
        perp = rspile_y.copy()
        binorm = rspile_x.copy()

        # OpenSees 3D geomTransf('Linear', ..., vecxz) uses:
        #   local x = element axis
        #   local y = normalize(vecxz x x)
        #   local z = x x y
        # With vecxz=perp, the actual local y/z axes are not simply perp/binorm.
        local_x = axis
        local_y = np.cross(perp, local_x)
        norm_y = np.linalg.norm(local_y)
        if norm_y > 1e-10:
            local_y = local_y / norm_y
        else:
            local_y = binorm.copy()
        local_z = np.cross(local_x, local_y)
        norm_z = np.linalg.norm(local_z)
        if norm_z > 1e-10:
            local_z = local_z / norm_z
        else:
            local_z = perp.copy()

             
        total_length = free_length + pile_length
        if mesh_positions is not None and len(mesh_positions) >= 2:
            node_arc_lengths = np.array([float(v) for v in mesh_positions], dtype=float)
            node_arc_lengths[0] = 0.0
            node_arc_lengths[-1] = total_length
        else:
            es = self.ele_size if self.ele_size else total_length / 80.0
            n_eles = max(int(round(total_length / es)), 10)
            node_arc_lengths = np.linspace(0.0, total_length, n_eles + 1)
        segment_lengths = np.diff(node_arc_lengths)
        n_eles = len(segment_lengths)
        n_nodes = n_eles + 1
        n_free = int(np.searchsorted(node_arc_lengths, free_length, side='left'))
        node_tributary_lengths = np.zeros(n_nodes)
        for i in range(n_nodes):
            left = 0.5 * segment_lengths[i - 1] if i > 0 else 0.0
            right = 0.5 * segment_lengths[i] if i < n_eles else 0.0
            node_tributary_lengths[i] = left + right

        self.piles.append({
            'x': x, 'y': y, 'L': pile_length, 'D': D, 'E': E_pile,
            'I': I_pile, 'A': A_pile, 'p_mult': p_multiplier,
            'y_mult': y_multiplier,
            'section_mode': str(section_mode or 'elastic'),
            'fiber_section_library': list(fiber_section_library or []),
            'fiber_section_segments': list(fiber_section_segments or []),
            'head_connectivity': self._normalize_head_connectivity(head_connectivity),
            'rotational_stiffness': rotational_stiffness,
            'alpha_rad': alpha_rad, 'beta_rad': beta_rad,
            'axis': axis, 'perp': perp, 'binorm': binorm,
            'local_x': local_x, 'local_y': local_y, 'local_z': local_z,
            'rspile_x': rspile_x, 'rspile_y': rspile_y, 'rspile_z': rspile_z,
            'rotation_angle_deg': rotation_angle_deg,
            'free_length': free_length, 'head_elevation': head_elevation,
            'tip_area_m2': tip_area_m2,
            'total_length': total_length,
            'n_eles': n_eles, 'n_nodes': n_nodes,
            'ele_size': float(np.mean(segment_lengths)) if n_eles else total_length, 'n_free': n_free,
            'node_arc_lengths': node_arc_lengths, 'segment_lengths': segment_lengths,
            'node_tributary_lengths': node_tributary_lengths,
            'cos_beta': np.sin(beta_rad),
        })

    def set_p_multipliers(self, p_multipliers):
        """Assign theoretical p-y reduction factors (group effect fm)."""
        if len(p_multipliers) != len(self.piles):
            raise ValueError("Length of p_multipliers must match number of piles.")
        for pile, p_mult in zip(self.piles, p_multipliers):
            pile['p_mult'] = float(p_mult)

    def set_y_multipliers(self, y_multipliers):
        """Retained for compatibility; strict-theory solver keeps y-multipliers neutral."""
        if len(y_multipliers) != len(self.piles):
            raise ValueError("Length of y_multipliers must match number of piles.")
        for pile in self.piles:
            pile['y_mult'] = 1.0

    def auto_assign_row_reduced_multipliers(self, load_direction_deg=0.0,
                                            leading_factor=0.90,
                                            trailing_factor=0.70,
                                            leading_y_multiplier=None,
                                            trailing_y_multiplier=None,
                                            elastic_profile=None,
                                            elastic_intensity=2.0,
                                            leading_elastic_intensity=None,
                                            trailing_elastic_intensity=None,
                                            upper_zone_diameters=10.0,
                                            lower_zone_diameters=24.0,
                                            leading_upper_zone_diameters=None,
                                            trailing_upper_zone_diameters=None,
                                            leading_lower_zone_diameters=None,
                                            trailing_lower_zone_diameters=None,
                                            row_tolerance=None):
        """Compatibility shim for older callers.

        Row-based empirical reduction is intentionally disabled in the
        strict-theory solver. Official group-effect reduction should be
        introduced through pairwise fm multipliers instead.
        """
        if not self.piles:
            return []
        self.set_p_multipliers([1.0] * len(self.piles))
        self.set_y_multipliers([1.0] * len(self.piles))
        return [1.0] * len(self.piles)

    @staticmethod
    def _beta_side_by_side(s_over_b):
        """RSPile side-by-side reduction factor."""
        if s_over_b >= 3.75:
            return 1.0
        if s_over_b <= 1.0:
            return 0.64
        return min(0.64 * (s_over_b ** 0.34), 1.0)

    @staticmethod
    def _beta_inline_leading(s_over_b):
        """RSPile in-line leading reduction factor."""
        if s_over_b >= 4.0:
            return 1.0
        if s_over_b <= 1.0:
            return 0.7
        return min(0.7 * (s_over_b ** 0.26), 1.0)

    @staticmethod
    def _beta_inline_trailing(s_over_b):
        """RSPile in-line trailing reduction factor."""
        if s_over_b >= 7.0:
            return 1.0
        if s_over_b <= 1.0:
            return 0.48
        return min(0.48 * (s_over_b ** 0.38), 1.0)

    @staticmethod
    def _beta_skewed(beta_inline, beta_side, theta_rad):
        """Elliptic interpolation used in RSPile skewed interaction."""
        cos_t = np.cos(theta_rad)
        sin_t = np.sin(theta_rad)
        return np.sqrt(beta_inline**2 * cos_t**2 + beta_side**2 * sin_t**2)

    def auto_assign_pairwise_multipliers(self, load_direction_deg=0.0,
                                         combine='product',
                                         min_factor=0.35,
                                         assign_elastic_y=False):
        """Apply official-style pairwise group-effect multipliers to p-y resistance only."""
        if not self.piles:
            return []

        theta = np.radians(load_direction_deg)
        load_dir = np.array([np.cos(theta), np.sin(theta)], dtype=float)
        if np.linalg.norm(load_dir) < 1.0e-12:
            load_dir = np.array([1.0, 0.0], dtype=float)

        p_factors = []
        for i, pile_i in enumerate(self.piles):
            xi = np.array([pile_i['x'], pile_i['y']], dtype=float)
            Di = max(float(pile_i['D']), 1.0e-9)
            pair_factors = []
            for j, pile_j in enumerate(self.piles):
                if i == j:
                    continue
                xj = np.array([pile_j['x'], pile_j['y']], dtype=float)
                rel = xi - xj
                spacing = float(np.linalg.norm(rel))
                if spacing < 1.0e-9:
                    continue

                s_over_b = spacing / Di
                beta_side = self._beta_side_by_side(s_over_b)
                beta_lead = self._beta_inline_leading(s_over_b)
                beta_trail = self._beta_inline_trailing(s_over_b)

                proj = float(np.dot(rel, load_dir))
                theta_rel = np.arccos(np.clip(abs(proj) / spacing, 0.0, 1.0))
                beta_inline = beta_lead if proj >= 0.0 else beta_trail
                pair_beta = self._beta_skewed(beta_inline, beta_side, theta_rel)
                pair_factors.append(float(np.clip(pair_beta, min_factor, 1.0)))

            if not pair_factors:
                p_factors.append(1.0)
            elif combine == 'minimum':
                p_factors.append(min(pair_factors))
            else:
                p_factors.append(float(np.prod(pair_factors)))

        self.set_p_multipliers(p_factors)
        self.set_y_multipliers([1.0] * len(self.piles))
        return p_factors

    @staticmethod
    def _resolve_p_multiplier(p_mult, z_vert=None, layer=None):
        """Resolve scalar or structured p-multiplier specifications."""
        if isinstance(p_mult, (int, float, np.integer, np.floating)):
            return float(p_mult)

        if isinstance(p_mult, dict):
            value = float(p_mult.get('default', 1.0))

            if z_vert is not None:
                for band in p_mult.get('depth_bands', []):
                    if len(band) != 3:
                        continue
                    z_top, z_bottom, band_value = band
                    if z_top <= z_vert <= z_bottom:
                        value *= float(band_value)

            if layer is not None:
                layer_type = layer.get('type')
                layer_factor = p_mult.get('by_type', {}).get(layer_type)
                if layer_factor is not None:
                    value *= float(layer_factor)

            return value

        return float(p_mult)

    @staticmethod
    def _resolve_y_multiplier(y_mult, z_vert=None, layer=None):
        """Resolve scalar or structured y-multiplier specifications."""
        if isinstance(y_mult, (int, float, np.integer, np.floating)):
            return max(1.0e-6, float(y_mult))

        if isinstance(y_mult, dict):
            value = float(y_mult.get('default', 1.0))

            if z_vert is not None:
                for band in y_mult.get('depth_bands', []):
                    if len(band) != 3:
                        continue
                    z_top, z_bottom, band_value = band
                    if z_top <= z_vert <= z_bottom:
                        value *= float(band_value)

            if layer is not None:
                layer_type = layer.get('type')
                layer_factor = y_mult.get('by_type', {}).get(layer_type)
                if layer_factor is not None:
                    value *= float(layer_factor)

            return max(1.0e-6, value)

        return 1.0

    def _build_elastic_group_y_profile(self, pile_diameter, p_factor,
                                       intensity=2.0,
                                       upper_zone_diameters=10.0,
                                       lower_zone_diameters=24.0):
        """Build a depth-banded y-multiplier profile for sandy working zones.

        The profile stretches only sandy layers and only over the upper and
        middle working depths of each sandy layer. This is intended to capture
        the RSPile-style elastic group effect without changing ultimate p.
        """
        factor = max(float(p_factor), 1.0e-6)
        if factor >= 0.999:
            return 1.0

        upper_mult = 1.0 + float(intensity) * (1.0 / factor - 1.0)
        lower_mult = 1.0 + 0.8 * float(intensity) * (1.0 / factor - 1.0)
        upper_len = float(upper_zone_diameters) * float(pile_diameter)
        lower_len = float(lower_zone_diameters) * float(pile_diameter)

        depth_bands = []
        sand_types = {'Sand', 'API Method for Sand', 'API Sand'}
        for layer in self.lat_layers:
            if layer['type'] not in sand_types:
                continue
            z0 = float(layer['z_top'])
            z1 = float(layer['z_bottom'])
            upper_end = min(z1, z0 + upper_len)
            lower_end = min(z1, z0 + lower_len)
            if upper_end > z0:
                depth_bands.append((z0, upper_end, upper_mult))
            if lower_end > upper_end:
                depth_bands.append((upper_end, lower_end, lower_mult))

        if not depth_bands:
            return max(1.0, upper_mult)

        return {
            'default': 1.0,
            'depth_bands': depth_bands,
        }

    def add_lateral_soil_layer(self, z_top, z_bottom, soil_type, **params):
        self.lat_layers.append({
            'z_top': z_top, 'z_bottom': z_bottom,
            'type': soil_type, 'params': params
        })

    def add_axial_soil_layer(self, z_top, z_bottom, soil_type, **params):
        self.ax_layers.append({
            'z_top': z_top, 'z_bottom': z_bottom,
            'type': soil_type, 'params': params
        })

    def set_tip_soil(self, soil_type, **params):
        self.tip_soil = {'type': soil_type, 'params': params}

    # =================================================================
           
    # =================================================================
    def _compute_sigma_v(self, z):
        sigma_v = 0.0
        sorted_layers = sorted(self.ax_layers, key=lambda l: l['z_top'])
        for layer in sorted_layers:
            if z <= layer['z_top']:
                break
            gamma = layer['params'].get('gamma',
                    layer['params'].get('gammaEff', 18.0))
            z_bot = min(z, layer['z_bottom'])
            sigma_v += gamma * max(0, z_bot - layer['z_top'])
            if z <= layer['z_bottom']:
                break
        return max(sigma_v, 0.01)

    def _get_ax_soil_at(self, z):
        for layer in self.ax_layers:
            if layer['z_top'] <= z <= layer['z_bottom']:
                return layer
        return None

    def _get_tz_params(self, z, D, ele_size):
        sigma_v = self._compute_sigma_v(z)
        layer = self._get_ax_soil_at(z)
        if layer is None:
            return 0.01, 0.001

        p = layer['params']
        st = layer['type']
        if st in ('API Sand', 'Sand'):
            return tz_sand_api(
                phiDegree=p.get('phiDegree', p.get('phi', 30)),
                d=D, sigmaV=sigma_v, z=z, elelength=ele_size,
                K=p.get('K', 0.8),
                limit_fmax=p.get('limit_fmax', True),
                max_unit_skin_friction=p.get('max_unit_skin_friction'))
        elif st in ('API Clay', 'Clay'):
            return tz_clay_api(cu=p.get('cu', 50), d=D,
                               sigmaV=sigma_v, z=z, elelength=ele_size,
                               max_unit_skin_friction=p.get('max_unit_skin_friction'))
        elif st == 'Drilled Sand':
            return tz_drilled_sand(phiDegree=p.get('phiDegree', 30),
                                   d=D, sigmaV=sigma_v, z=z,
                                   elelength=ele_size)
        elif st == 'Drilled Clay':
            return tz_drilled_clay(cu=p.get('cu', 50), d=D,
                                   sigmaV=sigma_v, z=z,
                                   elelength=ele_size)
        elif st == 'Elastic':
            return tz_elastic(ks=p.get('ks', 1e5), d=D,
                              elelength=ele_size)
        return 0.01, 0.001

    def _get_qz_params(self, D, L, tip_area_m2=None):
        if self.tip_soil is None:
            return 0.01, 0.001
        p = self.tip_soil['params']
        if tip_area_m2 is not None and float(tip_area_m2) > 0.0:
            p = dict(p)
            p['A_base'] = float(tip_area_m2)
            p['A_tip'] = float(tip_area_m2)
        st = self.tip_soil['type']
        sigma_v = self._compute_sigma_v(L)
        if st in ('API Sand', 'Sand'):
            return qz_sand_api(phiDegree=p.get('phiDegree', p.get('phi', 30)),
                               d=D, sigmaV=sigma_v,
                               Nq=p.get('Nq'), A_base=p.get('A_base'),
                               max_unit_end_bearing=p.get('max_unit_end_bearing'))
        elif st in ('API Clay', 'Clay'):
            return qz_clay_api(cu=p.get('cu', 100), d=D,
                               A_base=p.get('A_base'),
                               max_unit_end_bearing=p.get('max_unit_end_bearing'))
        elif st == 'Drilled Sand':
            return qz_drilled_sand(phiDegree=p.get('phiDegree', 30), d=D,
                                   sigmaV=sigma_v, G=p.get('G'))
        elif st == 'Drilled Clay':
            return qz_drilled_clay(cu=p.get('cu', 100), d=D,
                                   sigmaV=sigma_v)
        elif st == 'Elastic':
            return qz_elastic(kb=p.get('kb', 1e5), d=D)
        return 0.01, 0.001

                    
    def _eval_pult_for_layer(self, layer, z_eff, D):
        p = layer['params']
        st = layer['type']
        gammaEff = p.get('gammaEff', 0.0)

        if z_eff <= 0.0:
            if st == 'Elastic':
                return 0.0, None
            return 0.0, 1.0e-6

        if st == 'API Method for Sand':
            return py_api_method_for_sand(z_eff, gammaEff,
                       p.get('phiDegree', p.get('phi', 30)), D, p.get('k_modulus', p.get('kpy', 0.0)),
                       p.get('is_cyclic', False))
        elif st == 'Sand':
            return py_sand(z_eff, gammaEff,
                       p.get('phiDegree', p.get('phi', 30)), D, p.get('kpy', p.get('k_modulus', 0.0)),
                       p.get('is_cyclic', False))
        elif st in ('Soft Clay Soil', 'Clay'):
            return py_soft_clay_soil(z_eff, gammaEff, p.get('cu', 50), D,
                                     p.get('eps50', 0.01), p.get('J', 0.5),
                                     p.get('is_cyclic', False))
        elif st == 'Submerged Stiff Clay':
            return py_submerged_stiff_clay(z_eff, gammaEff, p.get('cu', 100),
                       p.get('ca', p.get('cu', 100)), D, p.get('eps50', 0.005))
        elif st in ('Dry Stiff Clay', 'Modified Stiff Clay without Free Water', 'Stiff Clay'):
            return py_dry_stiff_clay(z_eff, gammaEff, p.get('cu', 100),
                       p.get('ca', p.get('cu', 100)), D,
                       p.get('eps50', 0.005), p.get('J', 0.5))
        elif st == 'Weak Rock':
            return py_weak_rock(z_eff, gammaEff, p.get('qu', 1000), D,
                       p.get('krm', 0.0005), p.get('Eir'), p.get('RQD'))
        elif st == 'Elastic':
            k = py_elastic(z_eff, p['kh'], D)
            return k, None
        return 0.01, 0.001

    def _calc_georgiadis_depths(self, D):
        if not self.lat_layers:
            return
        dz = 0.01
        self.lat_layers[0]['z_eq_top'] = 0.0
        for i in range(len(self.lat_layers)):
            layer = self.lat_layers[i]
            H = layer['z_bottom'] - layer['z_top']
            layer['z_eq_bottom'] = layer['z_eq_top'] + H
            if i == len(self.lat_layers) - 1:
                break
                          
            n_pts = max(int(layer['z_eq_bottom'] / dz) + 1, 10)
            z_arr = np.linspace(0, layer['z_eq_bottom'], n_pts)
            pult_arr = np.array([self._eval_pult_for_layer(layer, z, D)[0]
                                 for z in z_arr])
            F_i = np.trapz(pult_arr, z_arr)
                         
            next_layer = self.lat_layers[i + 1]
            Z_max = min(100.0, layer['z_eq_bottom'] * 2)
            n_pts_next = max(int(Z_max / dz) + 1, 10)
            Z_arr = np.linspace(0, Z_max, n_pts_next)
            pult_next = np.array([self._eval_pult_for_layer(next_layer, Z, D)[0]
                                  for Z in Z_arr])
            cumF = np.array([np.trapz(pult_next[:k+1], Z_arr[:k+1])
                             for k in range(len(Z_arr))])
            if F_i > cumF[-1]:
                Z_eq = Z_arr[-1]
            elif F_i <= cumF[0]:
                Z_eq = 0.0
            else:
                Z_eq = np.interp(F_i, cumF, Z_arr)
            next_layer['z_eq_top'] = Z_eq

    def _get_py_at_depth(self, z_depth_vert, D):
        for layer in self.lat_layers:
            if layer['z_top'] <= z_depth_vert <= layer['z_bottom']:
                z_eq_top = layer.get('z_eq_top', 0.0)
                z_eff = z_eq_top + (z_depth_vert - layer['z_top'])
                return self._eval_pult_for_layer(layer, z_eff, D), layer, z_eff
        return (0.01, 0.001), None, z_depth_vert

    # =================================================================
          
    # =================================================================
    def _next_mat(self):
        t = self._mat_tag; self._mat_tag += 1; return t

    def _next_ele(self):
        t = self._ele_tag; self._ele_tag += 1; return t

    def _next_node(self):
        t = self._node_tag; self._node_tag += 1; return t

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    def _concrete_tension_parameters(self, fc, Ec):
        fc_mpa = abs(float(fc)) / 1000.0
        if fc_mpa <= 1.0e-12 or Ec <= 1.0e-12:
            return 0.0, 0.0
        fct = 0.33 * math.sqrt(fc_mpa) * 1000.0
        et = max(10.0 * fct / Ec, 1.0e-5)
        return fct, et

    def _create_fiber_uniaxial_material(self, kind, params, elastic_modulus):
        mat_tag = self._next_mat()
        params = dict(params or {})
        if kind == 'steel':
            fy = abs(self._safe_float(params.get('fy --Yield stress in tension(kPa)'), 0.0))
            fu = abs(self._safe_float(params.get('fu --Ultimate stress in tension(kPa)'), fy))
            Es = self._safe_float(params.get('Es--Initial elastic tangent(kPa)'), elastic_modulus)
            Esh = self._safe_float(params.get('Esh--Tangent at initial strain hardening(kPa)'), 0.0)
            esh = abs(self._safe_float(params.get('esh--Strain corresponding to initial strain hardening'), 0.015))
            eult = abs(self._safe_float(params.get('eult--Strain at peak stress'), max(esh, 0.1)))
            if fy > 1.0e-6 and fu >= fy and Es > 1.0e-6:
                ops.uniaxialMaterial(
                    'ReinforcingSteel',
                    mat_tag,
                    fy,
                    fu,
                    Es,
                    max(Esh, 1.0e-6),
                    esh,
                    max(eult, esh + 1.0e-6),
                )
            else:
                ops.uniaxialMaterial('Elastic', mat_tag, max(Es, 1.0))
            return mat_tag

        fc = self._safe_float(params.get('concreteCompressiveStrengthAt28Days-fc(kPa)'), 0.0)
        epsc0 = self._safe_float(params.get('concreteStrainAtMaximumStrength-ec'), -0.002)
        epsu = self._safe_float(params.get('concreteStrainAtCrushingStrength-ecu'), -0.004)
        Ec = self._safe_float(params.get('initialStiffness-Ec(kPa)'), elastic_modulus)
        if fc < -1.0e-6 and epsc0 < -1.0e-8 and epsu < epsc0:
            fct, et = self._concrete_tension_parameters(fc, Ec)
            ops.uniaxialMaterial('Concrete04', mat_tag, fc, epsc0, epsu, max(Ec, 1.0), fct, et)
        else:
            ops.uniaxialMaterial('Elastic', mat_tag, max(Ec, 1.0))
        return mat_tag

    def _resolve_fiber_section_library(self, pile):
        if str(pile.get('section_mode', 'elastic')) != 'fiber':
            return {}, []
        library = {
            str(item.get('name', '')): dict(item)
            for item in pile.get('fiber_section_library', [])
            if isinstance(item, dict) and str(item.get('name', '')).strip()
        }
        segments = []
        for item in pile.get('fiber_section_segments', []):
            if not isinstance(item, dict):
                continue
            section_name = str(item.get('section_name', '')).strip()
            if section_name and section_name in library:
                top = min(
                    self._safe_float(item.get('top_m', 0.0)),
                    self._safe_float(item.get('bottom_m', 0.0)),
                )
                bottom = max(
                    self._safe_float(item.get('top_m', 0.0)),
                    self._safe_float(item.get('bottom_m', 0.0)),
                )
                segments.append({
                    'top_m': top,
                    'bottom_m': bottom,
                    'section_name': section_name,
                })
        if not segments and len(library) == 1:
            only_name = next(iter(library))
            segments = [{
                'top_m': 0.0,
                'bottom_m': self._safe_float(pile.get('total_length', pile.get('L', 0.0))),
                'section_name': only_name,
            }]
        return library, segments

    def _build_fiber_section_tags(self, pile):
        library, segments = self._resolve_fiber_section_library(pile)
        if not library or not segments:
            return None, None

        section_tags = {}
        poisson = 0.25
        G_shear = pile['E'] / (2.0 * (1.0 + poisson))
        gj_default = max(G_shear * max(pile.get('I', 0.0) * 2.0, 1.0e-12), 1.0e-6)

        for section_name, section_def in library.items():
            mats = dict(section_def.get('material_params', {}) or {})
            core_mat = self._create_fiber_uniaxial_material('concrete', mats.get('core_concrete', {}), pile['E'])
            cover_mat = self._create_fiber_uniaxial_material('concrete', mats.get('cover_concrete', {}), pile['E'])
            rebar_mat = self._create_fiber_uniaxial_material('steel', mats.get('rebar', {}), pile['E'])
            sec_tag = self._next_mat()
            gj_value = max(
                G_shear * max(
                    self._safe_float(
                        dict(section_def.get('summary', {}) or {}).get('j_approx_m4', 0.0),
                        pile.get('I', 0.0) * 2.0,
                    ),
                    1.0e-12,
                ),
                gj_default,
            )
            ops.section('Fiber', sec_tag, '-GJ', gj_value)
            fibers = dict(section_def.get('fibers', {}) or {})
            for row in fibers.get('core', []) or []:
                ops.fiber(
                    self._safe_float(row.get('y_m', 0.0)),
                    self._safe_float(row.get('z_m', 0.0)),
                    max(self._safe_float(row.get('area_m2', 0.0)), 1.0e-12),
                    core_mat,
                )
            for role in ('inner_cover', 'outer_cover'):
                for row in fibers.get(role, []) or []:
                    ops.fiber(
                        self._safe_float(row.get('y_m', 0.0)),
                        self._safe_float(row.get('z_m', 0.0)),
                        max(self._safe_float(row.get('area_m2', 0.0)), 1.0e-12),
                        cover_mat,
                    )
            for group in fibers.get('rebar_groups', []) or []:
                for row in group.get('fibers', []) or []:
                    ops.fiber(
                        self._safe_float(row.get('y_m', 0.0)),
                        self._safe_float(row.get('z_m', 0.0)),
                        max(self._safe_float(row.get('area_m2', 0.0)), 1.0e-12),
                        rebar_mat,
                    )
            bi_tag = self._next_mat()
            ops.beamIntegration('Lobatto', bi_tag, sec_tag, 5)
            section_tags[section_name] = {
                'section_tag': sec_tag,
                'integration_tag': bi_tag,
            }
        return section_tags, segments

    def _integration_tag_for_position(self, arc_length, section_tags, segments):
        if not section_tags or not segments:
            return None
        for segment in segments:
            if segment['top_m'] - 1.0e-9 <= arc_length <= segment['bottom_m'] + 1.0e-9:
                info = section_tags.get(segment['section_name'])
                if info:
                    return info['integration_tag']
        info = section_tags.get(segments[-1]['section_name'])
        return info['integration_tag'] if info else None

    def configure_explicit_lateral_coupling(self, load_direction_deg=0.0,
                                            coupling_ratio=0.30,
                                            upper_zone_diameters=8.0,
                                            lower_zone_diameters=20.0,
                                            leading_upper_zone_diameters=None,
                                            leading_lower_zone_diameters=None,
                                            trailing_upper_zone_diameters=None,
                                            trailing_lower_zone_diameters=None,
                                            leading_scale=None,
                                            trailing_scale=None,
                                            shared_ground_ratio=0.15,
                                            working_stiffness_ratio=0.65,
                                            auto_scale_from_p=True,
                                            auto_scale_gain=1.0,
                                            column_tolerance=None):
        """Compatibility shim; strict-theory solver disables explicit lateral coupling."""
        self.explicit_coupling = None

    def _cluster_piles_by_projection(self, direction_deg=0.0, tolerance=None, use_perpendicular=False):
        if not self.piles:
            return []
        ang = np.radians(direction_deg)
        unit = np.array([np.cos(ang), np.sin(ang)], dtype=float)
        if use_perpendicular:
            unit = np.array([-unit[1], unit[0]], dtype=float)
        if tolerance is None:
            tolerance = max(p['D'] for p in self.piles) * 0.5

        values = []
        for idx, pile in enumerate(self.piles):
            xy = np.array([pile['x'], pile['y']], dtype=float)
            values.append((idx, float(np.dot(xy, unit))))
        values.sort(key=lambda item: item[1], reverse=True)

        groups = []
        for idx, proj in values:
            placed = False
            for group in groups:
                if abs(proj - group['center']) <= tolerance:
                    group['members'].append(idx)
                    group['values'].append(proj)
                    group['center'] = float(np.mean(group['values']))
                    placed = True
                    break
            if not placed:
                groups.append({'center': proj, 'members': [idx], 'values': [proj]})
        groups.sort(key=lambda group: group['center'], reverse=True)
        return groups

    def _explicit_coupling_weight(self, z_vert, pile_diameter, layer, cfg, row_role=None):
        if layer is None:
            return 0.0
        soil_type = layer.get('type', '')
        if soil_type not in ('Sand', 'API Method for Sand', 'API Sand'):
            return 0.0
        upper_d = cfg['upper_zone_diameters']
        lower_d = cfg['lower_zone_diameters']
        if row_role == 'leading':
            upper_d = cfg.get('leading_upper_zone_diameters', upper_d) or upper_d
            lower_d = cfg.get('leading_lower_zone_diameters', lower_d) or lower_d
        elif row_role == 'trailing':
            upper_d = cfg.get('trailing_upper_zone_diameters', upper_d) or upper_d
            lower_d = cfg.get('trailing_lower_zone_diameters', lower_d) or lower_d
        upper = upper_d * pile_diameter
        lower = lower_d * pile_diameter
        if z_vert <= 0.0:
            return 0.0
        if z_vert <= upper:
            return 1.0
        if z_vert <= lower:
            span = max(lower - upper, 1.0e-9)
            return max(0.0, 1.0 - (z_vert - upper) / span)
        return 0.0

    def _explicit_local_py_scale(self, z_vert, pile_diameter, layer, row_role=None):
        return 1.0

    def _build_explicit_lateral_coupling(self, pile_node_map, verbose=False):
        return []

    def _create_multilinear_sym(self, mat_tag, x_pts, y_pts):
        x_neg = -x_pts[::-1][:-1]
        y_neg = -y_pts[::-1][:-1]
        x_all = np.concatenate([x_neg, x_pts])
        y_all = np.concatenate([y_neg, y_pts])
        ops.uniaxialMaterial('ElasticMultiLinear', mat_tag,
                             '-strain', *x_all.tolist(),
                             '-stress', *y_all.tolist())

    @staticmethod
    def _native_axial_soil_type(soil_type):
        return 1 if soil_type in ('API Clay', 'Drilled Clay', 'Clay') else 2

    @staticmethod
    def _native_py_soil_type(soil_type):
        if soil_type in (
            'Soft Clay Soil',
            'Submerged Stiff Clay',
            'Dry Stiff Clay',
            'Modified Stiff Clay without Free Water',
            'Clay',
            'Stiff Clay',
        ):
            return 1
        if soil_type in ('API Method for Sand', 'Sand'):
            return 2
        return None

    # =================================================================
             
    # =================================================================
    def build_and_analyze(self, Fx=0, Fy=0, Fz=0, Mx=0, My=0, Mz=0,
                          n_steps=20, cap_fixity='2D', verbose=True,
                          cap_reference=None, load_location=None):
        if verbose:
            print("=" * 60)
            print("Monolithic 3D Group Pile Analysis (RSPile-Compliant)")
            print(f"  Piles: {len(self.piles)}")
            print(f"  Loads: Fx={Fx:.1f}, Fy={Fy:.1f}, Fz={Fz:.1f}")
            print(f"         Mx={Mx:.1f}, My={My:.1f}, Mz={Mz:.1f}")
            print(f"  Mode:  {cap_fixity}")
            print("=" * 60)

        self._mat_tag = 1
        self._ele_tag = 1

                                    
        D0 = self.piles[0]['D']
        self._calc_georgiadis_depths(D0)

        # --- OpenSees Init ---
        ops.wipe()
        ops.model('basic', '-ndm', 3, '-ndf', 6)

        cap_reference = np.asarray(cap_reference if cap_reference is not None else (0.0, 0.0, 0.0), dtype=float)
        load_location = np.asarray(load_location if load_location is not None else cap_reference, dtype=float)

        # --- Cap node ---
        CAP = 1
        ops.node(CAP, *cap_reference.tolist())
        if cap_fixity == '2D':
                                  
            ops.fix(CAP, 0, 1, 0, 1, 0, 1)
                         

        # --- Build each pile ---
        pile_node_map = []
        for k, p in enumerate(self.piles):
            info = self._build_pile(k, p, verbose)
            pile_node_map.append(info)
            self._connect_pile_to_cap(CAP, info)
        self._build_explicit_lateral_coupling(pile_node_map, verbose=verbose)

        # --- Load ---
        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)
        if np.linalg.norm(load_location - cap_reference) > 1.0e-12:
            LOAD = 2
            ops.node(LOAD, *load_location.tolist())
            ops.rigidLink('beam', CAP, LOAD)
            ops.load(LOAD, Fx, Fy, Fz, Mx, My, Mz)
        else:
            LOAD = CAP
            ops.load(CAP, Fx, Fy, Fz, Mx, My, Mz)

        # --- Analysis ---
        ops.system('UmfPack')
        ops.numberer('RCM')
        ops.constraints('Penalty', 1e15, 1e15)
        ops.test('NormDispIncr', 1e-5, 200, 0)
        ops.algorithm('KrylovNewton')
        ops.integrator('LoadControl', 1.0 / n_steps)
        ops.analysis('Static')

        success = True
        for step in range(n_steps):
            ok = ops.analyze(1)
            if ok != 0:
                for name, algo in [
                    ('Newton', lambda: ops.algorithm('Newton')),
                    ('Broyden', lambda: ops.algorithm('Broyden', 8)),
                    ('NewtonLineSearch', lambda: ops.algorithm('NewtonLineSearch')),
                    ('BFGS', lambda: ops.algorithm('BFGS')),
                    ('ModifiedNewton', lambda: ops.algorithm('ModifiedNewton', '-initial')),
                ]:
                    algo()
                    ok = ops.analyze(1)
                    if ok == 0:
                        ops.algorithm('KrylovNewton')
                        break
                if ok != 0:
                    if verbose:
                        print(f"  [WARN] Step {step} failed")
                    success = False
                    break

        if verbose:
            print("[OK] Analysis converged!" if success
                  else "[FAIL] Did not converge!")

        self._extract_results(pile_node_map, cap_reference=cap_reference, load_location=load_location, load_node=LOAD)
        return self.results

    # =================================================================
                             
    # =================================================================
    def _build_pile(self, k, p, verbose):
        base = (k + 1) * 10000
        head_pos = np.array([p['x'], p['y'], p.get('head_elevation', 0.0)])
        axis = p['axis']
        perp = p['perp']
        binorm = p['binorm']
        D = p['D']
        n_nodes = p['n_nodes']
        n_eles = p['n_eles']
        n_free = p['n_free']
        cos_beta = p['cos_beta']
        node_arc_lengths = p['node_arc_lengths']
        segment_lengths = p['segment_lengths']
        node_tributary_lengths = p['node_tributary_lengths']

        # --- Pile body nodes ---
        pile_nodes = []
        for i in range(n_nodes):
            nid = base + i
            pos = head_pos + node_arc_lengths[i] * axis
            ops.node(nid, *pos)
            ops.fix(nid, 0, 0, 0, 0, 0, 0) # Ensure nodes are free initially
            pile_nodes.append(nid)

        # --- Geometric transformation (3D beam) ---
        transf_tag = base
        ops.geomTransf('Linear', transf_tag, *perp.tolist())

        # --- Beam-column elements: elastic default or nonlinear fiber section ---
        beam_tags = []
        poisson = 0.25
        G_shear = p['E'] / (2.0 * (1.0 + poisson))
        J_torsion = p['I'] * 2  # circular section approximation
        shear_corr = 6.0 * (1.0 + poisson) / (7.0 + 6.0 * poisson)
        A_shear = max(shear_corr * p['A'], 1.0e-12)
        fiber_section_tags, fiber_segments = self._build_fiber_section_tags(p)
        for i in range(n_eles):
            etag = self._next_ele()
            arc_mid = 0.5 * (node_arc_lengths[i] + node_arc_lengths[i + 1])
            integration_tag = self._integration_tag_for_position(arc_mid, fiber_section_tags, fiber_segments)
            if integration_tag is not None:
                ops.element('forceBeamColumn', etag,
                            pile_nodes[i], pile_nodes[i + 1],
                            transf_tag, integration_tag)
            else:
                ops.element('ElasticTimoshenkoBeam', etag,
                            pile_nodes[i], pile_nodes[i + 1],
                            p['E'], G_shear, p['A'], J_torsion,
                            p['I'], p['I'], A_shear, A_shear,
                            transf_tag)
            beam_tags.append(etag)

                                            
        tz_tags = self._build_tz_springs(
            base, head_pos, axis, perp, D, node_arc_lengths, node_tributary_lengths,
            n_nodes, n_free, cos_beta, p['free_length'], pile_nodes)

                                              
        py_tags = self._build_py_springs(
            base, head_pos, axis, perp, binorm, D, node_arc_lengths, node_tributary_lengths,
            segment_lengths, n_nodes, n_free,
            cos_beta, p['free_length'], p['p_mult'], p.get('y_mult', 1.0),
            pile_nodes, row_role=p.get('group_row_role'))

                                         
        qz_tag = self._build_qz_spring(
            base, head_pos, axis, perp, D, node_arc_lengths,
            p['L'], pile_nodes, p.get('tip_area_m2'))

        if verbose:
            print(f"  Pile {k+1}: {n_nodes} nodes, {n_eles} beam eles, "
                  f"{len(tz_tags)} tz, {len(py_tags)} py, 1 qz")

        return {
            'head_node': pile_nodes[0],
            'tip_node': pile_nodes[-1],
            'pile_nodes': pile_nodes,
            'beam_tags': beam_tags,
            'tz_tags': tz_tags,
            'py_tags': py_tags,
            'qz_tag': qz_tag,
            'pile_info': p,
        }

    def _connect_pile_to_cap(self, cap_master_node, pile_info):
        """Connect each pile head to the cap control node.

        Strict static group-analysis interpretation:
        - the cap is represented by a control node at the cap reference point
        - each pile head is attached to that rigid cap kinematics through an
          attachment node at the pile-head plan location
        - connectivity only controls the relative pile-head rotational release
          with respect to the cap, matching the fixed / pinned / restrained
          concepts used in RSPile documentation
        """
        p = pile_info['pile_info']
        head_node = pile_info['head_node']
        head_pos = np.array([p['x'], p['y'], p.get('head_elevation', 0.0)])

        # Attachment node transfers the cap rigid-body motion from the cap
        # reference point to the actual pile-head location in plan.
        cap_attach_node = self._next_node()
        ops.node(cap_attach_node, *head_pos.tolist())
        ops.rigidLink('beam', cap_master_node, cap_attach_node)

        connectivity = p.get('head_connectivity', 'fixed')
        if connectivity == 'fixed':
            ops.rigidLink('beam', cap_attach_node, head_node)
            pile_info['cap_node'] = cap_attach_node
            return

        # Pinned/restrained heads always share translations with the cap.
        ops.equalDOF(cap_attach_node, head_node, 1, 2, 3)
        if connectivity == 'pinned':
            pile_info['cap_node'] = cap_attach_node
            return

        rot_k = p.get('rotational_stiffness')
        if rot_k is None:
            rot_vals = (1.0e8, 1.0e8, 1.0e8)
        elif np.isscalar(rot_k):
            rot_vals = (float(rot_k), float(rot_k), float(rot_k))
        else:
            if len(rot_k) != 3:
                raise ValueError("rotational_stiffness must be a scalar or length-3 iterable.")
            rot_vals = tuple(float(v) for v in rot_k)

        mat_tags = []
        for kval in rot_vals:
            mat = self._next_mat()
            ops.uniaxialMaterial('Elastic', mat, max(kval, 1.0e-6))
            mat_tags.append(mat)

        ele_tag = self._next_ele()
        ops.element('zeroLength', ele_tag, cap_attach_node, head_node,
                    '-mat', *mat_tags, '-dir', 4, 5, 6)
        pile_info['cap_node'] = cap_attach_node

    # -----------------------------------------------------------------
                            
    # -----------------------------------------------------------------
    def _build_tz_springs(self, base, head_pos, axis, perp, D, node_arc_lengths,
                          node_tributary_lengths, n_nodes, n_free, cos_beta, free_length,
                          pile_nodes):
        tz_tags = []
        for i in range(n_nodes):
            s = float(node_arc_lengths[i])
            dist_along = s - free_length
            z_vert = max(0.0, dist_along * cos_beta)

            # Soil node (fixed)
            soil_nid = base + 5000 + i
            pos_i = head_pos + s * axis
            ops.node(soil_nid, *pos_i)
            ops.fix(soil_nid, 1, 1, 1, 1, 1, 1)

            mat = self._next_mat()
            if dist_along < -0.001:
                # Above ground: negligible stiffness
                ops.uniaxialMaterial('Elastic', mat, 1e-6)
            else:
                trib_len = max(float(node_tributary_lengths[i]), 1.0e-9)
                tult, z50 = self._get_tz_params(z_vert, D, trib_len)
                ax_layer = self._get_ax_soil_at(z_vert)
                ax_type = ax_layer['type'] if ax_layer else 'unknown'

                                 
                tult_adj = tult

                if tult_adj < 1e-6 or z50 is None:
                    ops.uniaxialMaterial('Elastic', mat,
                                         tult_adj if z50 is None else 1e-3)
                elif self.spring_model_mode == 'native':
                    ops.uniaxialMaterial(
                        'TzSimple1',
                        mat,
                        self._native_axial_soil_type(ax_type),
                        float(tult_adj),
                        float(z50),
                    )
                else:
                    if ax_type in ('API Sand', 'Drilled Sand', 'Sand'):
                        curve_type = 'api_sand'
                    elif ax_type in ('API Clay', 'Drilled Clay', 'Clay'):
                        curve_type = 'api_clay'
                    else:
                        curve_type = 'hyperbolic'
                    zp = np.array([
                        0.0,
                        max(0.25 * z50, 1.0e-6),
                        max(0.5 * z50, 2.0e-6),
                        max(1.0 * z50, 4.0e-6),
                        max(2.0 * z50, 8.0e-6),
                        max(5.0 * z50, 2.0e-5),
                        max(10.0 * z50, 4.0e-5),
                        max(20.0 * z50, 8.0e-5),
                    ], dtype=float)
                    zp, tp = generate_tz_curve(
                        tult_adj,
                        z50,
                        model_type=curve_type,
                        z_range=zp,
                    )

                    self._create_multilinear_sym(mat, zp, tp)

            # zeroLength: oriented along pile axis
            etag = self._next_ele()
            ops.element('zeroLength', etag, soil_nid, pile_nodes[i],
                        '-mat', mat, '-dir', 1,
                        '-orient', *axis.tolist(), *perp.tolist())
            tz_tags.append(etag)

        return tz_tags

    # -----------------------------------------------------------------
                         
    # -----------------------------------------------------------------
    def _build_py_springs(self, base, head_pos, axis, perp, binorm, D, node_arc_lengths,
                          node_tributary_lengths, segment_lengths, n_nodes, n_free, cos_beta, free_length,
                          p_mult, y_mult, pile_nodes, row_role=None):
        py_tags = []
        n_py_pts = 25
        y_max = 0.5

        for i in range(n_nodes):
            s = float(node_arc_lengths[i])
            dist_along = s - free_length
            if dist_along < 0:
                continue            
            z_vert = dist_along * cos_beta

            # Soil node
            soil_nid = base + 6000 + i
            pos_i = head_pos + s * axis
            ops.node(soil_nid, *pos_i)
            ops.fix(soil_nid, 1, 1, 1, 1, 1, 1)

                  
            L_trib = max(float(node_tributary_lengths[i]), 1.0e-9)

            (pult, y50), layer, z_eff = self._get_py_at_depth(z_vert, D)
            soil_type = layer['type'] if layer else 'unknown'
            mat = self._next_mat()

            if pult < 1e-6 or y50 is None:
                # Elastic spring or negligible
                k_spring = pult * L_trib if y50 is None else 1e-3
                ops.uniaxialMaterial('Elastic', mat, k_spring)
            elif self.spring_model_mode == 'native':
                native_soil_type = self._native_py_soil_type(soil_type)
                if native_soil_type is None:
                    y_small = np.array([0, 1e-4, 5e-4, 1e-3, 3e-3, 5e-3])
                    y_linear = np.linspace(y_max / n_py_pts, y_max, n_py_pts)[1:]
                    y_vals = np.unique(np.concatenate([y_small, y_linear]))
                    _, p_curve = generate_py_curve(
                        pult, y50, 'Soft Clay Soil', y_vals)
                    p_mult_i = self._resolve_p_multiplier(p_mult, z_vert, layer)
                    force_pos = p_curve * L_trib * p_mult_i
                    force_pos[0] = 0.0
                    y_neg = -y_vals[::-1][:-1]
                    f_neg = -force_pos[::-1][:-1]
                    y_all = np.concatenate([y_neg, y_vals])
                    f_all = np.concatenate([f_neg, force_pos])
                    ops.uniaxialMaterial('ElasticMultiLinear', mat,
                                         '-strain', *y_all.tolist(),
                                         '-stress', *f_all.tolist())
                else:
                    p_mult_i = self._resolve_p_multiplier(p_mult, z_vert, layer)
                    ops.uniaxialMaterial(
                        'PySimple1',
                        mat,
                        native_soil_type,
                        float(pult * L_trib * p_mult_i),
                        float(y50),
                        0.3,
                    )
            else:
                # Build p-y multilinear curve directly from the selected single-pile model.
                y_small = np.array([0, 1e-4, 5e-4, 1e-3, 3e-3, 5e-3])
                y_linear = np.linspace(y_max / n_py_pts, y_max, n_py_pts)[1:]
                y_vals = np.unique(np.concatenate([y_small, y_linear]))

                z_eff = max(z_eff, 0.01)
                y_curve_vals = y_vals

                if soil_type == 'API Method for Sand':
                    # API sand uses the tanh formulation.
                    lp = layer['params']
                    _, p_curve = generate_py_curve(
                        pult, y50, 'API Method for Sand', y_curve_vals,
                        k_modulus=lp.get('k_modulus', lp.get('kpy', 0.0)),
                        z=z_eff)
                elif soil_type == 'Sand':
                    lp = layer['params']
                    p_curve = generate_reese_sand_py_points(
                        y_curve_vals, z_eff, lp.get('gammaEff', 0.0),
                        lp.get('phiDegree', lp.get('phi', 30)), D,
                        lp.get('kpy', lp.get('k_modulus', 0.0)),
                        lp.get('is_cyclic', False))
                elif soil_type in ('Soft Clay Soil', 'Clay'):
                    _, p_curve = generate_py_curve(
                        pult, y50, 'Soft Clay Soil', y_curve_vals)
                elif soil_type == 'Submerged Stiff Clay':
                    k_mod = layer['params'].get('k_modulus', 0.0)
                    A_coeff = stiff_clay_with_water_A(
                        z_eff / D,
                        layer['params'].get('is_cyclic', False),
                    )
                    _, p_curve = generate_py_curve(
                        pult, y50, 'Submerged Stiff Clay', y_curve_vals,
                        k_modulus=k_mod, z=z_eff, A=A_coeff)
                elif soil_type in ('Dry Stiff Clay', 'Modified Stiff Clay without Free Water', 'Stiff Clay'):
                    k_mod = layer['params'].get('k_modulus', 0.0)
                    _, p_curve = generate_py_curve(
                        pult, y50, 'Modified Stiff Clay without Free Water', y_curve_vals,
                        k_modulus=k_mod, z=z_eff)
                elif soil_type == 'Weak Rock':
                    # Reese & Nyman (1978)
                    Eir_val = layer['params'].get('Eir', 100000.0)
                    xr = z_eff / D
                    kir = min(100.0 + 400.0 * (xr / 3.0), 500.0)
                    Kir_val = kir * Eir_val
                    _, p_curve = generate_py_curve(
                        pult, y50, 'Weak Rock', y_curve_vals,
                        k_modulus=Kir_val, z=z_eff)
                else:
                    _, p_curve = generate_py_curve(
                        pult, y50, 'Soft Clay Soil', y_curve_vals)

                # Convert distributed resistance to tributary nodal force and
                # apply only the theoretical group-effect reduction fm.
                p_mult_i = self._resolve_p_multiplier(p_mult, z_vert, layer)
                force_pos = p_curve * L_trib * p_mult_i
                force_pos[0] = 0.0

                      
                y_neg = -y_vals[::-1][:-1]
                f_neg = -force_pos[::-1][:-1]
                y_all = np.concatenate([y_neg, y_vals])
                f_all = np.concatenate([f_neg, force_pos])

                ops.uniaxialMaterial('ElasticMultiLinear', mat,
                                     '-strain', *y_all.tolist(),
                                     '-stress', *f_all.tolist())

            # zeroLength: lateral springs
            # In 3D mode, the pile can move both in 'perp' and 'binorm' directions.
            # We assume isotropic soil resistance (same p-y in both lateral directions).
            
            # Spring Material (mat) represents the soil response
            etag_perp = self._next_ele()
            ops.element('zeroLength', etag_perp, soil_nid, pile_nodes[i],
                        '-mat', mat, '-dir', 1,
                        '-orient', *perp.tolist(), *axis.tolist())
            py_tags.append(etag_perp)
            
            # Second lateral spring (Binormal direction) for full 3D response
            etag_binorm = self._next_ele()
            ops.element('zeroLength', etag_binorm, soil_nid, pile_nodes[i],
                        '-mat', mat, '-dir', 1,
                        '-orient', *binorm.tolist(), *axis.tolist())
            py_tags.append(etag_binorm)

        return py_tags

    # -----------------------------------------------------------------
    # Q-z spring: API Table 6.7.3-1
    # -----------------------------------------------------------------
    def _build_qz_spring(self, base, head_pos, axis, perp, D, node_arc_lengths,
                         L, pile_nodes, tip_area_m2=None):
        tip_node = pile_nodes[-1]
        qz_soil_nid = base + 9000
        tip_pos = head_pos + float(node_arc_lengths[-1]) * axis
        ops.node(qz_soil_nid, *tip_pos)
        ops.fix(qz_soil_nid, 1, 1, 1, 1, 1, 1)

        qult, q50 = self._get_qz_params(D, L, tip_area_m2)
        mat = self._next_mat()
        if qult < 1e-6 or q50 is None:
            ops.uniaxialMaterial('Elastic', mat, qult if q50 is None else 1e-3)
        elif self.spring_model_mode == 'native':
            tip_type = str(self.tip_soil.get('type', 'API Sand')) if isinstance(self.tip_soil, dict) else 'API Sand'
            ops.uniaxialMaterial(
                'QzSimple1',
                mat,
                self._native_axial_soil_type(tip_type),
                float(qult),
                float(q50),
            )
        else:
            zp = np.array([
                0.0,
                max(0.25 * q50, 1.0e-6),
                max(0.5 * q50, 2.0e-6),
                max(1.0 * q50, 4.0e-6),
                max(2.0 * q50, 8.0e-6),
                max(5.0 * q50, 2.0e-5),
                max(10.0 * q50, 4.0e-5),
                max(20.0 * q50, 8.0e-5),
            ], dtype=float)
            zp, qp = generate_qz_curve(qult, q50, model_type='api', z_range=zp)
            self._create_multilinear_sym(mat, zp, qp)

        etag = self._next_ele()
        ops.element('zeroLength', etag, qz_soil_nid, tip_node,
                    '-mat', mat, '-dir', 1,
                    '-orient', *axis.tolist(), *perp.tolist())
        return etag

    # =================================================================
          
    # =================================================================
    def _extract_results(self, pile_node_map, cap_reference=None, load_location=None, load_node=None):
        CAP = 1
        cap_disp = [ops.nodeDisp(CAP, dof) for dof in range(1, 7)]
        load_disp = [ops.nodeDisp(load_node, dof) for dof in range(1, 7)] if load_node is not None else list(cap_disp)

        pile_results = []
        for k, info in enumerate(pile_node_map):
            p = info['pile_info']
            nodes = info['pile_nodes']
            beams = info['beam_tags']
            axis = p['axis']
            perp = p['perp']
            op_x = p['local_x']
            op_y = p['local_y']
            op_z = p['local_z']
            rsp_x = p['rspile_x']
            rsp_y = p['rspile_y']
            rsp_z = p['rspile_z']
            node_arc_lengths = np.asarray(p['node_arc_lengths'], dtype=float)

            # Head forces (from first beam element, i-node)
            f = ops.eleForce(beams[0])
            force_vec = np.array([f[0], f[1], f[2]])
            F_axial = np.dot(force_vec, axis)
            F_lateral = np.dot(force_vec, perp)

            # Displacements along pile
            n_nodes_pile = len(nodes)
            depths = np.zeros(n_nodes_pile)
            depths_from_head = np.zeros(n_nodes_pile)
            disps_axial = np.zeros(n_nodes_pile)
            disps_lateral = np.zeros(n_nodes_pile)
            disps_dx = np.zeros(n_nodes_pile)  # global X displacement
            disps_dy = np.zeros(n_nodes_pile)  # global Y displacement
            disps_dz = np.zeros(n_nodes_pile)  # global Z displacement (vertical)
            for i, nid in enumerate(nodes):
                d = [ops.nodeDisp(nid, dof) for dof in range(1, 4)]
                d_vec = np.array(d)
                s = float(node_arc_lengths[i])
                depths[i] = s - p['free_length']
                depths_from_head[i] = s
                disps_axial[i] = np.dot(d_vec, axis)
                disps_lateral[i] = np.dot(d_vec, perp)
                disps_dx[i] = d[0]
                disps_dy[i] = d[1]
                disps_dz[i] = d[2]

            # Element forces along pile (local coordinates)
            axial_forces = np.zeros(len(beams))
            shear_forces = np.zeros(len(beams))
            moments = np.zeros(len(beams))
            local_shear_y = np.zeros(len(beams))
            local_shear_z = np.zeros(len(beams))
            local_moment_y = np.zeros(len(beams))
            local_moment_z = np.zeros(len(beams))
            rspile_shear_x = np.zeros(len(beams))
            rspile_shear_y = np.zeros(len(beams))
            rspile_moment_x = np.zeros(len(beams))
            rspile_moment_y = np.zeros(len(beams))
            depths_ele = np.zeros(len(beams))
            depths_ele_from_head = np.zeros(len(beams))
            section_depths = np.zeros(len(nodes))
            section_depths_from_head = np.zeros(len(nodes))
            section_rspile_shear_x = np.zeros(len(nodes))
            section_rspile_shear_y = np.zeros(len(nodes))
            section_rspile_moment_x = np.zeros(len(nodes))
            section_rspile_moment_y = np.zeros(len(nodes))
            for j, etag in enumerate(beams):
                ef = ops.eleForce(etag)
                lf = ops.eleResponse(etag, 'localForce')
                if lf is None or len(lf) < 6:
                    lf = ef
                lf = np.asarray(lf, dtype=float)
                if lf.size >= 12:
                    lf_i = lf[:6]
                    lf_j = lf[6:12]
                else:
                    lf_i = np.asarray(ef[:6], dtype=float)
                    lf_j = np.asarray(ef[:6], dtype=float)

                fvec = np.array([ef[0], ef[1], ef[2]])
                mvec = np.array([ef[3], ef[4], ef[5]])
                global_force = lf_i[0] * op_x + lf_i[1] * op_y + lf_i[2] * op_z
                global_moment = lf_i[3] * op_x + lf_i[4] * op_y + lf_i[5] * op_z
                axial_forces[j] = np.dot(fvec, axis)
                shear_forces[j] = np.dot(fvec, perp)
                moments[j] = np.dot(mvec, p['binorm'])
                local_shear_y[j] = lf_i[1]
                local_shear_z[j] = lf_i[2]
                local_moment_y[j] = lf_i[4]
                local_moment_z[j] = lf_i[5]
                rspile_shear_x[j] = np.dot(global_force, rsp_x)
                rspile_shear_y[j] = np.dot(global_force, rsp_y)
                rspile_moment_x[j] = np.dot(global_moment, rsp_x)
                rspile_moment_y[j] = np.dot(global_moment, rsp_y)
                s_mid = 0.5 * (node_arc_lengths[j] + node_arc_lengths[j + 1])
                depths_ele[j] = s_mid - p['free_length']
                depths_ele_from_head[j] = s_mid

                global_force_i = lf_i[0] * op_x + lf_i[1] * op_y + lf_i[2] * op_z
                global_moment_i = lf_i[3] * op_x + lf_i[4] * op_y + lf_i[5] * op_z
                global_force_j = lf_j[0] * op_x + lf_j[1] * op_y + lf_j[2] * op_z
                global_moment_j = lf_j[3] * op_x + lf_j[4] * op_y + lf_j[5] * op_z

                section_depths[j] = float(node_arc_lengths[j]) - p['free_length']
                section_depths_from_head[j] = float(node_arc_lengths[j])
                section_rspile_shear_x[j] = np.dot(global_force_i, rsp_x)
                section_rspile_shear_y[j] = np.dot(global_force_i, rsp_y)
                section_rspile_moment_x[j] = np.dot(global_moment_i, rsp_x)
                section_rspile_moment_y[j] = np.dot(global_moment_i, rsp_y)

                if j == len(beams) - 1:
                    section_depths[j + 1] = float(node_arc_lengths[j + 1]) - p['free_length']
                    section_depths_from_head[j + 1] = float(node_arc_lengths[j + 1])
                    section_rspile_shear_x[j + 1] = -np.dot(global_force_j, rsp_x)
                    section_rspile_shear_y[j + 1] = -np.dot(global_force_j, rsp_y)
                    section_rspile_moment_x[j + 1] = -np.dot(global_moment_j, rsp_x)
                    section_rspile_moment_y[j + 1] = -np.dot(global_moment_j, rsp_y)

            head_disp = np.array([ops.nodeDisp(nodes[0], d)
                                  for d in range(1, 4)])

            # Global force components at pile head
            Fx_global = np.dot(force_vec, np.array([1, 0, 0]))
            Fy_global = np.dot(force_vec, np.array([0, 1, 0]))
            Fz_global = np.dot(force_vec, np.array([0, 0, 1]))

            pile_results.append({
                'id': k + 1,
                'head_elevation': float(p.get('head_elevation', 0.0)),
                'F_axial_head': F_axial,
                'F_lateral_head': F_lateral,
                'Fx_global': Fx_global,
                'Fy_global': Fy_global,
                'Fz_global': Fz_global,
                'head_disp_global': head_disp,
                'local_x_axis': p['local_x'],
                'local_y_axis': p['local_y'],
                'local_z_axis': p['local_z'],
                'rspile_x_axis': rsp_x,
                'rspile_y_axis': rsp_y,
                'rspile_z_axis': rsp_z,
                'depths': depths,
                'depths_from_head': depths_from_head,
                'disps_axial': disps_axial * 1000,     # mm (along pile axis)
                'disps_lateral': disps_lateral * 1000,  # mm (perp to pile axis)
                'disps_dx': disps_dx * 1000,            # mm (global X)
                'disps_dy': disps_dy * 1000,            # mm (global Y)
                'disps_dz': disps_dz * 1000,            # mm (global Z / vertical)
                'axial_forces': axial_forces,
                'shear_forces': shear_forces,
                'moments': moments,
                'local_shear_y': local_shear_y,
                'local_shear_z': local_shear_z,
                'local_moment_y': local_moment_y,
                'local_moment_z': local_moment_z,
                'rspile_shear_x': rspile_shear_x,
                'rspile_shear_y': rspile_shear_y,
                'rspile_moment_x': rspile_moment_x,
                'rspile_moment_y': rspile_moment_y,
                'section_rspile_shear_x': section_rspile_shear_x,
                'section_rspile_shear_y': section_rspile_shear_y,
                'section_rspile_moment_x': section_rspile_moment_x,
                'section_rspile_moment_y': section_rspile_moment_y,
                'depths_ele': depths_ele,
                'depths_ele_from_head': depths_ele_from_head,
                'section_depths': section_depths,
                'section_depths_from_head': section_depths_from_head,
            })

        self.results = {
            'cap_disp': cap_disp,  # [dx,dy,dz,rx,ry,rz]
            'cap_disp_x_mm': cap_disp[0] * 1000.0,
            'cap_disp_y_mm': cap_disp[1] * 1000.0,
            'cap_disp_z_mm': cap_disp[2] * 1000.0,
            'load_disp': load_disp,
            'load_disp_x_mm': load_disp[0] * 1000.0,
            'load_disp_y_mm': load_disp[1] * 1000.0,
            'load_disp_z_mm': load_disp[2] * 1000.0,
            'cap_reference': np.asarray(cap_reference if cap_reference is not None else (0.0, 0.0, 0.0), dtype=float),
            'load_location': np.asarray(load_location if load_location is not None else (0.0, 0.0, 0.0), dtype=float),
            'piles': pile_results,
        }
        return self.results


# =====================================================================
# Standalone test
# =====================================================================
if __name__ == '__main__':
    print("MonolithicGroupPileSolver (RSPile-Compliant) - import test OK")
