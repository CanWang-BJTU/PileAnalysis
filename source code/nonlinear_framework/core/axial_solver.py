# -*- coding: utf-8 -*-

import numpy as np
import openseespy.opensees as ops

try:
    from .tz_model import (
        generate_tz_curve,
        tz_clay_api,
        tz_drilled_clay,
        tz_drilled_sand,
        tz_elastic,
        tz_sand_api,
    )
    from .qz_model import (
        generate_qz_curve,
        qz_clay_api,
        qz_drilled_clay,
        qz_drilled_sand,
        qz_elastic,
        qz_sand_api,
    )
except Exception:
    from tz_model import (
        generate_tz_curve,
        tz_clay_api,
        tz_drilled_clay,
        tz_drilled_sand,
        tz_elastic,
        tz_sand_api,
    )
    from qz_model import (
        generate_qz_curve,
        qz_clay_api,
        qz_drilled_clay,
        qz_drilled_sand,
        qz_elastic,
        qz_sand_api,
    )


class AxialPileSolver:
    """Axial pile solver with RSPile-style midpoint shaft spring discretization."""

    def __init__(
        self,
        pile_length,
        pile_diameter,
        E_pile,
        A_pile=None,
        ele_size=None,
        mesh_positions=None,
        section_mode='elastic',
        spring_model_mode='multilinear',
        fiber_section_library=None,
        fiber_section_segments=None,
    ):
        self.L = float(pile_length)
        self.D = float(pile_diameter)
        self.E = float(E_pile)
        self.A = np.pi * self.D**2 / 4.0 if A_pile is None else float(A_pile)
        self.section_mode = str(section_mode or 'elastic')
        self.spring_model_mode = str(spring_model_mode or 'multilinear').lower()
        self.fiber_section_library = list(fiber_section_library or [])
        self.fiber_section_segments = list(fiber_section_segments or [])
        if mesh_positions is not None and len(mesh_positions) >= 2:
            self.node_depths = np.array([float(v) for v in mesh_positions], dtype=float)
            self.node_depths[0] = 0.0
            self.node_depths[-1] = self.L
        else:
            self.ele_size = self.L / 400.0 if ele_size in (None, 0, 0.0) else float(ele_size)
            n_eles = max(int(round(self.L / self.ele_size)), 1)
            self.node_depths = np.linspace(0.0, self.L, n_eles + 1)

        self.segment_lengths = np.diff(self.node_depths)
        self.segment_centers = 0.5 * (self.node_depths[:-1] + self.node_depths[1:])
        self.half_element_lengths = np.repeat(self.segment_lengths / 2.0, 2)
        self.n_eles = len(self.segment_lengths)
        self.n_nodes = self.n_eles + 1
        self.n_model_nodes = 2 * self.n_eles + 1
        self.ele_size = float(np.mean(self.segment_lengths)) if self.n_eles else self.L

        self.soil_layers = []
        self.tip_soil = None
        self.results = {}
        self._sigma_v_cache = None
        self._mat_tag_seed = 500000
        self._debug_fiber_initial_EA_kN = None
        self.half_element_centers = np.empty(self.n_model_nodes - 1, dtype=float)
        for i in range(self.n_eles):
            z0 = self.node_depths[i]
            z1 = self.node_depths[i + 1]
            self.half_element_centers[2 * i] = z0 + 0.25 * (z1 - z0)
            self.half_element_centers[2 * i + 1] = z0 + 0.75 * (z1 - z0)

    def _next_mat_tag(self):
        tag = self._mat_tag_seed
        self._mat_tag_seed += 1
        return tag

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

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
            segments = [{'top_m': 0.0, 'bottom_m': self.L, 'section_name': only_name}]
        return library, segments

    def _create_fiber_uniaxial_material(self, kind, params, elastic_modulus):
        mat_tag = self._next_mat_tag()
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
            ops.uniaxialMaterial('Concrete04', mat_tag, fc, epsc0, epsu, max(Ec, 1.0))
        else:
            ops.uniaxialMaterial('Elastic', mat_tag, max(Ec, 1.0))
        return mat_tag

    def _section_area_totals(self, section_def):
        mats = dict(section_def.get('material_params', {}) or {})
        fibers = dict(section_def.get('fibers', {}) or {})
        core_area = 0.0
        cover_area = 0.0
        rebar_area = 0.0
        for row in fibers.get('core', []) or []:
            core_area += self._safe_float(row.get('area_m2', 0.0))
        for role in ('inner_cover', 'outer_cover'):
            for row in fibers.get(role, []) or []:
                cover_area += self._safe_float(row.get('area_m2', 0.0))
        for group in fibers.get('rebar_groups', []) or []:
            for row in group.get('fibers', []) or []:
                rebar_area += self._safe_float(row.get('area_m2', 0.0))
        return mats, core_area, cover_area, rebar_area

    @staticmethod
    def _material_stress(material_tag, strain):
        ops.testUniaxialMaterial(material_tag)
        # Axial solver convention matches the existing elastic branch:
        # negative deformation/strain means downward compression.
        # This is also the native sign convention for OpenSees concrete materials.
        ops.setStrain(float(strain))
        return float(ops.getStress())

    def _section_axial_force_at_strain(self, section_def, strain):
        mats, core_area, cover_area, rebar_area = self._section_area_totals(section_def)
        total_force = 0.0

        if core_area > 0.0:
            core_mat = self._create_fiber_uniaxial_material('concrete', mats.get('core_concrete', {}), self.E)
            total_force += self._material_stress(core_mat, strain) * core_area
        if cover_area > 0.0:
            cover_mat = self._create_fiber_uniaxial_material('concrete', mats.get('cover_concrete', {}), self.E)
            total_force += self._material_stress(cover_mat, strain) * cover_area
        if rebar_area > 0.0:
            rebar_mat = self._create_fiber_uniaxial_material('steel', mats.get('rebar', {}), self.E)
            total_force += self._material_stress(rebar_mat, strain) * rebar_area

        return float(total_force)

    def _section_axial_force_points(self, section_def, strain_points):
        force_points = [
            self._section_axial_force_at_strain(section_def, strain)
            for strain in np.asarray(strain_points, dtype=float)
        ]
        return np.asarray(force_points, dtype=float)

    def _find_section_for_depth(self, depth):
        library, segments = self._resolve_fiber_sections()
        if not library or not segments:
            return None
        for segment in segments:
            if segment['top_m'] - 1.0e-9 <= depth <= segment['bottom_m'] + 1.0e-9:
                return library.get(segment['section_name'])
        return library.get(segments[-1]['section_name'])

    def _build_axial_section_material(self, half_length, depth):
        section_def = self._find_section_for_depth(depth)
        if section_def is None:
            return None
        strain_points = np.array([-0.015, -0.01, -0.006, -0.003, -0.001, -0.0002, 0.0, 0.0002, 0.001, 0.003, 0.006, 0.01, 0.015], dtype=float)
        disp_points = strain_points * max(float(half_length), 1.0e-9)
        force_points = self._section_axial_force_points(section_def, strain_points)
        if self._debug_fiber_initial_EA_kN is None:
            eps0 = -1.0e-8
            debug_force_points = self._section_axial_force_points(section_def, np.array([0.0, eps0], dtype=float))
            if abs(eps0) > 1.0e-18:
                self._debug_fiber_initial_EA_kN = abs((debug_force_points[1] - debug_force_points[0]) / eps0)
        mat_tag = self._next_mat_tag()
        ops.uniaxialMaterial('ElasticMultiLinear', mat_tag, '-strain', *disp_points.tolist(), '-stress', *force_points.tolist())
        return mat_tag

    def _get_tz_curve_type(self, soil_type):
        if soil_type == "API Sand":
            return "api_sand"
        if soil_type == "API Clay":
            return "api_clay"
        if soil_type == "Drilled Sand":
            return "drilled_sand"
        if soil_type == "Drilled Clay":
            return "drilled_clay"
        return "hyperbolic"

    def _get_qz_curve_type(self, soil_type):
        if soil_type in ("API Sand", "API Clay"):
            return "api"
        if soil_type == "Drilled Sand":
            return "drilled_sand"
        if soil_type == "Drilled Clay":
            return "drilled_clay"
        return "api"

    @staticmethod
    def _native_axial_soil_type(soil_type):
        return 1 if soil_type in ("API Clay", "Drilled Clay") else 2

    def _build_tz_displacement_points(self, curve_type, z50):
        if curve_type == "api_sand":
            return np.array([0.0, 0.00254], dtype=float)
        if curve_type == "api_clay":
            d_equiv = z50 / 0.0031 if z50 > 0 else self.D
            return d_equiv * np.array([0.0, 0.0016, 0.0031, 0.0057, 0.0080, 0.0100, 0.0200, 0.0500], dtype=float)
        if curve_type == "drilled_clay":
            d_equiv = z50 / 0.0010 if z50 > 0 else self.D
            return d_equiv * np.array([0.0, 0.0005, 0.0010, 0.0020, 0.0040, 0.0060, 0.0080, 0.0100, 0.0150, 0.0200], dtype=float)
        if curve_type == "drilled_sand":
            d_equiv = z50 / 0.0027 if z50 > 0 else self.D
            return d_equiv * np.array([0.0, 0.0005, 0.0010, 0.0020, 0.0040, 0.0060, 0.0080, 0.0100, 0.0120, 0.0150, 0.0200], dtype=float)
        return np.array(
            [
                0.0,
                max(0.25 * z50, 1.0e-6),
                max(0.5 * z50, 2.0e-6),
                max(1.0 * z50, 4.0e-6),
                max(2.0 * z50, 8.0e-6),
                max(5.0 * z50, 2.0e-5),
                max(10.0 * z50, 4.0e-5),
                max(20.0 * z50, 8.0e-5),
            ],
            dtype=float,
        )

    def _build_qz_displacement_points(self, curve_type, q50):
        if curve_type == "api":
            d_equiv = q50 / 0.013 if q50 > 0 else self.D
            return d_equiv * np.array([0.0, 0.0020, 0.0130, 0.0420, 0.0730, 0.1000, 0.2000], dtype=float)
        if curve_type == "drilled_clay":
            d_equiv = q50 / 0.006 if q50 > 0 else self.D
            return d_equiv * np.array([0.0, 0.0020, 0.0040, 0.0060, 0.0100, 0.0200, 0.0350, 0.0600, 0.1000], dtype=float)
        if curve_type == "drilled_sand":
            d_equiv = q50 / 0.028 if q50 > 0 else self.D
            return d_equiv * np.array([0.0, 0.0100, 0.0200, 0.0400, 0.0600, 0.0800, 0.1000, 0.1100], dtype=float)
        return np.array(
            [
                0.0,
                max(0.25 * q50, 1.0e-6),
                max(0.5 * q50, 2.0e-6),
                max(1.0 * q50, 4.0e-6),
                max(2.0 * q50, 8.0e-6),
                max(5.0 * q50, 2.0e-5),
                max(10.0 * q50, 4.0e-5),
                max(20.0 * q50, 8.0e-5),
            ],
            dtype=float,
        )

    def add_soil_layer(self, z_top, z_bottom, soil_type, **params):
        self.soil_layers.append(
            {
                "z_top": float(z_top),
                "z_bottom": float(z_bottom),
                "type": soil_type,
                "params": params,
            }
        )

    def set_tip_soil(self, soil_type, **params):
        self.tip_soil = {"type": soil_type, "params": params}

    def _compute_sigma_v(self, z):
        sigma_v = 0.0
        for layer in sorted(self.soil_layers, key=lambda item: item["z_top"]):
            if z <= layer["z_top"]:
                break
            gamma = float(layer["params"].get("gammaEff", 18.0))
            z_bot = min(z, float(layer["z_bottom"]))
            thickness = max(0.0, z_bot - float(layer["z_top"]))
            sigma_v += gamma * thickness
            if z <= layer["z_bottom"]:
                break
        return max(sigma_v, 0.01)

    def _precompute_sigma_v_array(self):
        if self._sigma_v_cache is not None:
            return self._sigma_v_cache
        depths = self.segment_centers
        self._sigma_v_cache = np.array([self._compute_sigma_v(z) for z in depths], dtype=float)
        return self._sigma_v_cache

    def _get_soil_type_at(self, z):
        for layer in self.soil_layers:
            if float(layer["z_top"]) <= z <= float(layer["z_bottom"]):
                return layer["type"]
        return "unknown"

    def _get_tz_params(self, z, seg_idx=None):
        for layer in self.soil_layers:
            if float(layer["z_top"]) <= z <= float(layer["z_bottom"]):
                p = layer["params"]
                st = layer["type"]
                sigma_v = self._sigma_v_cache[seg_idx] if seg_idx is not None and self._sigma_v_cache is not None else self._compute_sigma_v(z)

                if st == "API Sand":
                    return tz_sand_api(
                        phiDegree=p.get("phiDegree", 30),
                        d=self.D,
                        sigmaV=sigma_v,
                        z=z,
                        elelength=self.segment_lengths[seg_idx] if seg_idx is not None else self.ele_size,
                        K=p.get("K", 0.8),
                        limit_fmax=p.get("limit_fmax", True),
                        max_unit_skin_friction=p.get("max_unit_skin_friction"),
                    )
                if st == "API Clay":
                    return tz_clay_api(
                        cu=p.get("cu", 50),
                        d=self.D,
                        sigmaV=sigma_v,
                        z=z,
                        elelength=self.segment_lengths[seg_idx] if seg_idx is not None else self.ele_size,
                        max_unit_skin_friction=p.get("max_unit_skin_friction"),
                    )
                if st == "Drilled Sand":
                    return tz_drilled_sand(
                        phiDegree=p.get("phiDegree", 30),
                        d=self.D,
                        sigmaV=sigma_v,
                        z=z,
                        elelength=self.segment_lengths[seg_idx] if seg_idx is not None else self.ele_size,
                        max_unit_skin_friction=p.get("max_unit_skin_friction"),
                    )
                if st == "Drilled Clay":
                    return tz_drilled_clay(
                        cu=p.get("cu", 50),
                        d=self.D,
                        sigmaV=sigma_v,
                        z=z,
                        elelength=self.segment_lengths[seg_idx] if seg_idx is not None else self.ele_size,
                        max_unit_skin_friction=p.get("max_unit_skin_friction"),
                    )
                if st == "Elastic":
                    return tz_elastic(ks=p.get("ks", 1e5), d=self.D, elelength=self.segment_lengths[seg_idx] if seg_idx is not None else self.ele_size)
        return 0.01, 0.001

    def _get_qz_params(self):
        if self.tip_soil is None:
            self._last_qz_area = None
            self._last_qz_qult = 0.01
            self._last_qz_z50 = 0.001
            return 0.01, 0.001

        p = self.tip_soil["params"]
        st = self.tip_soil["type"]
        sigma_v = self._compute_sigma_v(self.L)
        a_base = p.get("A_tip", p.get("A_base", None))
        self._last_qz_area = None if a_base is None else float(a_base)

        if st == "API Sand":
            qult, z50 = qz_sand_api(
                phiDegree=p.get("phiDegree", 30),
                d=self.D,
                sigmaV=sigma_v,
                Nq=p.get("Nq"),
                A_base=a_base,
                max_unit_end_bearing=p.get("max_unit_end_bearing"),
            )
            self._last_qz_qult = qult
            self._last_qz_z50 = z50
            return qult, z50
        if st == "API Clay":
            qult, z50 = qz_clay_api(
                cu=p.get("cu", 100),
                d=self.D,
                A_base=a_base,
                max_unit_end_bearing=p.get("max_unit_end_bearing"),
            )
            self._last_qz_qult = qult
            self._last_qz_z50 = z50
            return qult, z50
        if st == "Drilled Sand":
            qult, z50 = qz_drilled_sand(
                phiDegree=p.get("phiDegree", 30),
                d=self.D,
                sigmaV=sigma_v,
                G=p.get("G"),
                A_base=a_base,
                max_unit_end_bearing=p.get("max_unit_end_bearing"),
            )
            self._last_qz_qult = qult
            self._last_qz_z50 = z50
            return qult, z50
        if st == "Drilled Clay":
            qult, z50 = qz_drilled_clay(
                cu=p.get("cu", 100),
                d=self.D,
                sigmaV=sigma_v,
                A_base=a_base,
                max_unit_end_bearing=p.get("max_unit_end_bearing"),
            )
            self._last_qz_qult = qult
            self._last_qz_z50 = z50
            return qult, z50
        if st == "Elastic":
            k = qz_elastic(kb=p.get("kb", 1e5), d=self.D)
            self._last_qz_qult = k
            self._last_qz_z50 = None
            return k, None
        self._last_qz_qult = 0.01
        self._last_qz_z50 = 0.001
        return 0.01, 0.001

    def build_model(self, verbose=True):
        if verbose:
            print("=" * 50)
            print("Building axial OpenSees model...")
            print(f"  L={self.L} m, D={self.D} m")
            print(f"  segments={self.n_eles}, report nodes={self.n_nodes}")
            print("=" * 50)

        self._precompute_sigma_v_array()

        ops.wipe()
        ops.model("basic", "-ndm", 1, "-ndf", 1)

        for i in range(self.n_model_nodes):
            ops.node(i + 1, 0.0)

        self.soil_shaft_base = self.n_model_nodes + 1
        for i in range(self.n_eles):
            ops.node(self.soil_shaft_base + i, 0.0)
            ops.fix(self.soil_shaft_base + i, 1)

        self.tip_soil_node = self.soil_shaft_base + self.n_eles
        ops.node(self.tip_soil_node, 0.0)
        ops.fix(self.tip_soil_node, 1)

        self.pile_ele_tags = []
        for i in range(self.n_model_nodes - 1):
            tag = i + 1
            half_len = max(self.half_element_lengths[i], 1.0e-9)
            depth = float(self.half_element_centers[i]) if i < len(self.half_element_centers) else 0.0
            pile_mat_tag = self._build_axial_section_material(half_len, depth)
            if pile_mat_tag is None:
                k_axial = self.E * self.A / half_len
                pile_mat_tag = tag
                ops.uniaxialMaterial("Elastic", pile_mat_tag, k_axial)
            ops.element("zeroLength", tag, i + 1, i + 2, "-mat", pile_mat_tag, "-dir", 1)
            self.pile_ele_tags.append(tag)

        self.tz_base_tag = len(self.pile_ele_tags) + 100
        self.tz_ele_tags = []
        for i in range(self.n_eles):
            z = self.segment_centers[i]
            mat_tag = self.tz_base_tag + i
            tult, z50 = self._get_tz_params(z, seg_idx=i)

            if tult < 1.0e-6 or z50 is None:
                ops.uniaxialMaterial("Elastic", mat_tag, tult if z50 is None else 1.0e-3)
            elif self.spring_model_mode == 'native':
                ops.uniaxialMaterial(
                    "TzSimple1",
                    mat_tag,
                    self._native_axial_soil_type(self._get_soil_type_at(z)),
                    float(tult),
                    float(z50),
                )
            else:
                curve_type = self._get_tz_curve_type(self._get_soil_type_at(z))
                z_pts = self._build_tz_displacement_points(curve_type, z50)
                z_pts, t_pts = generate_tz_curve(tult, z50, model_type=curve_type, z_range=z_pts)
                z_all = np.concatenate([-z_pts[::-1][:-1], z_pts])
                t_all = np.concatenate([-t_pts[::-1][:-1], t_pts])
                ops.uniaxialMaterial("ElasticMultiLinear", mat_tag, "-strain", *z_all.tolist(), "-stress", *t_all.tolist())

            ele_tag = self.tz_base_tag + i
            pile_mid_node = 2 * i + 2
            ops.element("zeroLength", ele_tag, self.soil_shaft_base + i, pile_mid_node, "-mat", mat_tag, "-dir", 1)
            self.tz_ele_tags.append(ele_tag)

        self.qz_ele_tag = self.tz_base_tag + self.n_eles + 1
        qz_mat_tag = self.qz_ele_tag
        qult, q50 = self._get_qz_params()
        if qult < 1.0e-6 or q50 is None:
            ops.uniaxialMaterial("Elastic", qz_mat_tag, qult if q50 is None else 1.0e-3)
        elif self.spring_model_mode == 'native':
            ops.uniaxialMaterial(
                "QzSimple1",
                qz_mat_tag,
                self._native_axial_soil_type(self.tip_soil["type"]),
                float(qult),
                float(q50),
            )
        else:
            curve_type = self._get_qz_curve_type(self.tip_soil["type"])
            z_pts = self._build_qz_displacement_points(curve_type, q50)
            z_pts, q_pts = generate_qz_curve(qult, q50, model_type=curve_type, z_range=z_pts)
            z_all = np.concatenate([-z_pts[::-1][:-1], z_pts])
            q_all = np.concatenate([-q_pts[::-1][:-1], q_pts])
            ops.uniaxialMaterial("ElasticMultiLinear", qz_mat_tag, "-strain", *z_all.tolist(), "-stress", *q_all.tolist())

        ops.element("zeroLength", self.qz_ele_tag, self.tip_soil_node, self.n_model_nodes, "-mat", qz_mat_tag, "-dir", 1)

    def analyze(self, axial_load=0.0, axial_disp=None, n_steps=20, verbose=True):
        if not hasattr(self, "qz_ele_tag"):
            self.build_model(verbose=verbose)

        ops.reset()
        ops.setTime(0.0)
        try:
            ops.remove("loadPattern", 1)
        except Exception:
            pass
        try:
            ops.remove("timeSeries", 1)
        except Exception:
            pass

        ops.timeSeries("Linear", 1)
        ops.pattern("Plain", 1, 1)
        ops.load(1, 1.0 if axial_disp is not None else axial_load)

        ops.system("BandGeneral")
        ops.numberer("RCM")
        ops.constraints("Plain")
        ops.test("NormDispIncr", 1e-6, 500, 0)
        ops.algorithm("KrylovNewton")
        if axial_disp is not None:
            ops.integrator("DisplacementControl", 1, 1, axial_disp / n_steps)
        else:
            ops.integrator("LoadControl", 1.0 / n_steps)
        ops.analysis("Static")

        success = True
        for step in range(n_steps):
            ok = ops.analyze(1)
            if ok != 0:
                for algo in (
                    lambda: ops.algorithm("Newton"),
                    lambda: ops.algorithm("Broyden", 8),
                    lambda: ops.algorithm("BFGS"),
                    lambda: ops.algorithm("ModifiedNewton"),
                ):
                    algo()
                    ok = ops.analyze(1)
                    if ok == 0:
                        ops.algorithm("KrylovNewton")
                        break
                if ok != 0:
                    success = False
                    if verbose:
                        print(f"[WARN] step {step} failed")
                    break

        if verbose:
            print("[OK] analysis complete" if success else "[FAIL] analysis incomplete")
        self._extract_results()
        return self.results

    def _extract_results(self):
        depths = np.array(self.node_depths, dtype=float)
        disps = np.zeros(self.n_nodes, dtype=float)
        axial_forces = np.zeros(self.n_nodes, dtype=float)
        skin_frictions = np.zeros(self.n_nodes, dtype=float)
        ult_skin_frictions = np.zeros(self.n_nodes, dtype=float)

        for i in range(self.n_nodes):
            disps[i] = ops.nodeDisp(2 * i + 1, 1)

        half_forces = np.zeros(len(self.pile_ele_tags), dtype=float)
        for i, ele_tag in enumerate(self.pile_ele_tags):
            f = ops.eleForce(ele_tag)
            half_forces[i] = -f[0] if len(f) > 0 else 0.0

        axial_forces[0] = half_forces[0] if len(half_forces) else 0.0
        for i in range(1, self.n_nodes - 1):
            axial_forces[i] = 0.5 * (half_forces[2 * i - 1] + half_forces[2 * i])
        if self.n_nodes > 1:
            axial_forces[-1] = half_forces[-1]

        segment_skin = np.zeros(self.n_eles, dtype=float)
        segment_ult = np.zeros(self.n_eles, dtype=float)
        for i, ele_tag in enumerate(self.tz_ele_tags):
            try:
                f = ops.eleForce(ele_tag)
                segment_skin[i] = f[0] if len(f) > 0 else 0.0
            except Exception:
                segment_skin[i] = 0.0
            tult, _ = self._get_tz_params(self.segment_centers[i], seg_idx=i)
            segment_ult[i] = tult

        if self.n_nodes > 1:
            skin_frictions[0] = 0.5 * segment_skin[0]
            ult_skin_frictions[0] = 0.5 * segment_ult[0]
            skin_frictions[-1] = 0.5 * segment_skin[-1]
            ult_skin_frictions[-1] = 0.5 * segment_ult[-1]
        for i in range(1, self.n_nodes - 1):
            skin_frictions[i] = 0.5 * (segment_skin[i - 1] + segment_skin[i])
            ult_skin_frictions[i] = 0.5 * (segment_ult[i - 1] + segment_ult[i])

        try:
            qz_force = ops.eleForce(self.qz_ele_tag)
            end_bearing = qz_force[0] if len(qz_force) > 0 else 0.0
        except Exception:
            end_bearing = 0.0

        self.results = {
            "depths": depths,
            "displacements": disps * 1000.0,
            "axial_forces": axial_forces,
            "skin_frictions": skin_frictions,
            "ult_skin_frictions": ult_skin_frictions,
            "end_bearing": end_bearing,
            "pile_top_disp": disps[0] * 1000.0,
            "pile_tip_disp": disps[-1] * 1000.0,
            "total_skin_friction": float(np.sum(np.abs(segment_skin))),
            "debug_pile_area_m2": float(self.A),
            "debug_pile_diameter_m": float(self.D),
            "debug_pile_E_kPa": float(self.E),
            "debug_elastic_EA_kN": float(self.E * self.A),
            "debug_fiber_initial_EA_kN": getattr(self, "_debug_fiber_initial_EA_kN", None),
            "debug_tip_area_m2": self._last_qz_area,
            "debug_qz_qult_kN": getattr(self, "_last_qz_qult", None),
            "debug_qz_z50_m": getattr(self, "_last_qz_z50", None),
            "debug_section_mode": self.section_mode,
            "debug_spring_model_mode": self.spring_model_mode,
        }

    def plot_results(self, show=True):
        import matplotlib.pyplot as plt

        r = self.results
        fig, axes = plt.subplots(1, 3, figsize=(12, 8))

        axes[0].plot(r["displacements"], r["depths"], "b-", linewidth=2)
        axes[0].set_xlabel("Settlement (mm)")
        axes[0].set_ylabel("Depth (m)")
        axes[0].invert_yaxis()
        axes[0].grid(True, alpha=0.3)

        axes[1].plot(r["axial_forces"], r["depths"], "r-", linewidth=2)
        axes[1].set_xlabel("Axial Force (kN)")
        axes[1].invert_yaxis()
        axes[1].grid(True, alpha=0.3)

        axes[2].plot(r["skin_frictions"], r["depths"], "g-", linewidth=2)
        axes[2].set_xlabel("Skin Friction (kN)")
        axes[2].invert_yaxis()
        axes[2].grid(True, alpha=0.3)

        plt.tight_layout()
        if show:
            plt.show()
        return fig


OpenSeesAxialSolver = AxialPileSolver
