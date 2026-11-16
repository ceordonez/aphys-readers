"""Practical salinity from conductivity (PSS-78), and density (EOS-80, surface).

UNESCO (1983), Algorithms for computation of fundamental properties of
seawater, UNESCO Technical Papers in Marine Science 44, pp. 6-12. Valid for
2-42 psu, -2-35 °C, 0-10000 dbar. Temperatures are ITS-90 and converted to
IPTS-68 (x 1.00024) for the formula, as Sea-Bird and TEOS-10 do.
"""

import numpy as np

C_STANDARD_MSCM = 42.914  # conductivity of standard seawater, S = 35, 15 °C, 0 dbar
A = (0.0080, -0.1692, 25.3851, 14.0941, -7.0261, 2.7081)
B = (0.0005, -0.0056, -0.0066, -0.0375, 0.0636, -0.0144)
K = 0.0162
C_RT = (0.6766097, 2.00564e-2, 1.104259e-4, -6.9698e-7, 1.0031e-9)
D = (3.426e-2, 4.464e-4, 4.215e-1, -3.107e-3)
E = (2.070e-5, -6.370e-10, 3.989e-15)


def salinity_pss78(cond_mscm, temp_c, press_dbar):
    """Practical salinity (psu) from conductivity (mS/cm), ITS-90 temperature (°C) and sea pressure (dbar)."""
    c = np.asarray(cond_mscm, dtype=float)
    t = np.asarray(temp_c, dtype=float) * 1.00024
    p = np.asarray(press_dbar, dtype=float)
    r = c / C_STANDARD_MSCM
    rt = C_RT[0] + t * (C_RT[1] + t * (C_RT[2] + t * (C_RT[3] + t * C_RT[4])))
    rp = 1 + p * (E[0] + p * (E[1] + p * E[2])) / (1 + D[0] * t + D[1] * t**2 + (D[2] + D[3] * t) * r)
    ratio = np.clip(r / (rp * rt), 0, None)
    root = np.sqrt(ratio)
    powers = [root**k for k in range(6)]
    s = sum(a * x for a, x in zip(A, powers))
    s += (t - 15) / (1 + K * (t - 15)) * sum(b * x for b, x in zip(B, powers))
    return s


def sigma_t(salinity, temp_c):
    """Density at the surface minus 1000 (kg/m3), EOS-80 one-atmosphere (UNESCO 1981, Millero and Poisson).

    ITS-90 temperature, converted to IPTS-68 for the formula. Without the
    pressure term: for stratification over a few tens of metres.
    """
    s = np.asarray(salinity, dtype=float)
    t = np.asarray(temp_c, dtype=float) * 1.00024
    rho_w = 999.842594 + t * (6.793952e-2 + t * (-9.095290e-3 + t * (1.001685e-4 + t * (-1.120083e-6 + t * 6.536332e-9))))
    a = 8.24493e-1 + t * (-4.0899e-3 + t * (7.6438e-5 + t * (-8.2467e-7 + t * 5.3875e-9)))
    b = -5.72466e-3 + t * (1.0227e-4 - 1.6546e-6 * t)
    return rho_w + a * s + b * s**1.5 + 4.8314e-4 * s**2 - 1000.0
