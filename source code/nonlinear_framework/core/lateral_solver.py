# -*-coding: UTF-8-*-
import math

import numpy as np
import openseespy.opensees as ops
from functools import lru_cache
try:
    from .py_model import (py_api_method_for_sand, py_sand, py_soft_clay_soil,
                           py_submerged_stiff_clay,
                           py_dry_stiff_clay,
                           py_weak_rock, py_elastic, generate_py_curve,
                           stiff_clay_with_water_A,
                           generate_reese_sand_py_points)
except Exception:
    from py_model import (py_api_method_for_sand, py_sand, py_soft_clay_soil,
                          py_submerged_stiff_clay,
                          py_dry_stiff_clay,
                          py_weak_rock, py_elastic, generate_py_curve,
                          stiff_clay_with_water_A,
                          generate_reese_sand_py_points)


class LateralPileSolver:

    def __init__(self, pile_length, pile_diameter, E_pile,
                 I_pile=None, A_pile=None, ele_size=None,
                 free_length=0.0, p_multiplier=1.0,
                 mesh_positions=None,
                 spring_model_mode='multilinear',
                 use_timoshenko=False, poisson_ratio=0.3,
                 shear_area_factor=0.9,
                 section_mode='elastic',
                 fiber_section_library=None,
                 fiber_section_segments=None):
        self.L = pile_length
        self.D = pile_diameter
        self.E = E_pile
        self.free_length = free_length
        self.use_timoshenko = use_timoshenko
        self.poisson_ratio = poisson_ratio
        self.shear_area_factor = shear_area_factor
        self.p_multiplier = p_multiplier                                
        self.section_mode = str(section_mode or 'elastic')
        self.spring_model_mode = str(spring_model_mode or 'multilinear').lower()
        self.fiber_section_library = list(fiber_section_library or [])
        self.fiber_section_segments = list(fiber_section_segments or [])

        total_length = free_length + pile_length
        if mesh_positions is not None and len(mesh_positions) >= 2:
            self.node_arc_lengths = np.array([float(v) for v in mesh_positions], dtype=float)
            self.node_arc_lengths[0] = 0.0
            self.node_arc_lengths[-1] = total_length
        else:
            if ele_size is None:
                self.ele_size = total_length / 400.0
            else:
                self.ele_size = ele_size
            self.node_arc_lengths = np.linspace(0.0, total_length, max(int(round(total_length / self.ele_size)), 1) + 1)

        if I_pile is None:
            self.I = np.pi * (pile_diameter ** 4) / 64
        else:
            self.I = I_pile

        if A_pile is None:
            self.A = np.pi * (pile_diameter ** 2) / 4
        else:
            self.A = A_pile

                
        self.total_length = total_length
        self.segment_lengths = np.diff(self.node_arc_lengths)
        self.n_eles = len(self.segment_lengths)
        self.n_nodes = self.n_eles + 1
        self.n_free_nodes = int(np.searchsorted(self.node_arc_lengths, free_length, side='left'))
        self.ele_size = float(np.mean(self.segment_lengths)) if self.n_eles else self.total_length
        self.node_tributary_lengths = np.zeros(self.n_nodes)
        for i in range(self.n_nodes):
            left = 0.5 * self.segment_lengths[i - 1] if i > 0 else 0.0
            right = 0.5 * self.segment_lengths[i] if i < self.n_eles else 0.0
            self.node_tributary_lengths[i] = left + right

                
        self.soil_layers = []  # [(z_top, z_bot, soil_type, params), ...]

                
        self.results = {}
        self._mat_tag_seed = 100000
        self._section_tag_seed = 200000

    def _next_mat_tag(self):
        tag = self._mat_tag_seed
        self._mat_tag_seed += 1
        return tag

    def _next_section_tag(self):
        tag = self._section_tag_seed
        self._section_tag_seed += 1
        return tag

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    def _fiber_modulus(self, kind, params):
        params = dict(params or {})
        if kind == 'steel':
            return self._safe_float(params.get('Es--Initial elastic tangent(kPa)'), self.E)
        return self._safe_float(params.get('initialStiffness-Ec(kPa)'), self.E)

    def _concrete_tension_parameters(self, fc, Ec):
        fc_mpa = abs(float(fc)) / 1000.0
        if fc_mpa <= 1.0e-12 or Ec <= 1.0e-12:
            return 0.0, 0.0
        # Preserve an uncracked initial bending response by supplying a modest
        # tensile branch to Concrete04 instead of zero-tension concrete.
        fct = 0.33 * math.sqrt(fc_mpa) * 1000.0
        et = max(10.0 * fct / Ec, 1.0e-5)
        return fct, et

    def _section_initial_rigidity(self, section_def):
        mats = dict(section_def.get('material_params', {}) or {})
        fibers = dict(section_def.get('fibers', {}) or {})
        rows = []
        for row in fibers.get('core', []) or []:
            rows.append((self._safe_float(row.get('y_m', 0.0)), self._safe_float(row.get('z_m', 0.0)), self._safe_float(row.get('area_m2', 0.0)), self._fiber_modulus('concrete', mats.get('core_concrete', {}))))
        for role in ('inner_cover', 'outer_cover'):
            for row in fibers.get(role, []) or []:
                rows.append((self._safe_float(row.get('y_m', 0.0)), self._safe_float(row.get('z_m', 0.0)), self._safe_float(row.get('area_m2', 0.0)), self._fiber_modulus('concrete', mats.get('cover_concrete', {}))))
        for group in fibers.get('rebar_groups', []) or []:
            for row in group.get('fibers', []) or []:
                rows.append((self._safe_float(row.get('y_m', 0.0)), self._safe_float(row.get('z_m', 0.0)), self._safe_float(row.get('area_m2', 0.0)), self._fiber_modulus('steel', mats.get('rebar', {}))))
        if not rows:
            return 0.0, 0.0, 0.0
        ea = sum(Ei * Ai for _, _, Ai, Ei in rows)
        cy = sum(Ei * Ai * yi for yi, _, Ai, Ei in rows) / max(ea, 1.0e-12)
        cz = sum(Ei * Ai * zi for _, zi, Ai, Ei in rows) / max(ea, 1.0e-12)
        eiy = sum(Ei * Ai * (zi - cz) ** 2 for _, zi, Ai, Ei in rows)
        eiz = sum(Ei * Ai * (yi - cy) ** 2 for yi, _, Ai, Ei in rows)
        return ea, eiy, eiz

    def _create_fiber_uniaxial_material(self, kind, params):
        mat_tag = self._next_mat_tag()
        params = dict(params or {})
        if kind == 'steel':
            fy = abs(self._safe_float(params.get('fy --Yield stress in tension(kPa)'), 0.0))
            fu = abs(self._safe_float(params.get('fu --Ultimate stress in tension(kPa)'), fy))
            Es = self._safe_float(params.get('Es--Initial elastic tangent(kPa)'), self.E)
            Esh = self._safe_float(params.get('Esh--Tangent at initial strain hardening(kPa)'), 0.0)
            esh = abs(self._safe_float(params.get('esh--Strain corresponding to initial strain hardening'), 0.015))
            eult = abs(self._safe_float(params.get('eult--Strain at peak stress'), max(esh, 0.1)))
            if fy > 1.0e-6 and fu >= fy and Es > 1.0e-6:
                ops.uniaxialMaterial('ReinforcingSteel', mat_tag, fy, fu, Es, max(Esh, 1.0e-6), esh, max(eult, esh + 1.0e-6))
            else:
                ops.uniaxialMaterial('Elastic', mat_tag, max(Es, 1.0))
            return mat_tag

        fc = self._safe_float(params.get('concreteCompressiveStrengthAt28Days-fc(kPa)'), 0.0)
        epsc0 = self._safe_float(params.get('concreteStrainAtMaximumStrength-ec'), -0.002)
        epsu = self._safe_float(params.get('concreteStrainAtCrushingStrength-ecu'), -0.004)
        Ec = self._safe_float(params.get('initialStiffness-Ec(kPa)'), self.E)
        if fc < -1.0e-6 and epsc0 < -1.0e-8 and epsu < epsc0:
            fct, et = self._concrete_tension_parameters(fc, Ec)
            ops.uniaxialMaterial('Concrete04', mat_tag, fc, epsc0, epsu, max(Ec, 1.0), fct, et)
        else:
            ops.uniaxialMaterial('Elastic', mat_tag, max(Ec, 1.0))
        return mat_tag

    def _resolve_fiber_sections(self):
        if self.section_mode != 'fiber':
            return {}, []
        library = {
            str(item.get('name', '')): dict(item)
            for item in self.fiber_section_library
            if isinstance(item, dict) and str(item.get('name', '')).strip()
        }
        segments = []
        for item in self.fiber_section_segments:
            if not isinstance(item, dict):
                continue
            name = str(item.get('section_name', '')).strip()
            if not name or name not in library:
                continue
            top = min(self._safe_float(item.get('top_m', 0.0)), self._safe_float(item.get('bottom_m', 0.0)))
            bottom = max(self._safe_float(item.get('top_m', 0.0)), self._safe_float(item.get('bottom_m', 0.0)))
            segments.append({'top_m': top, 'bottom_m': bottom, 'section_name': name})
        if not segments and len(library) == 1:
            only_name = next(iter(library))
            segments = [{'top_m': 0.0, 'bottom_m': self.total_length, 'section_name': only_name}]
        return library, segments

    def _build_fiber_section_tags(self):
        library, segments = self._resolve_fiber_sections()
        if not library or not segments:
            return {}, []
        section_tags = {}
        for name, section_def in library.items():
            if not hasattr(self, '_debug_fiber_initial_EA_kN'):
                ea, eiy, eiz = self._section_initial_rigidity(section_def)
                self._debug_fiber_initial_EA_kN = ea
                self._debug_fiber_initial_EIy_kN_m2 = eiy
                self._debug_fiber_initial_EIz_kN_m2 = eiz
            mats = dict(section_def.get('material_params', {}) or {})
            core_mat = self._create_fiber_uniaxial_material('concrete', mats.get('core_concrete', {}))
            cover_mat = self._create_fiber_uniaxial_material('concrete', mats.get('cover_concrete', {}))
            rebar_mat = self._create_fiber_uniaxial_material('steel', mats.get('rebar', {}))
            sec_tag = self._next_section_tag()
            ops.section('Fiber', sec_tag)
            fibers = dict(section_def.get('fibers', {}) or {})
            for row in fibers.get('core', []) or []:
                ops.fiber(self._safe_float(row.get('y_m', 0.0)), self._safe_float(row.get('z_m', 0.0)), max(self._safe_float(row.get('area_m2', 0.0)), 1.0e-12), core_mat)
            for role in ('inner_cover', 'outer_cover'):
                for row in fibers.get(role, []) or []:
                    ops.fiber(self._safe_float(row.get('y_m', 0.0)), self._safe_float(row.get('z_m', 0.0)), max(self._safe_float(row.get('area_m2', 0.0)), 1.0e-12), cover_mat)
            for group in fibers.get('rebar_groups', []) or []:
                for row in group.get('fibers', []) or []:
                    ops.fiber(self._safe_float(row.get('y_m', 0.0)), self._safe_float(row.get('z_m', 0.0)), max(self._safe_float(row.get('area_m2', 0.0)), 1.0e-12), rebar_mat)
            bi_tag = self._next_section_tag()
            ops.beamIntegration('Lobatto', bi_tag, sec_tag, 5)
            section_tags[name] = bi_tag
        return section_tags, segments

    def _build_elastic_section_integration(self):
        sec_tag = self._next_section_tag()
        ops.section('Elastic', sec_tag, self.E, self.A, self.I)
        bi_tag = self._next_section_tag()
        ops.beamIntegration('Lobatto', bi_tag, sec_tag, 5)
        return bi_tag

    @staticmethod
    def _integration_tag_for_position(arc_mid, section_tags, segments):
        if not section_tags or not segments:
            return None
        for segment in segments:
            if segment['top_m'] - 1.0e-9 <= arc_mid <= segment['bottom_m'] + 1.0e-9:
                return section_tags.get(segment['section_name'])
        return section_tags.get(segments[-1]['section_name'])

    @staticmethod
    def _resolve_2d_equivalent_loads(Fx=0.0, Fy=0.0, Fz=0.0, Mx=0.0, My=0.0, Mz=0.0,
                                     z_Fx=0.0, z_Fy=0.0, z_Fz=0.0, z_Mx=0.0, z_My=0.0, z_Mz=0.0):
        horiz = np.array([float(Fx), float(Fy)], dtype=float)
        h_mag = float(np.linalg.norm(horiz))
        moment_vec = np.array([float(Mx), float(My)], dtype=float)
        m_h_mag = float(np.linalg.norm(moment_vec))

        if h_mag > 1.0e-12:
            e = horiz / h_mag
        elif m_h_mag > 1.0e-12:
            e = np.array([moment_vec[1], -moment_vec[0]], dtype=float) / m_h_mag
        else:
            e = np.array([1.0, 0.0], dtype=float)

        bend_axis = np.array([-e[1], e[0]], dtype=float)
        force_induced_moment = np.array([float(Fy) * float(z_Fy), -float(Fx) * float(z_Fx)], dtype=float)
        direct_moment = np.array([float(Mx), float(My)], dtype=float)
        effective_moment = float(np.dot(direct_moment + force_induced_moment, bend_axis))

        return {
            "analysis_dir_x": float(e[0]),
            "analysis_dir_y": float(e[1]),
            "analysis_angle_deg": float(np.degrees(np.arctan2(e[1], e[0]))),
            "effective_lateral_load_kN": h_mag,
            "effective_moment_kN_m": effective_moment,
            "force_induced_moment_x_kN_m": float(force_induced_moment[0]),
            "force_induced_moment_y_kN_m": float(force_induced_moment[1]),
            "ignored_axial_force_kN": float(Fz),
            "ignored_torsion_kN_m": float(Mz),
            "original_loads": {
                "Fx": {"value": float(Fx), "z_m": float(z_Fx)},
                "Fy": {"value": float(Fy), "z_m": float(z_Fy)},
                "Fz": {"value": float(Fz), "z_m": float(z_Fz)},
                "Mx": {"value": float(Mx), "z_m": float(z_Mx)},
                "My": {"value": float(My), "z_m": float(z_My)},
                "Mz": {"value": float(Mz), "z_m": float(z_Mz)},
            },
        }

    def analyze_6dof(self, Fx=0.0, Fy=0.0, Fz=0.0, Mx=0.0, My=0.0, Mz=0.0,
                     z_Fx=0.0, z_Fy=0.0, z_Fz=0.0, z_Mx=0.0, z_My=0.0, z_Mz=0.0,
                     lateral_disp=None, top_bc='free', bottom_bc='free',
                     n_steps=20, verbose=True):
        eq = self._resolve_2d_equivalent_loads(
            Fx=Fx, Fy=Fy, Fz=Fz, Mx=Mx, My=My, Mz=Mz,
            z_Fx=z_Fx, z_Fy=z_Fy, z_Fz=z_Fz, z_Mx=z_Mx, z_My=z_My, z_Mz=z_Mz,
        )
        results = self.analyze(
            lateral_load=eq["effective_lateral_load_kN"],
            lateral_disp=lateral_disp,
            moment_load=eq["effective_moment_kN_m"],
            top_bc=top_bc,
            bottom_bc=bottom_bc,
            n_steps=n_steps,
            verbose=verbose,
        )
        results.update(eq)
        disp = float(results.get("pile_top_disp", 0.0))
        results["pile_top_disp_x_mm"] = disp * eq["analysis_dir_x"]
        results["pile_top_disp_y_mm"] = disp * eq["analysis_dir_y"]
        return results

    # -----------------------------------------------------------------
            
    # -----------------------------------------------------------------
    def add_soil_layer(self, z_top, z_bottom, soil_type, **params):
        self.soil_layers.append({
            'z_top': z_top,
            'z_bottom': z_bottom,
            'type': soil_type,
            'params': params
        })

    def _eval_pult_for_layer(self, layer, z_eff):
        p = layer['params']
        st = layer['type']
        gammaEff = p.get('gammaEff', 0.0)

        if z_eff <= 0.0:
            if st == 'Elastic':
                return 0.0, None
            return 0.0, 1.0e-6

        if st == 'API Method for Sand':
            return py_api_method_for_sand(z_eff, gammaEff, p.get('phiDegree', 30),
                               self.D, p.get('k_modulus', 0.0),
                               p.get('is_cyclic', False))
        elif st == 'Sand':
            return py_sand(z_eff, gammaEff, p.get('phiDegree', 30),
                                 self.D, p.get('kpy', 0.0),
                                 p.get('is_cyclic', False))
        elif st == 'Soft Clay Soil':
            return py_soft_clay_soil(z_eff, gammaEff, p.get('cu', 50),
                                        self.D, p.get('eps50', 0.01),
                                        p.get('J', 0.5),
                                        p.get('is_cyclic', False))
        elif st == 'Submerged Stiff Clay':
            return py_submerged_stiff_clay(z_eff, gammaEff, p.get('cu', 100),
                                       p.get('ca', p.get('cu', 100)),
                                       self.D, p.get('eps50', 0.005))
        elif st == 'Dry Stiff Clay':
            return py_dry_stiff_clay(z_eff, gammaEff, p.get('cu', 100),
                                              p.get('ca', p.get('cu', 100)),
                                              self.D, p.get('eps50', 0.005),
                                              p.get('J', 0.5))
        elif st == 'Modified Stiff Clay without Free Water':
            return py_dry_stiff_clay(z_eff, gammaEff, p.get('cu', 100),
                                              p.get('ca', p.get('cu', 100)),
                                              self.D, p.get('eps50', 0.005),
                                              p.get('J', 0.5))
        elif st == 'Weak Rock':
            return py_weak_rock(z_eff, gammaEff, p.get('qu', 1000),
                                self.D, p.get('krm', 0.0005),
                                p.get('Eir', None),
                                p.get('RQD', None))
        elif st == 'Elastic':
            k = py_elastic(z_eff, p['kh'], self.D)
            return k, None
        return 0.01, 0.001

    def _calc_georgiadis_depths(self):
        if not self.soil_layers:
            return
            
        dz = 0.01
        self.soil_layers[0]['z_eq_top'] = 0.0
        
        for i in range(len(self.soil_layers)):
            layer = self.soil_layers[i]
            H = layer['z_bottom'] - layer['z_top']
            layer['z_eq_bottom'] = layer['z_eq_top'] + H
            
            if i == len(self.soil_layers) - 1:
                break
            
                                 
            n_pts = max(int(layer['z_eq_bottom'] / dz) + 1, 10)
            z_arr = np.linspace(0, layer['z_eq_bottom'], n_pts)
            pult_arr = np.zeros(n_pts)
            
            for j, z in enumerate(z_arr):
                pult, _ = self._eval_pult_for_layer(layer, z)
                pult_arr[j] = pult if pult else 0
            
                                    
            F_i = np.trapz(pult_arr, z_arr)
            
                                  
            next_layer = self.soil_layers[i+1]
            Z_max = min(100.0, layer['z_eq_bottom'] * 2)             
            n_pts_next = max(int(Z_max / dz) + 1, 10)
            Z_arr = np.linspace(0, Z_max, n_pts_next)
            pult_next_arr = np.zeros(n_pts_next)
            
            for j, Z in enumerate(Z_arr):
                pult, _ = self._eval_pult_for_layer(next_layer, Z)
                pult_next_arr[j] = pult if pult else 0
            
                               
            cumF_arr = np.array([np.trapz(pult_next_arr[:k+1], Z_arr[:k+1]) 
                                 for k in range(len(Z_arr))])
            
                                
            if F_i > cumF_arr[-1]:
                Z_eq = Z_arr[-1]
            elif F_i <= cumF_arr[0]:
                Z_eq = 0.0
            else:
                Z_eq = np.interp(F_i, cumF_arr, Z_arr)
            
            next_layer['z_eq_top'] = Z_eq

    def _get_py_params(self, z):
        for layer in self.soil_layers:
            if layer['z_top'] <= z <= layer['z_bottom']:
                # Georgiadis Effective Depth Layer Substitution
                z_eq_top = layer.get('z_eq_top', 0.0)
                z_eff = z_eq_top + (z - layer['z_top'])
                return self._eval_pult_for_layer(layer, z_eff)
        return 0.01, 0.001

    @staticmethod
    def _native_py_soil_type(soil_type):
        if soil_type in (
            'Soft Clay Soil',
            'Submerged Stiff Clay',
            'Dry Stiff Clay',
            'Modified Stiff Clay without Free Water',
        ):
            return 1
        if soil_type in ('API Method for Sand', 'Sand'):
            return 2
        return None

    # -----------------------------------------------------------------
              
    # -----------------------------------------------------------------
    def analyze(self, lateral_load=0.0, lateral_disp=None,
                moment_load=0.0,
                top_bc='free', bottom_bc='free',
                n_steps=20, verbose=True):
        if verbose:
            print("=" * 50)
            print("Lateral pile analysis")
            print(f"  pile_length={self.L} m, pile_diameter={self.D} m, free_length={self.free_length} m")
            print(f"  elements={self.n_eles}, nodes={self.n_nodes}")
            print(f"  load: H={lateral_load} kN, M={moment_load} kN*m")
            print("=" * 50)

                                    
        self._calc_georgiadis_depths()

                               
        ops.wipe()
        ops.model('basic', '-ndm', 2, '-ndf', 3)

                        
        for i in range(self.n_nodes):
            y_coord = -self.node_arc_lengths[i] + self.free_length
            ops.node(i + 1, 0.0, y_coord)                  
            ops.node(i + 1001, 0.0, y_coord)                   
            ops.fix(i + 1001, 1, 1, 1)

                        
        if bottom_bc == 'pinned':
            ops.fix(self.n_nodes, 1, 1, 0)
        elif bottom_bc == 'fixed':
            ops.fix(self.n_nodes, 1, 1, 1)
        else:  # free
            ops.fix(self.n_nodes, 0, 1, 0)          

                        
        if top_bc == 'fixed_rotation':
            ops.fix(1, 0, 0, 1)          

                      
        ops.geomTransf('Linear', 1)
        G_pile = self.E / (2.0 * (1.0 + self.poisson_ratio))
        Avy = self.shear_area_factor * self.A
        fiber_section_tags, fiber_segments = self._build_fiber_section_tags()
        elastic_integration_tag = None if fiber_section_tags else self._build_elastic_section_integration()
        for i in range(self.n_eles):
            arc_mid = 0.5 * (self.node_arc_lengths[i] + self.node_arc_lengths[i + 1])
            integration_tag = self._integration_tag_for_position(arc_mid, fiber_section_tags, fiber_segments)
            if integration_tag is not None:
                ops.element('forceBeamColumn', i + 1, i + 1, i + 2, 1, integration_tag)
            elif elastic_integration_tag is not None:
                ops.element('forceBeamColumn', i + 1, i + 1, i + 2, 1, elastic_integration_tag)
            elif self.use_timoshenko:
                try:
                    ops.element('ElasticTimoshenkoBeam', i + 1, i + 1, i + 2,
                                self.E, G_pile, self.A, self.I, Avy, 1)
                except Exception:
                    ops.element('elasticBeamColumn', i + 1, i + 1, i + 2,
                                self.A, self.E, self.I, 1)
            else:
                ops.element('elasticBeamColumn', i + 1, i + 1, i + 2,
                            self.A, self.E, self.I, 1)

                      
        n_py_pts = 25
        y_max = 0.2  # m

        for i in range(self.n_nodes):
                               
            z = self.node_arc_lengths[i] - self.free_length
            mat_tag = i + 2001

            if z < 0:
                                
                ops.uniaxialMaterial('Elastic', mat_tag, 1e-6)
            else:
                        
                L_trib = self.node_tributary_lengths[i]

                pult, y50 = self._get_py_params(z)

                if pult < 1e-6 or y50 is None:
                             
                    k_spring = pult * L_trib * self.p_multiplier if y50 is None else 1e-3
                    ops.uniaxialMaterial('Elastic', mat_tag, k_spring)
                elif self.spring_model_mode == 'native':
                    soil_type = self._get_soil_type_at(z)
                    native_soil_type = self._native_py_soil_type(soil_type)
                    if native_soil_type is None:
                        pass
                    else:
                        ops.uniaxialMaterial(
                            'PySimple1',
                            mat_tag,
                            native_soil_type,
                            float(pult * L_trib * self.p_multiplier),
                            float(y50),
                            0.3,
                        )
                        native_soil_type = native_soil_type
                    if native_soil_type is None:
                        # Fallback to current multilinear representation when no native analogue exists.
                        y_small = np.array([0, 1e-4, 5e-4, 1e-3, 3e-3, 5e-3])
                        y_linear = np.linspace(y_max / n_py_pts, y_max, n_py_pts)[1:]
                        y_vals = np.unique(np.concatenate([y_small, y_linear]))
                        z0 = max(0.0, z - 0.5 * self.segment_lengths[i - 1]) if i > 0 else 0.0
                        z1 = max(0.0, z + 0.5 * self.segment_lengths[i]) if i < self.n_eles else max(0.0, z)
                        z_samples = np.array([max(z, 0.0)]) if z1 <= z0 else np.linspace(z0, z1, 3)
                        p_curve_avg = np.mean(
                            np.array([self._py_curve_per_unit_length(zs, y_vals) for zs in z_samples]),
                            axis=0
                        )
                        force_pos = p_curve_avg * L_trib * self.p_multiplier
                        force_pos[0] = 0.0
                        y_neg = -y_vals[::-1][:-1]
                        f_neg = -force_pos[::-1][:-1]
                        y_all = np.concatenate([y_neg, y_vals])
                        f_all = np.concatenate([f_neg, force_pos])
                        ops.uniaxialMaterial('ElasticMultiLinear', mat_tag,
                                             '-strain', *y_all.tolist(),
                                             '-stress', *f_all.tolist())
                else:
                                  
                                                               
                    # Densify the small-displacement range so the multilinear
                    # spring tracks the theoretical p-y curve in the working range.
                    y_small = np.array([0, 1e-4, 5e-4, 1e-3, 3e-3, 5e-3])
                    y_linear = np.linspace(y_max / n_py_pts, y_max, n_py_pts)[1:]
                    y_vals = np.unique(np.concatenate([y_small, y_linear]))
                    z0 = max(0.0, z - 0.5 * self.segment_lengths[i - 1]) if i > 0 else 0.0
                    z1 = max(0.0, z + 0.5 * self.segment_lengths[i]) if i < self.n_eles else max(0.0, z)
                    z_samples = np.array([max(z, 0.0)]) if z1 <= z0 else np.linspace(z0, z1, 3)
                    p_curve_avg = np.mean(
                        np.array([self._py_curve_per_unit_length(zs, y_vals) for zs in z_samples]),
                        axis=0
                    )

                                        
                    soil_type = self._get_soil_type_at(z)
                    layer_params = self._get_layer_at(z)
                    z_eq_top = layer_params.get('z_eq_top', 0.0)
                    z_eff_for_curve = z_eq_top + (z - layer_params['z_top'])
                    z_eff_for_curve = max(z_eff_for_curve, 0.01)
                    
                    if soil_type == 'Sand':
                        lp = layer_params['params']
                        p_curve = generate_reese_sand_py_points(
                            y_vals, z_eff_for_curve,
                            lp.get('gammaEff', 0.0),
                            lp.get('phiDegree', 30),
                            self.D, lp.get('kpy', 0.0),
                            lp.get('is_cyclic', False))
                    elif soil_type in ('API Method for Sand',):
                        k_mod = layer_params['params'].get('k_modulus', 0.0)
                        _, p_curve = generate_py_curve(
                            pult, y50, 'API Method for Sand', y_vals,
                            k_modulus=k_mod, z=z_eff_for_curve)
                    elif soil_type == 'Soft Clay Soil':
                        _, p_curve = generate_py_curve(
                            pult, y50, 'Soft Clay Soil', y_vals)
                    elif soil_type == 'Submerged Stiff Clay':
                        k_mod = layer_params['params'].get('k_modulus', 0.0)
                        A_coeff = stiff_clay_with_water_A(
                            z_eff_for_curve / self.D,
                            layer_params['params'].get('is_cyclic', False),
                        )
                        _, p_curve = generate_py_curve(
                            pult, y50, 'Submerged Stiff Clay', y_vals,
                            k_modulus=k_mod, z=z_eff_for_curve, A=A_coeff)
                    elif soil_type == 'Dry Stiff Clay':
                        _, p_curve = generate_py_curve(
                            pult, y50, 'Dry Stiff Clay', y_vals)
                    elif soil_type == 'Modified Stiff Clay without Free Water':
                        k_mod = layer_params['params'].get('k_modulus', 0.0)
                        _, p_curve = generate_py_curve(
                            pult, y50, 'Modified Stiff Clay without Free Water',
                            y_vals, k_modulus=k_mod, z=z_eff_for_curve)
                    elif soil_type == 'Weak Rock':
                        Eir_val = layer_params['params'].get('Eir', 100000.0)
                        xr = z_eff_for_curve / self.D
                        kir = min(100.0 + 400.0 * (xr / 3.0), 500.0)
                        Kir_val = kir * Eir_val
                        _, p_curve = generate_py_curve(
                            pult, y50, 'Weak Rock', y_vals,
                            k_modulus=Kir_val, z=z_eff_for_curve)
                    else:
                        _, p_curve = generate_py_curve(
                            pult, y50, 'Soft Clay Soil', y_vals)

                                                           
                    p_curve = p_curve_avg
                    force_pos = p_curve * L_trib * self.p_multiplier
                    force_pos[0] = 0.0

                            
                    y_neg = -y_vals[::-1][:-1]
                    f_neg = -force_pos[::-1][:-1]
                    y_all = np.concatenate([y_neg, y_vals])
                    f_all = np.concatenate([f_neg, force_pos])

                    ops.uniaxialMaterial('ElasticMultiLinear', mat_tag,
                                         '-strain', *y_all.tolist(),
                                         '-stress', *f_all.tolist())

                         
            ele_tag = i + 2001
            ops.element('zeroLength', ele_tag, i + 1001, i + 1,
                        '-mat', mat_tag, '-dir', 1)

                     
        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)

        if lateral_disp is not None:
                    
            ops.load(1, 1.0, 0.0, 0.0)           
        else:
            if lateral_load != 0:
                ops.load(1, lateral_load, 0.0, 0.0)
            if moment_load != 0:
                                                
                                       
                          
                ops.load(1, 0.0, 0.0, -moment_load)

                        
        ops.system('BandGeneral')
        ops.numberer('RCM')
        ops.constraints('Penalty', 1e15, 1e15)
        ops.test('NormDispIncr', 1e-6, 500, 0)
        ops.algorithm('KrylovNewton')

        if lateral_disp is not None:
            ops.integrator('DisplacementControl', 1, 1,
                           lateral_disp / n_steps)
        else:
            ops.integrator('LoadControl', 1.0 / n_steps)

        ops.analysis('Static')

                                        
        success = True
        for step in range(n_steps):
            ok = ops.analyze(1)

            if ok != 0:
                                                              
                algorithms = [
                    ('Newton', lambda: ops.algorithm('Newton')),
                    ('Broyden', lambda: ops.algorithm('Broyden', 8)),
                    ('NewtonLineSearch', lambda: ops.algorithm('NewtonLineSearch')),
                    ('BFGS', lambda: ops.algorithm('BFGS')),
                    ('ModifiedNewton', lambda: ops.algorithm('ModifiedNewton', '-initial')),
                ]

                for name, set_algo in algorithms:
                    set_algo()
                    ok = ops.analyze(1)
                    if ok == 0:
                        if verbose:
                            print(f"  Step {step}: converged with {name}")
                        ops.algorithm('KrylovNewton')
                        break

                if ok != 0:
                    if verbose:
                        print(f"  [WARN] Step {step}: failed to converge")
                    success = False
                    break

        if verbose:
            if success:
                print("[OK] 鍒嗘瀽鎴愬姛鏀舵暃!")
            else:
                print("[FAIL] 鍒嗘瀽鏈畬鍏ㄦ敹鏁?")

                        
        self._extract_results()
        return self.results

    def _get_soil_type_at(self, z):
        for layer in self.soil_layers:
            if layer['z_top'] <= z <= layer['z_bottom']:
                return layer['type']
        return 'unknown'

    def _get_layer_at(self, z):
        for layer in self.soil_layers:
            if layer['z_top'] <= z <= layer['z_bottom']:
                return layer
        return None

    def _py_curve_per_unit_length(self, z, y_vals):
        """Build a p-y curve per unit length at one vertical depth."""
        pult, y50 = self._get_py_params(z)
        if pult < 1e-6 or y50 is None:
            if y50 is None:
                return y_vals * max(pult, 0.0)
            return np.zeros_like(y_vals)

        soil_type = self._get_soil_type_at(z)
        layer_params = self._get_layer_at(z)
        z_eq_top = layer_params.get('z_eq_top', 0.0)
        z_eff_for_curve = z_eq_top + (z - layer_params['z_top'])
        z_eff_for_curve = max(z_eff_for_curve, 0.01)

        if soil_type == 'Sand':
            lp = layer_params['params']
            return generate_reese_sand_py_points(
                y_vals, z_eff_for_curve,
                lp.get('gammaEff', 0.0),
                lp.get('phiDegree', 30),
                self.D, lp.get('kpy', 0.0),
                lp.get('is_cyclic', False))
        if soil_type in ('API Method for Sand',):
            k_mod = layer_params['params'].get('k_modulus', 0.0)
            _, p_curve = generate_py_curve(
                pult, y50, 'API Method for Sand', y_vals,
                k_modulus=k_mod, z=z_eff_for_curve)
            return p_curve
        if soil_type == 'Soft Clay Soil':
            _, p_curve = generate_py_curve(
                pult, y50, 'Soft Clay Soil', y_vals)
            return p_curve
        if soil_type == 'Submerged Stiff Clay':
            k_mod = layer_params['params'].get('k_modulus', 0.0)
            A_coeff = stiff_clay_with_water_A(
                z_eff_for_curve / self.D,
                layer_params['params'].get('is_cyclic', False),
            )
            _, p_curve = generate_py_curve(
                pult, y50, 'Submerged Stiff Clay', y_vals,
                k_modulus=k_mod, z=z_eff_for_curve, A=A_coeff)
            return p_curve
        if soil_type == 'Dry Stiff Clay':
            _, p_curve = generate_py_curve(
                pult, y50, 'Dry Stiff Clay', y_vals)
            return p_curve
        if soil_type == 'Modified Stiff Clay without Free Water':
            k_mod = layer_params['params'].get('k_modulus', 0.0)
            _, p_curve = generate_py_curve(
                pult, y50, 'Modified Stiff Clay without Free Water',
                y_vals, k_modulus=k_mod, z=z_eff_for_curve)
            return p_curve
        if soil_type == 'Weak Rock':
            Eir_val = layer_params['params'].get('Eir', 100000.0)
            xr = z_eff_for_curve / self.D
            kir = min(100.0 + 400.0 * (xr / 3.0), 500.0)
            Kir_val = kir * Eir_val
            _, p_curve = generate_py_curve(
                pult, y50, 'Weak Rock', y_vals,
                k_modulus=Kir_val, z=z_eff_for_curve)
            return p_curve

        _, p_curve = generate_py_curve(
            pult, y50, 'Soft Clay Soil', y_vals)
        return p_curve

    # -----------------------------------------------------------------
            
    # -----------------------------------------------------------------
    def _extract_results(self):
        depths = np.zeros(self.n_nodes)
        disps = np.zeros(self.n_nodes)
        rotations = np.zeros(self.n_nodes)

        for i in range(self.n_nodes):
            depths[i] = self.node_arc_lengths[i] - self.free_length
            disps[i] = ops.nodeDisp(i + 1, 1)
            # Flip OpenSees CCW-positive rotation to match the GUI/RSPile sign convention.
            rotations[i] = -ops.nodeDisp(i + 1, 3)

                
                                                          
        depths_ele = np.zeros(self.n_eles)
        moments = np.zeros(self.n_eles)
        shears = np.zeros(self.n_eles)

        for i in range(self.n_eles):
            depths_ele[i] = 0.5 * (self.node_arc_lengths[i] + self.node_arc_lengths[i + 1]) - self.free_length
            force = ops.eleForce(i + 1)
            # force = [Fx_i, Fy_i, M_i, Fx_j, Fy_j, M_j]
            shears[i] = force[0]                
            moments[i] = -force[2]                             

                           
        # zeroLength: I-node=soil(fixed), J-node=pile
                                                           
                                                                
        soil_reactions = np.zeros(self.n_nodes)
        soil_reactions_per_m = np.zeros(self.n_nodes)
        soil_stiffness = np.zeros(self.n_nodes)
        for i in range(self.n_nodes):
            z = depths[i]
            if z >= 0:
                ele_tag = i + 2001
                        
                L_trib = self.node_tributary_lengths[i]
                try:
                    f = ops.eleForce(ele_tag)
                    # f[3] is the pile-side x-force at the zeroLength spring.
                    soil_reactions[i] = f[3] if len(f) > 3 else 0.0
                    soil_reactions_per_m[i] = soil_reactions[i] / L_trib
                    if abs(disps[i]) > 1.0e-12:
                        soil_stiffness[i] = abs(soil_reactions_per_m[i] / disps[i])
                except Exception:
                    soil_reactions[i] = 0.0
                    soil_reactions_per_m[i] = 0.0
                    soil_stiffness[i] = 0.0

        self.results = {
            'depths': depths,
            'displacements': disps * 1000,  # mm
            'rotations': rotations,
            'depths_ele': depths_ele,
            'moments': moments,
            'shears': shears,
            'soil_reactions': soil_reactions,         # kN (total force)
            'soil_reactions_per_m': soil_reactions_per_m,  # kN/m
            'soil_stiffness': soil_stiffness,  # kN/m^2
            'pile_top_disp': disps[0] * 1000,  # mm
            'max_moment': np.max(np.abs(moments)),
            'max_moment_depth': depths_ele[np.argmax(np.abs(moments))],
            'debug_pile_area_m2': float(self.A),
            'debug_pile_inertia_m4': float(self.I),
            'debug_pile_E_kPa': float(self.E),
            'debug_elastic_EA_kN': float(self.E * self.A),
            'debug_elastic_EI_kN_m2': float(self.E * self.I),
            'debug_fiber_initial_EA_kN': getattr(self, '_debug_fiber_initial_EA_kN', None),
            'debug_fiber_initial_EIy_kN_m2': getattr(self, '_debug_fiber_initial_EIy_kN_m2', None),
            'debug_fiber_initial_EIz_kN_m2': getattr(self, '_debug_fiber_initial_EIz_kN_m2', None),
            'debug_section_mode': self.section_mode,
            'debug_spring_model_mode': self.spring_model_mode,
        }

    # -----------------------------------------------------------------
            
    # -----------------------------------------------------------------
    def plot_results(self, show=True):
        r = self.results

        fig, axes = plt.subplots(1, 4, figsize=(16, 8))
        fig.suptitle(f'Lateral Pile Analysis Results\n'
                     f'D={self.D}m, L={self.L}m, E={self.E/1e6:.0f}MPa',
                     fontsize=12, fontweight='bold')

                
        ax = axes[0]
        ax.plot(r['displacements'], r['depths'], 'b-', linewidth=2)
        ax.axvline(x=0, color='gray', linestyle='-', alpha=0.3)
        ax.set_xlabel('Displacement (mm)')
        ax.set_ylabel('Depth (m)')
        ax.set_title('(a) Displacement')
        ax.invert_yaxis()
        ax.grid(True, alpha=0.3)

                
        ax = axes[1]
        ax.plot(r['moments'], r['depths_ele'], 'r-', linewidth=2)
        ax.axvline(x=0, color='gray', linestyle='-', alpha=0.3)
        ax.set_xlabel('Moment (kN路m)')
        ax.set_title('(b) Moment')
        ax.invert_yaxis()
        ax.grid(True, alpha=0.3)

                
        ax = axes[2]
        ax.plot(r['shears'], r['depths_ele'], 'g-', linewidth=2)
        ax.axvline(x=0, color='gray', linestyle='-', alpha=0.3)
        ax.set_xlabel('Shear (kN)')
        ax.set_title('(c) Shear')
        ax.invert_yaxis()
        ax.grid(True, alpha=0.3)

                  
        ax = axes[3]
        ax.plot(r['soil_reactions'], r['depths'], 'm-', linewidth=2)
        ax.axvline(x=0, color='gray', linestyle='-', alpha=0.3)
        ax.set_xlabel('Soil Reaction (kN)')
        ax.set_title('(d) Soil Reaction')
        ax.invert_yaxis()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        if show:
            plt.show()
        return fig


# =============================================================================
            
# =============================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("妯悜妗╂眰瑙ｅ櫒娴嬭瘯 (API Sand)")
    print("=" * 60)

    solver = LateralPileSolver(
        pile_length=10.0,
        pile_diameter=0.5,
        E_pile=200e6,             
        ele_size=0.2
    )

                         
    solver.add_soil_layer(0, 5, 'Soft Clay Soil', gammaEff=10.0, cu=30.0, eps50=0.02)
                     
    solver.add_soil_layer(5, 20, 'API Method for Sand', gammaEff=18.0, phiDegree=30.0, k_modulus=10000.0)

    results = solver.analyze(lateral_load=100.0, n_steps=20, verbose=True)

    print(f"\n妗╅《浣嶇Щ: {results['pile_top_disp']:.4f} mm")
    print(f"鏈€澶у集鐭? {results['max_moment']:.2f} kN路m")
    print(f"鏈€澶у集鐭╂繁搴? {results['max_moment_depth']:.2f} m")

    # solver.plot_results()



