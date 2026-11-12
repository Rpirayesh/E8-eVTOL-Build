"""Small 3-D frame finite-element solver (Euler-Bernoulli, 6 DOF per node).

Used for the global airframe model (booms, spars, fuselage beam, lumped masses):
static solution with inertia relief and free-free / constrained modal analysis.
Verified against closed-form results and CalculiX in tools/fea/validation.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


@dataclass
class Section:
    A: float
    Iy: float
    Iz: float
    J: float
    E: float
    G: float
    rho: float
    c: float = 0.0          # extreme-fibre distance for bending stress
    name: str = ""

    @classmethod
    def pipe(cls, ro, ri, E, G, rho, name=""):
        A = np.pi * (ro**2 - ri**2)
        I = np.pi / 4 * (ro**4 - ri**4)
        return cls(A, I, I, 2 * I, E, G, rho, ro, name)


@dataclass
class Frame:
    nodes: list = field(default_factory=list)      # xyz
    elems: list = field(default_factory=list)      # (n1, n2, Section, vref, tag)
    masses: dict = field(default_factory=dict)     # node -> (m, Ixx, Iyy, Izz)

    def node(self, xyz) -> int:
        self.nodes.append(np.asarray(xyz, float))
        return len(self.nodes) - 1

    def find(self, xyz, tol=1e-6):
        for i, p in enumerate(self.nodes):
            if np.linalg.norm(p - np.asarray(xyz)) < tol:
                return i
        return self.node(xyz)

    def beam(self, a: int, b: int, sec: Section, n: int = 1, vref=(0, 0, 1), tag=""):
        """Add a beam from node a to b, subdivided into n elements."""
        pa, pb = self.nodes[a], self.nodes[b]
        prev = a
        for k in range(1, n + 1):
            nxt = b if k == n else self.node(pa + (pb - pa) * k / n)
            self.elems.append((prev, nxt, sec, np.asarray(vref, float), tag))
            prev = nxt

    def add_mass(self, n: int, m: float, I=(0.0, 0.0, 0.0)):
        old = self.masses.get(n, (0.0, 0.0, 0.0, 0.0))
        self.masses[n] = (old[0] + m, old[1] + I[0], old[2] + I[1], old[3] + I[2])

    # ------------------------------------------------------------------ element matrices
    @staticmethod
    def _T(p1, p2, vref):
        ex = (p2 - p1) / np.linalg.norm(p2 - p1)
        v = vref if abs(np.dot(vref, ex)) < 0.99 else np.array([0, 1.0, 0])
        ez = v - np.dot(v, ex) * ex
        ez /= np.linalg.norm(ez)
        ey = np.cross(ez, ex)
        R = np.vstack([ex, ey, ez])
        T = np.zeros((12, 12))
        for i in range(4):
            T[3 * i:3 * i + 3, 3 * i:3 * i + 3] = R
        return T, R

    @staticmethod
    def _k_local(L, s: Section):
        E, G, A, Iy, Iz, J = s.E, s.G, s.A, s.Iy, s.Iz, s.J
        k = np.zeros((12, 12))
        a = E * A / L
        k[0, 0] = k[6, 6] = a; k[0, 6] = k[6, 0] = -a
        t = G * J / L
        k[3, 3] = k[9, 9] = t; k[3, 9] = k[9, 3] = -t
        for (I, i1, i2, sgn) in ((Iz, 1, 5, 1), (Iy, 2, 4, -1)):
            c1, c2, c3, c4 = 12 * E * I / L**3, 6 * E * I / L**2, 4 * E * I / L, 2 * E * I / L
            j1, j2 = i1 + 6, i2 + 6
            k[i1, i1] = k[j1, j1] = c1; k[i1, j1] = k[j1, i1] = -c1
            k[i1, i2] = k[i2, i1] = sgn * c2; k[i1, j2] = k[j2, i1] = sgn * c2
            k[j1, i2] = k[i2, j1] = -sgn * c2; k[j1, j2] = k[j2, j1] = -sgn * c2
            k[i2, i2] = k[j2, j2] = c3; k[i2, j2] = k[j2, i2] = c4
        return k

    @staticmethod
    def _m_local(L, s: Section):
        """Lumped translational mass + small rotary inertia (adequate for low modes)."""
        m = s.rho * s.A * L
        M = np.zeros((12, 12))
        for i in (0, 1, 2, 6, 7, 8):
            M[i, i] = m / 2
        rot = m / 2 * (L**2 / 12 + (s.Iy + s.Iz) / s.A / 2)
        for i in (3, 4, 5, 9, 10, 11):
            M[i, i] = rot * (2.0 if i in (3, 9) else 1.0) * 0.5
        return M

    def assemble(self, with_mass=True):
        n = len(self.nodes) * 6
        K = sp.lil_matrix((n, n))
        M = sp.lil_matrix((n, n))
        for (a, b, s, vref, _) in self.elems:
            p1, p2 = self.nodes[a], self.nodes[b]
            L = np.linalg.norm(p2 - p1)
            T, _ = self._T(p1, p2, vref)
            ke = T.T @ self._k_local(L, s) @ T
            me = T.T @ self._m_local(L, s) @ T
            dofs = np.r_[6 * a:6 * a + 6, 6 * b:6 * b + 6]
            for i in range(12):
                for j in range(12):
                    if ke[i, j]:
                        K[dofs[i], dofs[j]] += ke[i, j]
                    if with_mass and me[i, j]:
                        M[dofs[i], dofs[j]] += me[i, j]
        for nd, (m, Ix, Iy, Iz) in self.masses.items():
            for k in range(3):
                M[6 * nd + k, 6 * nd + k] += m
            for k, I in enumerate((Ix, Iy, Iz)):
                M[6 * nd + 3 + k, 6 * nd + 3 + k] += I
        return K.tocsr(), M.tocsr()

    # ------------------------------------------------------------------ rigid-body properties
    def mass_properties(self):
        K, M = self.assemble()
        n = len(self.nodes)
        mt = 0.0
        mx = np.zeros(3)
        Md = M.diagonal()
        for i in range(n):
            m = Md[6 * i]
            mt += m
            mx += m * self.nodes[i]
        cg = mx / mt
        I = np.zeros((3, 3))
        for i in range(n):
            m = Md[6 * i]
            r = self.nodes[i] - cg
            I += m * (np.dot(r, r) * np.eye(3) - np.outer(r, r))
            I += np.diag(Md[6 * i + 3:6 * i + 6])
        return mt, cg, I, M

    # ------------------------------------------------------------------ solutions
    def solve_inertia_relief(self, F: np.ndarray, support: int):
        """Static response to applied loads F (n_dof) balanced by rigid-body inertia.

        The rigid-body accelerations that equilibrate F are computed from the mass
        matrix; the resulting D'Alembert loads are added and the structure is held
        by a single fully fixed node (reactions ~ 0 when balanced)."""
        K, M = self.assemble()
        mt, cg, I, M = self.mass_properties()
        n = len(self.nodes)
        Ftot, Mtot = np.zeros(3), np.zeros(3)
        for i in range(n):
            f = F[6 * i:6 * i + 3]
            Ftot += f
            Mtot += np.cross(self.nodes[i] - cg, f) + F[6 * i + 3:6 * i + 6]
        a = Ftot / mt
        alpha = np.linalg.solve(I, Mtot)
        Md = M.diagonal()
        Fi = F.copy()
        for i in range(n):
            r = self.nodes[i] - cg
            acc = a + np.cross(alpha, r)
            Fi[6 * i:6 * i + 3] -= Md[6 * i] * acc
            Fi[6 * i + 3:6 * i + 6] -= Md[6 * i + 3:6 * i + 6] * alpha
        fixed = np.arange(6 * support, 6 * support + 6)
        free = np.setdiff1d(np.arange(6 * n), fixed)
        u = np.zeros(6 * n)
        u[free] = spla.spsolve(K[free][:, free].tocsc(), Fi[free])
        R = K @ u - Fi
        return u, dict(accel=a, alpha=alpha, reaction=R[fixed], cg=cg, mass=mt)

    def solve_static(self, F, fixed_dofs):
        K, _ = self.assemble(with_mass=False)
        n = K.shape[0]
        free = np.setdiff1d(np.arange(n), fixed_dofs)
        u = np.zeros(n)
        u[free] = spla.spsolve(K[free][:, free].tocsc(), F[free])
        return u, K @ u - F

    def modes(self, n_modes=12, fixed_dofs=()):
        """Natural frequencies (Hz) by shift-invert Lanczos; massless DOFs are allowed."""
        K, M = self.assemble()
        n = K.shape[0]
        free = np.setdiff1d(np.arange(n), np.asarray(fixed_dofs, int))
        Kf, Mf = K[free][:, free].tocsc(), M[free][:, free].tocsc()
        sigma = -(2 * np.pi * 0.5) ** 2
        w2, V = spla.eigsh(Kf, k=n_modes + 6, M=Mf, sigma=sigma, which="LM")
        order = np.argsort(w2)
        w2, V = w2[order], V[:, order]
        f = np.sqrt(np.clip(w2, 0, None)) / (2 * np.pi)
        full = np.zeros((n, V.shape[1]))
        full[free] = V
        return f, full

    def element_forces(self, u):
        """Local end forces per element: N, Vy, Vz, T, My, Mz at both ends."""
        out = []
        for (a, b, s, vref, tag) in self.elems:
            p1, p2 = self.nodes[a], self.nodes[b]
            L = np.linalg.norm(p2 - p1)
            T, _ = self._T(p1, p2, vref)
            ue = u[np.r_[6 * a:6 * a + 6, 6 * b:6 * b + 6]]
            fl = self._k_local(L, s) @ (T @ ue)
            out.append(fl)
        return out

    def stresses(self, u):
        """Max combined axial + bending stress and torsional shear per element (Pa)."""
        res = []
        for fl, (a, b, s, vref, tag) in zip(self.element_forces(u), self.elems):
            N = max(abs(fl[0]), abs(fl[6]))
            My = max(abs(fl[4]), abs(fl[10]))
            Mz = max(abs(fl[5]), abs(fl[11]))
            Tq = max(abs(fl[3]), abs(fl[9]))
            Mb = np.hypot(My, Mz)
            sig = N / s.A + Mb * s.c / max(s.Iy, s.Iz)
            tau = Tq * s.c / s.J if s.J else 0.0
            res.append(dict(tag=tag, n1=a, n2=b, N=N, M=Mb, T=Tq, sigma=sig, tau=tau, sec=s.name))
        return res
