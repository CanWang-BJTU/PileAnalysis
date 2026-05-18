# -*-coding: UTF-8-*-
import numpy as np


# =============================================================================
# 1. API Sand Driven Pile
# =============================================================================
def tz_sand_api(phiDegree, d, sigmaV, z, elelength, K=0.8,
                limit_fmax=True, max_unit_skin_friction=None):
    sigmaV = sigmaV if sigmaV > 0 else 0.01

                              
    delta = (phiDegree - 5.0) * np.pi / 180.0

                 
    tau_ult_theory = K * sigmaV * np.tan(delta)
    
                                   
    # RSPile/API published guideline table for cohesionless siliceous soils.
    # Values beyond the listed points are linearly interpolated between the
    # published anchors and clamped outside the range.
    phi_tab = [15, 20, 25, 30, 35]
    fmax_tab = [47.8, 67.0, 81.3, 95.7, 114.8]
    if phiDegree <= phi_tab[0]:
        f_max = fmax_tab[0]
    elif phiDegree >= phi_tab[-1]:
        f_max = fmax_tab[-1]
    else:
        f_max = np.interp(phiDegree, phi_tab, fmax_tab)
        
    tau_ult_limited = min(tau_ult_theory, f_max)

    # RSPile exposes Maximum Unit Skin Friction as the user-controlled cap.
    # When the user provides that value, it should govern instead of an
    # internal hard cap from the recommendation table.
    tau_ult_base = tau_ult_theory if not limit_fmax else tau_ult_limited
    if max_unit_skin_friction is not None:
        tau_ult_base = min(tau_ult_theory, max_unit_skin_friction)

    tult = tau_ult_base * (np.pi * d * elelength)
    
                                                               
                                                             
                              
    z50 = 0.00254 / 2.0
        
    return tult, z50


# =============================================================================
# 2. API Clay Driven Pile
# =============================================================================
def tz_clay_api(cu, d, sigmaV, z, elelength, max_unit_skin_friction=None):
    sigmaV = sigmaV if sigmaV > 0 else 0.01
    psi = cu / sigmaV

                      
    if psi <= 1.0:
        alpha = 0.5 * (psi ** -0.5)
    else:
        alpha = 0.5 * (psi ** -0.25)
    alpha = min(alpha, 1.0)

              
    tau_ult = alpha * cu
    if max_unit_skin_friction is not None:
        tau_ult = min(tau_ult, max_unit_skin_friction)
    tult = tau_ult * (np.pi * d * elelength)

                             
    z50 = 0.0031 * d
    return tult, z50


# =============================================================================
# 3. Drilled Shaft Sand (Kulhawy, 1991 / O'Neill & Reese, 1999)
# =============================================================================
def tz_drilled_sand(phiDegree, d, sigmaV, z, elelength,
                    max_unit_skin_friction=None):
    sigmaV = sigmaV if sigmaV > 0 else 0.01
    if max_unit_skin_friction is not None:
        tult = max_unit_skin_friction * (np.pi * d * elelength)
        z50 = 0.0027 * d
        return tult, z50

                               
    phi = phiDegree * np.pi / 180.0
    K0 = 1.0 - np.sin(phi)

                             
    delta = phi

               
                                                              
    tau_ult = max_unit_skin_friction if max_unit_skin_friction is not None else K0 * sigmaV * np.tan(delta)

                     
                                 
    beta = K0 * np.tan(phi)
    if max_unit_skin_friction is None:
        tau_ult = min(tau_ult, 200.0)            
    tult = tau_ult * (np.pi * d * elelength)

                                            
    z50 = 0.0027 * d
    return tult, z50


# =============================================================================
# 4. Drilled Shaft Clay (O'Neill & Reese, 1999)
# =============================================================================
def tz_drilled_clay(cu, d, sigmaV, z, elelength,
                    max_unit_skin_friction=None):
    sigmaV = sigmaV if sigmaV > 0 else 0.01
    if max_unit_skin_friction is not None:
        tult = max_unit_skin_friction * (np.pi * d * elelength)
        z50 = 0.0010 * d
        return tult, z50

                                
                                   
                                       
    Pa = 101.325             
    cu_ratio = cu / Pa

    if cu_ratio <= 1.5:
        alpha = 0.55
    elif cu_ratio <= 2.5:
        alpha = 0.55 - 0.1 * (cu_ratio - 1.5)
    else:
        alpha = 0.45

                        
    if z < 1.5:
        alpha = 0.0            
    elif z < 1.5 + d:
        alpha *= (z - 1.5) / d       

    tau_ult = max_unit_skin_friction if max_unit_skin_friction is not None else alpha * cu
    tult = tau_ult * (np.pi * d * elelength)

                                            
    z50 = 0.0010 * d
    return tult, z50


# =============================================================================
# 5. Elastic Soil
# =============================================================================
def tz_elastic(ks, d, elelength):
    return ks * np.pi * d * elelength


# =============================================================================
            
# =============================================================================
def generate_tz_curve(tult, z50, model_type='api_clay', z_range=None):
    if z_range is None:
        z_range = np.linspace(0, max(20 * z50, 0.02), 200)

    t_vals = np.zeros_like(z_range)

    if model_type == 'api_sand':
        # API sand / Mosher (1984): linear-perfectly-plastic.
        # z50 is stored as half of the 0.1 inch yield displacement so that
        # z_peak = 2*z50 = 0.00254 m in the strict API sand interpretation.
        z_peak = max(2.0 * z50, 1.0e-6)
        t_vals = np.where(z_range <= z_peak, tult * (z_range / z_peak), tult)

    elif model_type == 'api_clay':
                                       
        # z/zc:      0.0   0.0016  0.0031  0.0057  0.0080  0.0100  0.02  inf
        # t/tult:    0.0   0.30    0.50    0.75    0.90    1.00    0.90  0.90
                                                                        
        zc = z50 / 0.0031 if z50 > 0 else 0.01
        z_ratio_pts = np.array([0.0, 0.0016, 0.0031, 0.0057, 0.0080, 0.0100, 0.02, 1.0])
        t_ratio_pts = np.array([0.0, 0.30,   0.50,   0.75,   0.90,   1.00,   0.90, 0.90])

                 
        z_ratio = z_range / zc if zc > 0 else np.zeros_like(z_range)
        t_vals = np.interp(z_ratio, z_ratio_pts, t_ratio_pts) * tult

    elif model_type == 'drilled_clay':
        x50 = 0.0010
        d_equiv = z50 / x50 if z50 > 0 else 1.0
        z_ratio = z_range / d_equiv if d_equiv > 0 else np.zeros_like(z_range)
        z_ratio_pts = np.array([0.0, 0.0005, 0.0010, 0.0020, 0.0040,
                                0.0060, 0.0080, 0.0100, 0.0150, 0.0200])
        t_ratio_pts = np.array([0.0, 0.22,   0.46,   0.71,   0.885,
                                0.945,  0.960,  0.960,  0.905,  0.82])
        t_vals = np.interp(z_ratio, z_ratio_pts, t_ratio_pts) * tult

    elif model_type == 'drilled_sand':
        x50 = 0.0027
        d_equiv = z50 / x50 if z50 > 0 else 1.0
        z_ratio = z_range / d_equiv if d_equiv > 0 else np.zeros_like(z_range)
        z_ratio_pts = np.array([0.0, 0.0005, 0.0010, 0.0020, 0.0040,
                                0.0060, 0.0080, 0.0100, 0.0120, 0.0150, 0.0200])
        t_ratio_pts = np.array([0.0, 0.12,   0.24,   0.44,   0.70,
                                0.82,   0.90,   0.96,   0.99,   1.00,   0.96])
        t_vals = np.interp(z_ratio, z_ratio_pts, t_ratio_pts) * tult

    elif model_type == 'hyperbolic':
                                                     
        if z50 > 0:
            t_vals = tult * (z_range / z50) / (1.0 + z_range / z50)

    return z_range, t_vals


# =============================================================================
          
# =============================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("t-z 模型库测试")
    print("=" * 60)

    print("\n1. API Sand Driven:")
    t, z = tz_sand_api(35, 1.0, 19.0, 10.0, 1.0)
    print(f"   z=10m: tult={t:.2f} kN, z50={z:.6f} m")

    print("\n2. API Clay Driven:")
    t, z = tz_clay_api(50, 1.0, 19.0, 10.0, 1.0)
    print(f"   z=10m: tult={t:.2f} kN, z50={z:.6f} m")

    print("\n3. Drilled Shaft Sand:")
    t, z = tz_drilled_sand(35, 1.0, 19.0, 10.0, 1.0)
    print(f"   z=10m: tult={t:.2f} kN, z50={z:.6f} m")

    print("\n4. Drilled Shaft Clay:")
    t, z = tz_drilled_clay(50, 1.0, 19.0, 10.0, 1.0)
    print(f"   z=10m: tult={t:.2f} kN, z50={z:.6f} m")

    print("\n5. Elastic:")
    k = tz_elastic(5000, 1.0, 1.0)
    print(f"   k_spring={k:.2f} kN/m")
