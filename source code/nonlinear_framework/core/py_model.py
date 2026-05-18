# -*-coding: UTF-8-*-
import numpy as np


# =============================================================================
# 1. API Method for Sand (API RP 2A)
# =============================================================================
def py_api_method_for_sand(z, gammaEff, phiDegree, b, k_modulus, is_cyclic=False):
    z = max(z, 0.01)
    phi = phiDegree * np.pi / 180.0

    alpha = phi / 2.0
    beta = np.pi / 4.0 + phi / 2.0
    K0 = 0.4
    Ka = np.tan(np.pi / 4.0 - phi / 2.0) ** 2
    Kp = np.tan(np.pi / 4.0 + phi / 2.0) ** 2

                                           
    C1 = np.tan(beta) * (Kp * np.tan(alpha) + K0 * (
        np.tan(phi) * np.sin(beta) * (1 / np.cos(alpha) + 1) - np.tan(alpha)))
    C2 = Kp - Ka
    C3 = (Kp ** 2) * (Kp + K0 * np.tan(phi)) - Ka

                                     
    pus = (C1 * z + C2 * b) * gammaEff * z
    pud = C3 * b * gammaEff * z
    pu = min(pus, pud)

            
    if is_cyclic:
        A = 0.9
    else:
        A = max(0.9, 3.0 - 0.8 * (z / b))

                                                                          
    y50 = (A * pu) / (k_modulus * z) * 0.5493
    return pu * A, y50


# =============================================================================
# 1b. Sand (Reese, Cox & Koop, 1974)
# =============================================================================

                                          
_REESE_ZB_TABLE = np.array([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0])
_REESE_AS_STATIC = np.array([2.856, 2.575, 2.254, 1.974, 1.702, 1.462, 1.254, 1.098, 0.979, 0.880])
# Figure 5.6 in the RSPile theory manual defines A/B graphically rather than
# as a tabulated formula. The original coarse 10-point B digitization tended to
# under-read the mid-depth portion (z/b ~= 1 to 4), which made the Reese sand
# curve leave the initial linear branch too early. These values are a refined
# digitization of the same figure and preserve the original end points.
_REESE_BS_STATIC = np.array([2.154, 1.822, 1.570, 1.336, 1.122, 0.941, 0.771, 0.658, 0.583, 0.500])
_REESE_BC_CYCLIC = np.array([2.154, 1.822, 1.570, 1.336, 1.122, 0.941, 0.771, 0.658, 0.583, 0.500])


def _reese_coeff_A(zb, is_cyclic=False):
    if is_cyclic:
        return 0.9
    return float(np.interp(min(zb, 5.0), _REESE_ZB_TABLE, _REESE_AS_STATIC))


def _reese_coeff_B(zb, is_cyclic=False):
    table = _REESE_BC_CYCLIC if is_cyclic else _REESE_BS_STATIC
    return float(np.interp(min(zb, 5.0), _REESE_ZB_TABLE, table))


_STIFF_CLAY_WATER_ZB_TABLE = np.array([0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0])
_STIFF_CLAY_WATER_AS = np.array([0.20, 0.23, 0.30, 0.40, 0.47, 0.52, 0.58, 0.60, 0.60])
_STIFF_CLAY_WATER_AC = np.array([0.20, 0.21, 0.23, 0.25, 0.27, 0.29, 0.30, 0.31, 0.31])


def stiff_clay_with_water_A(zb, is_cyclic=False):
    """Reese et al. (1975) Figure 5.3 A coefficient for submerged stiff clay."""
    table = _STIFF_CLAY_WATER_AC if is_cyclic else _STIFF_CLAY_WATER_AS
    zb_eff = min(max(float(zb), 0.0), _STIFF_CLAY_WATER_ZB_TABLE[-1])
    return float(np.interp(zb_eff, _STIFF_CLAY_WATER_ZB_TABLE, table))


def py_sand(z, gammaEff, phiDegree, b, kpy, is_cyclic=False):
    z = max(z, 0.01)
    phi = phiDegree * np.pi / 180.0

                     
    alpha = phi / 2.0
    beta = np.pi / 4.0 + phi / 2.0
    K0 = 0.4
    Ka = np.tan(np.pi / 4.0 - phi / 2.0) ** 2
    Kp = np.tan(np.pi / 4.0 + phi / 2.0) ** 2

    C1 = np.tan(beta) * (Kp * np.tan(alpha) + K0 * (
        np.tan(phi) * np.sin(beta) * (1 / np.cos(alpha) + 1) - np.tan(alpha)))
    C2 = Kp - Ka
    C3 = (Kp ** 2) * (Kp + K0 * np.tan(phi)) - Ka

    pus = (C1 * z + C2 * b) * gammaEff * z
    pud = C3 * b * gammaEff * z
    ps = min(pus, pud)

                                                         
    zb = z / b
    As = _reese_coeff_A(zb, is_cyclic)
    pu = As * ps
    ym = b / 60.0        
    return pu, ym


def generate_reese_sand_py_points(y_vals, z, gammaEff, phiDegree, b, kpy,
                                   is_cyclic=False):
    z = max(z, 0.01)
    phi = phiDegree * np.pi / 180.0

                       
    alpha = phi / 2.0
    beta = np.pi / 4.0 + phi / 2.0
    K0 = 0.4
    Ka = np.tan(np.pi / 4.0 - phi / 2.0) ** 2
    Kp = np.tan(np.pi / 4.0 + phi / 2.0) ** 2

    C1c = np.tan(beta) * (Kp * np.tan(alpha) + K0 * (
        np.tan(phi) * np.sin(beta) * (1 / np.cos(alpha) + 1) - np.tan(alpha)))
    C2c = Kp - Ka
    C3c = (Kp ** 2) * (Kp + K0 * np.tan(phi)) - Ka

    pus = (C1c * z + C2c * b) * gammaEff * z
    pud = C3c * b * gammaEff * z
    ps = min(pus, pud)

    zb = z / b
    As = _reese_coeff_A(zb, is_cyclic)
    Bs = _reese_coeff_B(zb, is_cyclic)

    pu = As * ps
    pm = Bs * ps
    ym = b / 60.0
    yu = 3.0 * b / 80.0
    k0 = kpy * z                 

    p_vals = np.zeros_like(y_vals, dtype=float)
    if pu < 1e-10 or k0 < 1e-10:
        return p_vals

              
    m_slope = (pu - pm) / (yu - ym) if (yu > ym and pu > pm) else 0.0

                          
    n = pm / (m_slope * ym) if (m_slope > 1e-10 and ym > 1e-10) else 1.0

                                          
    C_para = pm / (ym ** (1.0 / n)) if ym > 0 else 0.0

                                                                  
    if n > 1.001 and C_para > 1e-10 and k0 > 1e-10:
        yk = (C_para / k0) ** (n / (n - 1.0))
    elif abs(n - 1.0) <= 0.001:
        yk = C_para / k0 if k0 > 1e-10 else 0.0
    else:
        yk = 0.0
    yk = min(yk, ym)              

                               
    conditions = [
        y_vals <= 0,
        y_vals <= yk,
        y_vals <= ym,
        y_vals <= yu,
        y_vals > yu
    ]
    choices = [
        0.0,
        k0 * y_vals,
        C_para * (y_vals ** (1.0 / n)),
        pm + m_slope * (y_vals - ym),
        pu
    ]
    p_vals = np.select(conditions, choices)

    return p_vals


# =============================================================================
# 2. Soft Clay Soil (Matlock, 1970)
# =============================================================================
def py_soft_clay_soil(z, gammaEff, cu, b, eps50, J=0.5, is_cyclic=False):
    z = max(z, 0.01)

               
    p1 = (3 + (gammaEff / cu) * z + (J / b) * z) * cu * b
    p2 = 9 * cu * b
    pult = min(p1, p2)

                                  
    if is_cyclic:
        zr = 6 * b * cu / (gammaEff * b + J * cu)        
        if z < zr:
            pult = 0.72 * pult * (z / zr)

    y50 = 2.5 * eps50 * b
    return pult, y50


# =============================================================================
# 3. Submerged Stiff Clay (Reese et al., 1975)
# =============================================================================
def py_submerged_stiff_clay(z, gammaEff, cu, ca, b, eps50):
    z = max(z, 0.01)

    pc1 = 2 * ca * b + gammaEff * b * z + 2.83 * ca * z
    pc2 = 11 * cu * b
    pult = min(pc1, pc2)

    y50 = eps50 * b
    return pult, y50


# =============================================================================
# 4. Dry Stiff Clay (Welch & Reese, 1972)
# =============================================================================
def py_dry_stiff_clay(z, gammaEff, cu, ca, b, eps50, J=0.5):
    z = max(z, 0.01)

    p1 = (3 + gammaEff * z / ca + J * z / b) * ca * b
    p2 = 9 * cu * b
    pult = min(p1, p2)

    y50 = 2.5 * eps50 * b
    return pult, y50


# =============================================================================
# 5. Weak Rock (Reese, 1997)
# =============================================================================
def py_weak_rock(z, gammaEff, qu, b, krm=0.0005, Eir=None, RQD=100.0):
    z = max(z, 0.01)
    if Eir is None:
        Eir = 100 * qu

                                                         
    # RQD=0 → alpha_r=1/3, RQD=50 → alpha_r=2/3, RQD=100 → alpha_r=1.0
    if RQD is not None:
        alpha_r = 1.0 / 3.0 + (2.0 / 3.0) * (RQD / 100.0)
        alpha_r = min(max(alpha_r, 1.0 / 3.0), 1.0)
    else:
        alpha_r = 1.0
    xr = z / b
    if xr <= 3.0:
        pult = alpha_r * qu * b * (1 + 1.4 * xr)
    else:
        pult = 5.2 * alpha_r * qu * b

            
    y50 = krm * b
    return pult, y50


# =============================================================================
# 6. Elastic Soil
# =============================================================================
def py_elastic(z, kh, b):
    return kh * b


# =============================================================================
            
# =============================================================================
def generate_py_curve(pult, y50, model_type='API Method for Sand', y_range=None,
                      k_modulus=None, z=None, A=None):
    if y_range is None:
        y_range = np.linspace(0, max(20 * y50, 0.05), 200)

    p_vals = np.zeros_like(y_range)

    if model_type == 'API Method for Sand':
        # p = A*pu * tanh(k*z*y / (A*pu))
        if k_modulus is None or z is None:
            raise ValueError("API Method for Sand 需要提供 k_modulus 和 z")
        if pult > 1e-10:
            p_vals = pult * np.tanh(k_modulus * z * y_range / pult)
        else:
            p_vals = np.zeros_like(y_range)

    elif model_type == 'Soft Clay Soil':
        # Matlock (1970): p = 0.5 * pult * (y / y50)^(1/3), capped at pult
        if y50 > 0:
            mask = y_range > 0
            p_vals[mask] = np.minimum(0.5 * pult * (y_range[mask] / y50) ** (1.0 / 3.0), pult)

    elif model_type == 'Submerged Stiff Clay':
                                                                           
                                                       
                                  
                                           
        if k_modulus is not None and z is not None and k_modulus > 0 and z > 0:
            Esi = k_modulus * z                    

                                                       
                                                                             
            A_coeff = 0.35 if A is None else float(A)

                   
            Asy50 = A_coeff * y50
            y_6A = 6.0 * Asy50
            y_18A = 18.0 * Asy50

                                                          
            # => y_i = (0.5*pc/Esi)^2 * y50
            if Esi > 1e-10 and y50 > 1e-10:
                y_i = (0.5 * pult / Esi) ** 2.0 / y50
            else:
                y_i = 0.0

                    
            Ess = -0.0625 * pult / y50 if y50 > 0 else 0.0

                                           
            if y50 > 0 and y_6A > Asy50:
                p_6A = 0.5 * pult * (y_6A / y50) ** 0.5 - \
                       0.055 * pult * ((y_6A - Asy50) / Asy50) ** 1.25
            else:
                p_6A = 0.5 * pult

                                    
            p_res = p_6A + Ess * (y_18A - y_6A)
            p_res = max(p_res, 0.0)

                         
            conditions = [
                y_range <= 0,
                y_range <= y_i,
                y_range <= Asy50,
                y_range <= y_6A,
                y_range <= y_18A,
                y_range > y_18A
            ]
            
                                 
            y_diff = np.maximum(y_range - Asy50, 0)        
            p_para_seg3 = 0.5 * pult * (y_range / y50) ** 0.5
            p_offset_seg3 = 0.055 * pult * (y_diff / Asy50) ** 1.25
            
                     
            p_seg4 = p_6A + Ess * (y_range - y_6A)
            p_seg4 = np.maximum(p_seg4, 0.0)
            
            choices = [
                0.0,
                Esi * y_range,
                0.5 * pult * (y_range / y50) ** 0.5,
                p_para_seg3 - p_offset_seg3,
                p_seg4,
                p_res
            ]
            p_vals = np.select(conditions, choices)
        else:
                               
            if y50 > 0:
                mask = y_range > 0
                p_vals[mask] = np.minimum(0.5 * pult * (y_range[mask] / y50) ** 0.5, pult)

    elif model_type == 'Dry Stiff Clay':
        # Welch & Reese (1972): p = 0.5 * pult * (y / y50)^(1/4), capped at pult
        # y50 = 2.5 * eps50 * b
        if y50 > 0:
            mask = y_range > 0
            p_vals[mask] = np.minimum(0.5 * pult * (y_range[mask] / y50) ** 0.25, pult)

    elif model_type == 'Modified Stiff Clay without Free Water':
        # RSPile Section 5.13: p = min(initial_stiffness * y, Dry Stiff Clay curve)
        # k_modulus here is the "Initial Stiffness" parameter from RSPile
        if y50 > 0:
            mask = y_range > 0
            # Use exponent 0.25 which perfectly matches RSPile's behavior for Modified Stiff Clay
            p_dry = np.minimum(0.5 * pult * (y_range[mask] / y50) ** 0.25, pult)
            if k_modulus is not None and k_modulus > 0:
                p_linear = k_modulus * z * y_range[mask]
                p_vals[mask] = np.minimum(p_linear, p_dry)
            else:
                p_vals[mask] = p_dry

    elif model_type == 'Weak Rock':
                                 
                                                 
                                                              
                                                     
                                                    
                                                                                                
                                                                
        Kir = k_modulus if k_modulus is not None else 100000.0 * 100.0
        yrm = y50  # y50 = krm * b
        
        if y50 > 0 and Kir > 0 and yrm > 0:
                  
            yA = (0.5 * pult / (Kir * yrm ** 0.25)) ** (4.0 / 3.0)
            
                          
            p_curve = np.where(y_range < 16.0 * yrm, 
                              0.5 * pult * (y_range / yrm) ** 0.25, 
                              pult)
            p_linear = Kir * y_range
            
                  
            conditions = [
                y_range <= 0,
                y_range <= yA,
                y_range > yA
            ]
            choices = [
                0.0,
                p_linear,
                np.minimum(p_curve, pult)
            ]
            p_vals = np.select(conditions, choices)
        elif y50 > 0:
                  
            p_vals[y_range > 0] = np.minimum(
                np.where(y_range[y_range > 0] < 16.0 * yrm,
                        0.5 * pult * (y_range[y_range > 0] / yrm) ** 0.25,
                        pult),
                pult
            )

    elif model_type == 'elastic':
              
        p_vals = y_range * pult  # pult here is k_spring = kh*b

    else:
        raise ValueError(f"Unknown model_type: {model_type}")

    return y_range, p_vals


# =============================================================================
          
# =============================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("p-y 模型库测试")
    print("=" * 60)

    print("\n1. API Method for Sand:")
    p, y = py_api_method_for_sand(5.0, 10.0, 30.0, 1.0, 16300)
    print(f"   z=5m: pult={p:.2f} kN/m, y50={y:.6f} m")

    print("\n2. Soft Clay Soil:")
    p, y = py_soft_clay_soil(5.0, 10.0, 40.0, 1.0, 0.020)
    print(f"   z=5m: pult={p:.2f} kN/m, y50={y:.6f} m")

    print("\n3. Submerged Stiff Clay:")
    p, y = py_submerged_stiff_clay(5.0, 10.0, 100.0, 100.0, 1.0, 0.005)
    print(f"   z=5m: pult={p:.2f} kN/m, y50={y:.6f} m")

    print("\n4. Dry Stiff Clay:")
    p, y = py_dry_stiff_clay(5.0, 10.0, 100.0, 100.0, 1.0, 0.005)
    print(f"   z=5m: pult={p:.2f} kN/m, y50={y:.6f} m")

    print("\n5. Weak Rock:")
    p, y = py_weak_rock(5.0, 22.0, 500.0, 1.0)
    print(f"   z=5m: pult={p:.2f} kN/m, y50={y:.6f} m")

    print("\n6. Elastic Soil:")
    k = py_elastic(5.0, 5000.0, 1.0)
    print(f"   z=5m: k_spring={k:.2f} kN/m/m")
