"""Array geometry, steering vectors and attitude rotations (body frame FRD, earth NED)."""
import numpy as np
from .params import C, spacing_m


ARM_DEG = np.array([0.0, 120.0, 240.0])


def positions(r=None):
    """Y array in the body x-y plane (metres): element 0 = centre (reference/bypass
    element), elements 1-3 at radius r, 120 deg apart, element 1 toward the nose."""
    r = spacing_m() if r is None else r
    a = np.radians(ARM_DEG)
    return np.vstack([[0.0, 0.0, 0.0], np.c_[r * np.cos(a), r * np.sin(a), np.zeros(3)]])


def positions_square(d):
    h = d / 2.0
    return np.array([[-h, -h, 0.0], [h, -h, 0.0], [-h, h, 0.0], [h, h, 0.0]])


def positions_ula(d):
    return np.c_[(np.arange(4) - 1.5) * d, np.zeros(4), np.zeros(4)]


def unit(az_deg, el_deg):
    """Direction (toward the source) from azimuth (from x/nose, toward y/right) and
    elevation (positive UP). Body/earth frames are x-fwd/north, y-right/east, z-down."""
    az, el = np.radians(az_deg), np.radians(el_deg)
    return np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), -np.sin(el)])


def steer(k, f_hz, pos=None, cal=None):
    """Plane-wave steering vector for unit direction k (body frame)."""
    pos = positions() if pos is None else pos
    a = np.exp(1j * 2 * np.pi * f_hz / C * (pos @ k))
    return a if cal is None else a * cal


# ------------------------------------------------------------ rotations -----
def rot_z(deg):
    t = np.radians(deg); c, s = np.cos(t), np.sin(t)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rot_x(deg):
    t = np.radians(deg); c, s = np.cos(t), np.sin(t)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(deg):
    t = np.radians(deg); c, s = np.cos(t), np.sin(t)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def dcm_body_to_earth(yaw, pitch, roll):
    """C_eb such that k_earth = C_eb @ k_body (aerospace 3-2-1 Euler, degrees)."""
    return rot_z(yaw) @ rot_y(pitch) @ rot_x(roll)


def body_dir(k_earth, yaw, pitch, roll):
    return dcm_body_to_earth(yaw, pitch, roll).T @ k_earth
