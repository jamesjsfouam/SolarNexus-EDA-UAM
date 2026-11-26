"""Demostración de punta a punta con datos sintéticos.

    python -m solarnexus                # día laborable
    python -m solarnexus --dia finde    # día de fin de semana
"""

from __future__ import annotations

import argparse
import sys

from . import datos
from .config import Parametros
from .despacho import Bateria, ControladorDespacho
from .mesh import Enlace, Nodo, RedMeshDC
from .oraculo import seleccionar_por_aic


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="solarnexus", description="Despacho predictivo SolarNexus (datos sintéticos)")
    ap.add_argument("--dias", type=int, default=120, help="días de histórico para estimar el modelo")
    ap.add_argument("--dia", choices=["laborable", "finde"], default="laborable", help="día a pronosticar")
    ap.add_argument("--semilla", type=int, default=7)
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # consola de Windows (cp1252)

    p = Parametros()
    # Histórico empieza en lunes; tras él se busca el primer día del tipo pedido.
    extra = 1
    while ((args.dias + extra - 1) % 7 >= 5) != (args.dia == "finde"):
        extra += 1
    serie = datos.generar(args.dias + extra, semilla=args.semilla)
    historico = serie.tramo(0, 24 * args.dias)
    objetivo = serie.dia(args.dias + extra - 1)
    nombre_dia = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][int(objetivo.dia_semana[0])]

    modelo, candidatos = seleccionar_por_aic(historico.observaciones, p.rejilla_tb)
    print("=== 1. Oráculo econométrico 3P ===")
    print(f"Observaciones: {modelo.n}   Tb elegida por AIC: {modelo.tb:.0f} °C   R²: {modelo.r2:.3f}")
    print("Tb  " + "  ".join(f"{m.tb:>6.0f}" for m in candidatos))
    print("AIC " + "  ".join(f"{m.aic_eviews:>6.3f}" for m in candidatos) + "   (escala EViews)")
    for nombre, valor in modelo.coeficientes().items():
        print(f"  {nombre:<11}{valor:>9.4f}")

    pron = modelo.pronosticar(objetivo.observaciones)
    prob = pron.prob_en_margen(p.delta)
    bateria = Bateria(capacidad_kwh=1500, potencia_max_kw=300, soc_kwh=150, soc_min_kwh=150)
    controlador = ControladorDespacho(bateria, p)
    plan = controlador.planificar(objetivo.horas, pron.consumo, objetivo.pv, prob)

    print(f"\n=== 2. Despacho de 24 h ({nombre_dia}) ===")
    print(f"Pico vespertino previsto: {'sí' if controlador.pico_previsto(objetivo.horas, pron.consumo, objetivo.pv) else 'no'}"
          f"   compuerta de exportación: P >= {p.confianza:.0%} con delta = {p.delta}")
    print(f"{'h':>2} {'C^':>6} {'PV':>6} {'P(m)':>5} {'G':>6} {'Bc':>6} {'Bd':>6} {'X':>6} {'SOC':>6}  régimen")
    for d in plan:
        f = d.flujos
        print(f"{d.hora:>2} {f.consumo:>6.0f} {f.pv:>6.0f} {d.prob_en_margen:>5.2f} {f.red:>6.0f} {f.b_carga:>6.0f}"
              f" {f.b_descarga:>6.0f} {f.exportacion:>6.0f} {d.soc_final_kwh:>6.0f}  {d.regimen.value}")
    print("Totales kWh: " + "  ".join(
        f"{k}={sum(getattr(d.flujos, a) for d in plan):.0f}"
        for k, a in [("G", "red"), ("Bc", "b_carga"), ("Bd", "b_descarga"), ("X", "exportacion")]
    ))

    print("\n=== 3. Red mesh DC (un intervalo de ejemplo) ===")
    red = RedMeshDC(
        nodos=[Nodo("Copérnico", 120, 40), Nodo("Pabellón C", 10, 90), Nodo("Biblioteca", 30, 30)],
        enlaces=[
            Enlace("Copérnico", "Pabellón C", capacidad=60, costo_transferencia=0.02, perdida=0.03),
            Enlace("Copérnico", "Biblioteca", capacidad=60, costo_transferencia=0.01, perdida=0.02),
            Enlace("Biblioteca", "Pabellón C", capacidad=60, costo_transferencia=0.01, perdida=0.02),
        ],
        costo_ciclado=0.12,
    )
    r = red.resolver()
    for (o, dst), f in r.flujos.items():
        print(f"  {o} → {dst}: {f:6.1f} kWh")
    print("  Switches cerrados: " + ", ".join(f"{o}→{dst}" for o, dst in r.switches_cerrados))
    print("  Desde inversor central: " + ", ".join(f"{k}={v:.1f}" for k, v in r.desde_central.items() if v > 1e-9))
    print("  Precios sombra λ (USD/kWh): " + ", ".join(f"{k}={v:.4f}" for k, v in r.precios_sombra.items()))
    print(f"  Costo total del intervalo: {r.costo_total:.3f} USD")
    print("\n(Datos sintéticos: sustituir por Copérnico, registro académico y Solar Jaguar.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
