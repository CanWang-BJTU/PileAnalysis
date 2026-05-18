# -*-coding: UTF-8-*-
import numpy as np


# =============================================================================
# 1. API Sand (Meyerhof, 1976)
# =============================================================================
def qz_sand_api(phiDegree, d, sigmaV, z=None, Nq=None, A_base=None,
                max_unit_end_bearing=None):
    sigmaV = max(sigmaV, 0.01)

                           
    if Nq is None:
        # RSPile/API published guideline table for cohesionless siliceous soils.
        phi_table = [15, 20, 25, 30, 35]
        Nq_table = [8, 12, 20, 40, 50]
        if phiDegree <= phi_table[0]:
            Nq = Nq_table[0]
        elif phiDegree >= phi_table[-1]:
            Nq = Nq_table[-1]
        else:
            Nq = np.interp(phiDegree, phi_table, Nq_table)

             
    q = sigmaV * Nq

                      
    area = A_base if A_base is not None else (np.pi * (d ** 2) / 4.0)

            
    qult = q * area

                              
    qlim_table = {15: 1900, 20: 2900, 25: 4800, 30: 9600, 35: 12000}  # kPa
             
    phi_keys = sorted(qlim_table.keys())
    qlim_vals = [qlim_table[k] for k in phi_keys]
    if phiDegree <= phi_keys[0]:
        qlim = qlim_vals[0]
    elif phiDegree >= phi_keys[-1]:
        qlim = qlim_vals[-1]
    else:
        qlim = np.interp(phiDegree, phi_keys, qlim_vals)

    qult_base = min(qult, qlim * area)
    if max_unit_end_bearing is not None:
        qult_base = min(q * area, max_unit_end_bearing * area)
    qult = qult_base

                                          
                                                 
    z50 = 0.013 * d
    return qult, z50


# =============================================================================
# 2. API Clay
# =============================================================================
def qz_clay_api(cu, d, A_base=None, max_unit_end_bearing=None):
    q = 9 * cu
    area = A_base if A_base is not None else (np.pi * (d ** 2) / 4.0)
    if max_unit_end_bearing is not None:
        q = min(q, max_unit_end_bearing)
    qult = q * area

                                
    z50 = 0.013 * d
    return qult, z50


# =============================================================================
                                                            
# =============================================================================
def qz_drilled_sand(phiDegree, d, sigmaV, z=None, G=None,
                    A_base=None, max_unit_end_bearing=None):
    sigmaV = max(sigmaV, 0.01)
    area = A_base if A_base is not None else (np.pi * d ** 2 / 4.0)
    if max_unit_end_bearing is not None:
        qult = max_unit_end_bearing * area
        z50 = 0.022 * d
        return qult, z50
    phi = phiDegree * np.pi / 180.0

                 
    if G is None:
        G = 200 * sigmaV        

    k0 = 1 - np.sin(phi)

          
    Ir = G / (sigmaV * np.tan(phi)) if np.tan(phi) > 1e-10 else 1.0

                     
    Nq = (1 + 2 * k0) * (1.0 / (3.0 - np.sin(phi))) * \
         np.exp(np.pi / 2.0 - phi) * \
         (np.tan(np.pi / 4.0 + phi / 2.0)) ** 2 * \
         Ir ** ((4 * np.sin(phi)) / (3.0 * (1 + np.sin(phi))))

    qu = max_unit_end_bearing if max_unit_end_bearing is not None else Nq * sigmaV
    qult = qu * area

                                               
    z50 = 0.022 * d
    return qult, z50


# =============================================================================
# 4. Drilled Shaft Clay (O'Neill & Reese, 1999)
# =============================================================================
def qz_drilled_clay(cu, d, sigmaV=None, z=None,
                    A_base=None, max_unit_end_bearing=None):
    area = A_base if A_base is not None else (np.pi * (d ** 2) / 4.0)
    if max_unit_end_bearing is not None:
        qult = max_unit_end_bearing * area
        z50 = 0.006 * d
        return qult, z50
                          
    Nc = 9.0
    q = Nc * cu
    qult = q * area

                                               
    z50 = 0.006 * d
    return qult, z50


# =============================================================================
# 5. Elastic Soil
# =============================================================================
def qz_elastic(kb, d):
    return kb * np.pi * d ** 2 / 4.0


# =============================================================================
            
# =============================================================================
def generate_qz_curve(qult, z50, model_type='api', z_range=None):
    if z_range is None:
        z_range = np.linspace(0, max(20 * z50, 0.05), 200)

    q_vals = np.zeros_like(z_range)

    if model_type == 'api':
                                    
        # z/zc:     0.0   0.002  0.013  0.042  0.073  0.100  inf
                                                                       
        zc = z50 / 0.013 if z50 > 0 else 0.01
        z_ratio_pts = np.array([0.0, 0.002, 0.013, 0.042, 0.073, 0.100, 1.0])
        q_ratio_pts = np.array([0.0, 0.25,  0.50,  0.75,  0.90,  1.00,  1.00])

                 
        z_ratio = z_range / zc if zc > 0 else np.zeros_like(z_range)
        q_vals = np.interp(z_ratio, z_ratio_pts, q_ratio_pts) * qult

    elif model_type == 'drilled_clay':
        x50 = 0.006
        d_equiv = z50 / x50 if z50 > 0 else 1.0
        z_ratio = z_range / d_equiv if d_equiv > 0 else np.zeros_like(z_range)
        z_ratio_pts = np.array([0.0, 0.002, 0.004, 0.006, 0.010, 0.020, 0.035, 0.060, 0.100])
        q_ratio_pts = np.array([0.0, 0.20, 0.38, 0.52, 0.70, 0.88, 0.95, 0.98, 0.99])
        q_vals = np.interp(z_ratio, z_ratio_pts, q_ratio_pts) * qult

    elif model_type == 'drilled_sand':
        x50 = 0.028
        d_equiv = z50 / x50 if z50 > 0 else 1.0
        z_ratio = z_range / d_equiv if d_equiv > 0 else np.zeros_like(z_range)
        z_ratio_pts = np.array([0.0, 0.010, 0.020, 0.040, 0.060, 0.080, 0.100, 0.110])
        q_ratio_pts = np.array([0.0, 0.18, 0.35, 0.70, 1.00, 1.25, 1.45, 1.50])
        q_vals = np.interp(z_ratio, z_ratio_pts, q_ratio_pts) * qult

    elif model_type == 'vijayvergiya':
        # Vijayvergiya (1977): q = qult * (z/zc)^(1/3), capped at qult
        zc = 0.05 * z50 / 0.00625               
        if zc <= 0:
            zc = 0.01
        mask = z_range > 0
        q_vals[mask] = np.minimum(qult * (z_range[mask] / zc) ** (1.0 / 3.0), qult)

    return z_range, q_vals


# =============================================================================
          
# =============================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("q-z 模型库测试")
    print("=" * 60)

    print("\n1. API Sand:")
    q, z = qz_sand_api(35, 1.0, sigmaV=19.0*15.0)  # sigmaV = gamma*z
    print(f"   z=15m: qult={q:.2f} kN, z50={z:.6f} m")

    print("\n2. API Clay:")
    q, z = qz_clay_api(100, 1.0)
    print(f"   qult={q:.2f} kN, z50={z:.6f} m")

    print("\n3. Drilled Shaft Sand:")
    q, z = qz_drilled_sand(35, 1.0, sigmaV=19.0*15.0)
    print(f"   z=15m: qult={q:.2f} kN, z50={z:.6f} m")

    print("\n4. Drilled Shaft Clay:")
    q, z = qz_drilled_clay(100, 1.0)
    print(f"   qult={q:.2f} kN, z50={z:.6f} m")

    print("\n5. Elastic:")
    k = qz_elastic(5000, 1.0)
    print(f"   k_spring={k:.2f} kN/m")
