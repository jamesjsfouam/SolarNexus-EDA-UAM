"""Línea de comandos del componente estadístico.

    python -m solarnexus.estadistica validar                       # datos de demostración
    python -m solarnexus.estadistica validar --csv datos.csv --desde 2025-10-09
    python -m solarnexus.estadistica pronosticar --fecha 2026-11-03 --salida pronostico.json
    python -m solarnexus.estadistica pronosticar --api http://localhost:8000 --enviar

Fuentes de datos: --csv (formato de solarnexus.datos), --api (backend, GET /api/v1/measurements)
o, si no se indica ninguna, el año sintético de demostración.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .. import datos
from ..oraculo import seleccionar_por_aic
from . import fuentes
from .cliente import ErrorAPI, enviar_pronostico, leer_mediciones
from .metricas import CRITERIOS_ASHRAE
from .pronostico import a_contrato, escenario_climatologico, escenario_con_clima, pronosticar_dia
from .validacion import ReporteValidacion, validar

DEMO_INICIO_PRUEBA = "2026-10-01"
DEMO_FECHA_PRONOSTICO = "2026-11-03"
REJILLA_TB = range(22, 31)


def _cargar(args) -> tuple[datos.SerieCampus, str]:
    if args.csv and args.api:
        raise SystemExit("Usa --csv o --api, no ambos")
    if args.csv:
        return datos.cargar_csv(Path(args.csv).read_text(encoding="utf-8")), "csv"
    if args.api:
        return leer_mediciones(args.api), "api"
    return datos.generar_anio_demo(), "demo"


def _desde(serie: datos.SerieCampus, desde: str | None) -> datos.SerieCampus:
    if desde is None:
        return serie
    return serie.filtrar(serie.fechas.astype("datetime64[D]") >= np.datetime64(desde, "D"))


def _ultimo_dia(serie: datos.SerieCampus) -> np.datetime64:
    return serie.fechas.astype("datetime64[D]").max()


def _sumar(fecha: np.datetime64 | str, dias: int) -> str:
    return str(np.datetime64(fecha, "D") + np.timedelta64(dias, "D"))


def _clima(fuente: str, inicio: str, fin: str, args) -> fuentes.Clima | None:
    if fuente == "climatologico":
        return None
    c = fuentes.obtener(fuente, inicio, fin, args.lat, args.lon)
    print(f"Clima: {c.fuente}, {len(c)} horas ({inicio} → {fin}).")
    return c


def imprimir_reporte(r: ReporteValidacion) -> None:
    m, d = r.modelo, r.diagnosticos
    print("=== Modelo 3P (estimado antes de la prueba) ===")
    print(f"Observaciones: {m.n}   Tb: {m.tb:.0f} °C   R²: {m.r2:.4f}   σ (ln): {np.sqrt(m.sigma2):.4f}")
    print(f"{'coeficiente':<12}{'valor':>10}{'e.e. MCO':>10}{'e.e. HAC':>10}{'p HAC':>11}")
    for c in d.coeficientes:
        print(f"{c.nombre:<12}{c.valor:>10.4f}{c.ee_mco:>10.4f}{c.ee_hac:>10.4f}{c.p_valor_hac:>11.3g}")
    print(f"(errores HAC de Newey-West con {d.rezagos_hac} rezagos)")

    print("\n=== Diagnósticos de residuos ===")
    print(f"Durbin-Watson: {d.durbin_watson:.3f}  (≈2 = sin autocorrelación)")
    for p in (d.breusch_godfrey, d.breusch_pagan, d.jarque_bera):
        veredicto = "se rechaza" if p.rechaza() else "no se rechaza"
        print(f"{p.nombre:<16} estadístico {p.estadistico:>10.2f}  p = {p.p_valor:.3g}  → {veredicto}: {p.hipotesis_nula}")
    print(f"Factor de Duan (sesgo al volver de logaritmos): {d.factor_duan:.4f}")
    for aviso in d.avisos():
        print(f"  ! {aviso}")

    print(f"\n=== Validación ASHRAE Guideline 14 (backtest de {r.dias_prueba} días desde {r.inicio_prueba}) ===")
    print("Regresores de los días de prueba: " + ", ".join(f"{o} ({n} días)" for o, n in r.regresores.items()))
    print(f"{'muestra':<22}{'CV(RMSE)':>10}{'NMBE':>9}{'R²':>8}{'MAPE':>8}   criterio   ¿cumple?")
    for nombre, x in (("dentro (horario)", r.dentro_muestra), ("fuera (horario)", r.fuera_horario), ("fuera (diario)", r.fuera_diario)):
        c = CRITERIOS_ASHRAE[x.frecuencia]
        print(f"{nombre:<22}{x.cv_rmse_pct:>9.1f}%{x.nmbe_pct:>8.1f}%{x.r2:>8.3f}{x.mape_pct:>7.1f}%"
              f"   ≤{c['cv_rmse']:.0f}% / ±{c['nmbe']:.0f}%   {'sí' if x.cumple_ashrae else 'NO'}")

    print(f"\n=== Calibración de P(|error| ≤ {r.delta}) ===")
    print(f"Probabilidad media sin calibrar: {r.prob_media_sin_calibrar:.1%}")
    print(f"Frecuencia real dentro del margen: {r.frecuencia_en_margen:.1%}")
    print(f"Factor de calibración k: {r.factor_calibracion:.3f}  ({'el modelo era demasiado confiado' if r.factor_calibracion > 1 else 'el modelo era prudente'})")
    print(f"Cobertura real del intervalo del 95 % calibrado: {r.cobertura_95:.1%}")
    print(f"\nApto para alimentar el despacho: {'sí' if r.apto_para_despacho else 'NO'}")


def cmd_validar(args) -> int:
    serie, origen = _cargar(args)
    serie = _desde(serie, args.desde)
    inicio = args.inicio_prueba or (DEMO_INICIO_PRUEBA if origen == "demo" else _sumar(_ultimo_dia(serie), 1 - args.dias))
    if args.clima == "open-meteo":
        raise SystemExit("Para validar días pasados usa --clima open-meteo-pasados (pronósticos tal como se emitieron)")
    clima = _clima(args.clima, inicio, _sumar(inicio, args.dias - 1), args)
    r = validar(serie, inicio, dias_prueba=args.dias, rejilla_tb=REJILLA_TB, delta=args.delta,
                inicio_entrenamiento=args.desde, clima=clima, kwp=args.kwp, rendimiento=args.rendimiento)
    if args.salida:
        Path(args.salida).write_text(json.dumps(r.a_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Reporte JSON guardado en {args.salida}")
    if args.json:
        print(json.dumps(r.a_dict(), ensure_ascii=False, indent=2))
    else:
        imprimir_reporte(r)
    return 0


def cmd_pronosticar(args) -> int:
    serie, origen = _cargar(args)
    serie = _desde(serie, args.desde)
    fecha = args.fecha or (DEMO_FECHA_PRONOSTICO if origen == "demo" else _sumar(_ultimo_dia(serie), 1))
    if not 1 <= args.horizonte <= 7:
        raise SystemExit("--horizonte debe estar entre 1 y 7 días (el contrato admite hasta 168 horas)")

    dias = [_sumar(fecha, i) for i in range(args.horizonte)]
    # El backtest debe usar la misma clase de regresores que el pronóstico: con Open-Meteo,
    # los pronósticos pasados tal como se emitieron.
    fuente_backtest = "open-meteo-pasados" if args.clima == "open-meteo" else args.clima

    # 1) Calibración con un backtest de los días previos a la fecha.
    historico = serie.antes_de(fecha)
    inicio_bt = _sumar(fecha, -args.dias)
    clima_bt = _clima(fuente_backtest, inicio_bt, _sumar(fecha, -1), args)
    r = validar(historico, inicio_bt, dias_prueba=args.dias, rejilla_tb=REJILLA_TB, delta=args.delta,
                clima=clima_bt, kwp=args.kwp, rendimiento=args.rendimiento)
    # 2) Modelo final con todo el historial disponible.
    modelo, _ = seleccionar_por_aic(historico.observaciones, REJILLA_TB)
    clima = _clima(args.clima, dias[0], dias[-1], args)

    def escenario(d: str):
        if clima is not None:
            try:
                e = escenario_con_clima(historico, d, clima, kwp=args.kwp, rendimiento=args.rendimiento)
                if args.kwp and np.isnan(clima.perfil_24h(d)[2]).all():
                    print(f"! {clima.fuente} aún no publica la radiación de {d}: la PV es el perfil histórico.")
                return e
            except ValueError:
                print(f"! {clima.fuente} no tiene datos para {d}: se usa el escenario climatológico.")
        return escenario_climatologico(historico, d)

    escenarios = [escenario(d) for d in dias]
    pronosticos = [
        pronosticar_dia(modelo, e, delta=args.delta,
                        factor_calibracion=r.factor_calibracion, factor_duan=r.diagnosticos.factor_duan)
        for e in escenarios
    ]
    origenes = sorted({e.origen for e in escenarios})
    cita = " Datos meteorológicos: Open-Meteo.com (CC BY 4.0)." if any("open-meteo" in o for o in origenes) else ""
    notas = (f"Datos: {origen}. Tb={modelo.tb:.0f} °C, n={modelo.n}. Backtest {r.dias_prueba} días "
             f"({', '.join(r.regresores)}): CV(RMSE)={r.fuera_horario.cv_rmse_pct:.1f} %, "
             f"NMBE={r.fuera_horario.nmbe_pct:.1f} %, k={r.factor_calibracion:.3f}, delta={args.delta}. "
             f"Regresores del pronóstico: {', '.join(origenes)}.{cita}")
    cuerpo = a_contrato(pronosticos, model_version=args.version, notes=notas)

    print(f"Pronóstico {dias[0]} → {dias[-1]} ({len(cuerpo['points'])} horas). Tb = {modelo.tb:.0f} °C, k = {r.factor_calibracion:.3f}.")
    print(f"{'hora local':<27}{'demanda':>9}{'PV':>8}{'P(margen)':>11}")
    for p in cuerpo["points"][:24]:
        print(f"{p['interval_start']:<27}{p['demand_kwh']:>9.1f}{p['pv_generation_kwh']:>8.1f}{p['probability_within_margin']:>11.3f}")
    if len(cuerpo["points"]) > 24:
        print(f"… y {len(cuerpo['points']) - 24} horas más")
    if not r.apto_para_despacho:
        print("! Aviso: el backtest no cumple ASHRAE 14 o la calibración; revisa antes de usarlo para despachar.")

    if args.salida:
        Path(args.salida).write_text(json.dumps(cuerpo, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Guardado en {args.salida}")
    if args.enviar:
        destino = args.enviar if isinstance(args.enviar, str) else args.api
        if not destino:
            raise SystemExit("--enviar necesita una URL (o usa --api)")
        respuesta = enviar_pronostico(destino, cuerpo)
        print(f"Enviado a {destino}/api/v1/forecasts → id {respuesta.get('id')}")
    return 0


def cmd_exportar(args) -> int:
    serie, origen = _cargar(args)
    serie = _desde(serie, args.desde)
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(datos.a_csv(serie), encoding="utf-8")
    dias = serie.fechas.astype("datetime64[D]")
    print(f"{len(serie)} horas ({origen}, {dias.min()} → {dias.max()}) exportadas a {salida}")
    return 0


def cmd_clima(args) -> int:
    c = fuentes.obtener(args.fuente, args.inicio, args.fin, args.lat, args.lon)
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(c.a_csv(), encoding="utf-8")
    faltan = int(np.isnan(c.temperatura).sum())
    print(f"{len(c)} horas de {c.fuente} guardadas en {salida}" + (f" ({faltan} sin temperatura)" if faltan else ""))
    if "open-meteo" in c.fuente:
        print("Cita la fuente: Weather data by Open-Meteo.com (CC BY 4.0).")
    return 0


def main(argv: list[str] | None = None) -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="solarnexus.estadistica", description="Validación y pronóstico del modelo 3P")
    sub = ap.add_subparsers(dest="comando", required=True)

    def comunes(p):
        p.add_argument("--csv", help="CSV horario (fecha,temperatura,humedad,actividad,area,consumo,pv)")
        p.add_argument("--api", help="URL base del backend, p. ej. http://localhost:8000")
        p.add_argument("--desde", help="descartar datos anteriores a esta fecha (quiebre estructural)")
        p.add_argument("--dias", type=int, default=28, help="días del backtest (por defecto 28)")
        p.add_argument("--delta", type=float, default=0.10, help="margen admisible en ln C (0.10 ≈ ±10 %%)")
        p.add_argument("--clima", default="climatologico", choices=("climatologico",) + fuentes.FUENTES,
                       help="origen de temperatura y humedad (por defecto, promedio de los últimos 28 días)")
        p.add_argument("--kwp", type=float, help="potencia solar instalada; estima la PV con la radiación de --clima")
        p.add_argument("--rendimiento", type=float, default=0.80, help="factor de rendimiento de la planta (PR)")
        p.add_argument("--lat", type=float, default=fuentes.LAT_UAM)
        p.add_argument("--lon", type=float, default=fuentes.LON_UAM)

    v = sub.add_parser("validar", help="ASHRAE 14, diagnósticos y calibración")
    comunes(v)
    v.add_argument("--inicio-prueba", help="primer día del backtest (AAAA-MM-DD)")
    v.add_argument("--json", action="store_true", help="salida en JSON")
    v.add_argument("--salida", help="guardar el reporte JSON en este archivo (lo usa analisis/contraste_python.R)")
    v.set_defaults(func=cmd_validar)

    x = sub.add_parser("exportar", help="exportar los datos a CSV para el análisis en R")
    x.add_argument("--csv", help="CSV de entrada")
    x.add_argument("--api", help="URL base del backend")
    x.add_argument("--desde", help="descartar datos anteriores a esta fecha")
    x.add_argument("--salida", default="analisis/datos/solarnexus_datos.csv", help="archivo CSV de salida")
    x.set_defaults(func=cmd_exportar)

    c = sub.add_parser("clima", help="descargar clima horario de Managua a CSV (también para R)")
    c.add_argument("--fuente", required=True, choices=fuentes.FUENTES)
    c.add_argument("--inicio", required=True, help="AAAA-MM-DD")
    c.add_argument("--fin", required=True, help="AAAA-MM-DD (inclusive)")
    c.add_argument("--lat", type=float, default=fuentes.LAT_UAM)
    c.add_argument("--lon", type=float, default=fuentes.LON_UAM)
    c.add_argument("--salida", default="analisis/datos/clima.csv")
    c.set_defaults(func=cmd_clima)

    p = sub.add_parser("pronosticar", help="pronóstico en el formato de POST /api/v1/forecasts")
    comunes(p)
    p.add_argument("--fecha", help="primer día a pronosticar (por defecto, el día siguiente a los datos)")
    p.add_argument("--horizonte", type=int, default=1, help="días a pronosticar, de 1 a 7")
    p.add_argument("--version", default="0.1.0", help="model_version que se envía al backend")
    p.add_argument("--salida", help="guardar el JSON en este archivo")
    p.add_argument("--enviar", nargs="?", const=True, help="enviar al backend (URL o, sin valor, la de --api)")
    p.set_defaults(func=cmd_pronosticar)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, ErrorAPI) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
