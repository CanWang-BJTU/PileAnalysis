# -*- coding: utf-8 -*-

import math
from typing import Dict


class AxialParamProcessor:
    """Normalize collected axial payload to solver-ready inputs.

    This follows the validation/combined strict-style defaults where applicable.
    """

    @staticmethod
    def normalize(payload: Dict) -> Dict:
        out = dict(payload)
        pile_shape = str(out.get("pile_shape", "Circle"))
        pile_diameter = float(out.get("pile_diameter_m", 0.0))
        pile_thickness = float(out.get("pile_thickness_m", 0.0))

        if pile_shape == "Pipe":
            pile_tip_area = 0.0
        else:
            pile_tip_area = math.pi * pile_diameter * pile_diameter / 4.0

        layers = []
        for row in out.get("layers", []):
            soil_type = str(row.get("soil_type", "API Sand"))
            params = dict(row.get("params", {}))
            if soil_type == "API Sand":
                params.setdefault("limit_fmax", False)
                params.setdefault("z50_multiplier", 1.0)
            layer = dict(row)
            layer["params"] = params
            layers.append(layer)
        out["layers"] = layers

        tip_type = None
        tip_params: Dict = {}
        pile_bottom_z = float(out.get("pile_bottom_z_m", -float(out.get("pile_length_m", 0.0))))
        pile_length = abs(pile_bottom_z) if pile_bottom_z < 0.0 else float(out.get("pile_length_m", 0.0))
        for layer in layers:
            z_top = float(layer.get("z_top", 0.0))
            z_bottom = float(layer.get("z_bottom", 0.0))
            if z_top - 1.0e-8 <= pile_length <= z_bottom + 1.0e-8:
                tip_type = str(layer.get("soil_type", "API Sand"))
                tip_params = dict(layer.get("params", {}))
                break
        if tip_type is None and layers:
            tip_type = str(layers[-1].get("soil_type", "API Sand"))
            tip_params = dict(layers[-1].get("params", {}))
        if tip_type is None:
            tip_type = "API Sand"
        tip_params["A_base"] = pile_tip_area
        tip_params["A_tip"] = pile_tip_area
        if tip_type == "API Sand":
            tip_params.setdefault("Nq", 40.0)
        out["tip_params"] = tip_params
        out["tip_type"] = tip_type
        return out
