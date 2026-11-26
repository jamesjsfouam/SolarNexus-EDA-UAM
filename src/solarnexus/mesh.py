"""Red mesh DC entre pabellones (grafo dirigido) con precios sombra nodales.

Cada intervalo se resuelve un MILP:

    min  Σ_a c_a·f_a + Σ_a s_a·y_a + c_ciclado·Σ_i central_i
    s.a. Σ_{a entra a i} (1 - p_a)·f_a - Σ_{a sale de i} f_a + central_i - vertido_i = carga_i - gen_i   (λ_i)
         0 <= f_a <= cap_a·y_a,   y_a ∈ {0, 1}   (switch de estado sólido cerrado / abierto)

donde central_i es energía que llega al nodo pasando por el inversor central / batería
principal (costo de ciclado) y vertido_i es excedente que no se usa en la malla.

Los precios sombra λ_i se obtienen fijando los switches en la solución entera y
resolviendo el PL resultante: son las variables duales de las restricciones de balance.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp


def conviene_transferir(costo_transferencia: float, costo_ciclado: float) -> bool:
    """Regla de enrutamiento: Costo_transferencia(i→j) < Costo_ciclado(central)."""
    return costo_transferencia < costo_ciclado


@dataclass(frozen=True)
class Nodo:
    nombre: str
    generacion: float  # kWh DC disponibles en el intervalo
    carga: float       # kWh demandados en el intervalo


@dataclass(frozen=True)
class Enlace:
    origen: str
    destino: str
    capacidad: float               # kWh máximos por intervalo
    costo_transferencia: float = 0.0  # costo por kWh transferido (desgaste, operación)
    perdida: float = 0.0           # fracción perdida en el enlace DC [0, 1)
    costo_switch: float = 0.0      # costo fijo por cerrar el switch en el intervalo


@dataclass(frozen=True)
class ResultadoMesh:
    flujos: dict[tuple[str, str], float]
    switches_cerrados: list[tuple[str, str]]
    desde_central: dict[str, float]
    vertido: dict[str, float]
    precios_sombra: dict[str, float]
    costo_total: float


class RedMeshDC:
    def __init__(self, nodos: list[Nodo], enlaces: list[Enlace], costo_ciclado: float) -> None:
        nombres = [n.nombre for n in nodos]
        if len(set(nombres)) != len(nombres):
            raise ValueError("Hay nodos con nombre repetido")
        for e in enlaces:
            if e.origen not in nombres or e.destino not in nombres:
                raise ValueError(f"Enlace con nodo desconocido: {e.origen} → {e.destino}")
            if not 0 <= e.perdida < 1:
                raise ValueError("La pérdida del enlace debe estar en [0, 1)")
        self.nodos = nodos
        self.enlaces = enlaces
        self.costo_ciclado = costo_ciclado
        self._idx = {n: i for i, n in enumerate(nombres)}

    # Orden de variables: [f_a (m), central_i (n), vertido_i (n), y_a (m)]
    def _balance(self) -> tuple[np.ndarray, np.ndarray]:
        n, m = len(self.nodos), len(self.enlaces)
        a = np.zeros((n, 2 * m + 2 * n))
        for k, e in enumerate(self.enlaces):
            a[self._idx[e.destino], k] += 1 - e.perdida
            a[self._idx[e.origen], k] -= 1
        for i in range(n):
            a[i, m + i] = 1        # central
            a[i, m + n + i] = -1   # vertido
        b = np.array([nd.carga - nd.generacion for nd in self.nodos])
        return a, b

    def resolver(self) -> ResultadoMesh:
        n, m = len(self.nodos), len(self.enlaces)
        a_bal, b = self._balance()
        c = np.concatenate(
            [
                [e.costo_transferencia for e in self.enlaces],
                np.full(n, self.costo_ciclado),
                np.zeros(n),
                [e.costo_switch for e in self.enlaces],
            ]
        )
        # f_a - cap_a·y_a <= 0
        a_cap = np.zeros((m, 2 * m + 2 * n))
        for k, e in enumerate(self.enlaces):
            a_cap[k, k] = 1
            a_cap[k, m + 2 * n + k] = -e.capacidad
        restricciones = [LinearConstraint(a_bal, b, b)]
        if m:
            restricciones.append(LinearConstraint(a_cap, -np.inf, 0))
        integralidad = np.concatenate([np.zeros(m + 2 * n), np.ones(m)])
        sup = np.concatenate([[e.capacidad for e in self.enlaces], np.full(2 * n, np.inf), np.ones(m)])
        res = milp(c, constraints=restricciones, integrality=integralidad, bounds=Bounds(0, sup))
        if not res.success:
            raise RuntimeError(f"El MILP de la red mesh no tiene solución: {res.message}")

        y = np.round(res.x[m + 2 * n :])
        # PL con switches fijos → variables duales del balance = precios sombra.
        cotas = [(0, e.capacidad * y[k]) for k, e in enumerate(self.enlaces)] + [(0, None)] * (2 * n)
        lp = linprog(c[: m + 2 * n], A_eq=a_bal[:, : m + 2 * n], b_eq=b, bounds=cotas, method="highs")
        if not lp.success:
            raise RuntimeError(f"El PL de precios sombra falló: {lp.message}")

        x = lp.x
        nombres = [nd.nombre for nd in self.nodos]
        flujos = {(e.origen, e.destino): float(x[k]) for k, e in enumerate(self.enlaces)}
        return ResultadoMesh(
            flujos=flujos,
            switches_cerrados=[(e.origen, e.destino) for k, e in enumerate(self.enlaces) if y[k] and x[k] > 1e-9],
            desde_central={nombres[i]: float(x[m + i]) for i in range(n)},
            vertido={nombres[i]: float(x[m + n + i]) for i in range(n)},
            precios_sombra={nombres[i]: float(lp.eqlin.marginals[i]) for i in range(n)},
            costo_total=float(res.fun),
        )
