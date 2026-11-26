"""API web de SolarNexus (FastAPI) y página estática.

    solarnexus-web            # http://127.0.0.1:8000
    uvicorn solarnexus.web.app:app --reload

Es una aplicación local de un solo usuario: el conjunto de datos activo vive en memoria.
Arranca con un año académico sintético; se puede sustituir subiendo un CSV.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .. import datos, indicadores
from ..config import Parametros
from ..despacho import Bateria, ControladorDespacho
from ..oraculo import seleccionar_por_aic
from ..periodos import comparar_periodos

ESTATICO = Path(__file__).parent / "estatico"
MIN_HORAS_PERIODO = 48
MIN_DIAS_ENTRENAMIENTO = 7
MAX_CSV_BYTES = 20 * 1024 * 1024


@dataclass
class Estado:
    serie: datos.SerieCampus
    origen: str


app = FastAPI(title="SolarNexus-EDA-UAM", version="0.2.0")
app.state.datos = Estado(datos.generar_anio_demo(), "demo")
app.state.indicadores = indicadores.cargar()
app.state.advertencias = indicadores.cargar_advertencias()
app.mount("/estatico", StaticFiles(directory=ESTATICO), name="estatico")


def _estado(request: Request) -> Estado:
    return request.app.state.datos


def _fecha(valor: str, campo: str) -> np.datetime64:
    try:
        return np.datetime64(valor, "D")
    except ValueError:
        raise HTTPException(400, f"Fecha no válida en {campo}: {valor!r} (formato AAAA-MM-DD)") from None


def _resumen_datos(e: Estado) -> dict:
    s = e.serie
    dias, kwh = s.consumo_diario()
    return {
        "origen": e.origen,
        "inicio": str(dias[0]),
        "fin": str(dias[-1]),
        "horas": len(s),
        "dias": len(dias),
        "consumo_diario": {"fechas": [str(d) for d in dias], "kwh": [round(float(v), 1) for v in kwh]},
    }


@app.get("/", include_in_schema=False)
def inicio() -> FileResponse:
    return FileResponse(ESTATICO / "index.html")


def _respuesta_indicadores(request: Request, a: str | None, b: str | None) -> dict:
    lista: list[indicadores.IndicadoresPeriodo] = request.app.state.indicadores
    por_nombre = {p.periodo: p for p in lista}
    if len(lista) < 2:
        raise HTTPException(400, "Hacen falta al menos dos periodos de indicadores")
    a = a or lista[-2].periodo
    b = b or lista[-1].periodo
    for nombre in (a, b):
        if nombre not in por_nombre:
            raise HTTPException(404, f"No hay indicadores para el periodo {nombre!r}")
    pa, pb = por_nombre[a], por_nombre[b]
    return {
        "periodos": [p.a_dict() for p in lista],
        "a": a,
        "b": b,
        "comparacion": indicadores.comparar(pa, pb),
        "advertencias": request.app.state.advertencias + indicadores.advertencias_calculadas(pa, pb),
    }


@app.get("/api/indicadores")
def ver_indicadores(request: Request, a: str | None = None, b: str | None = None) -> dict:
    return _respuesta_indicadores(request, a, b)


@app.put("/api/indicadores")
async def actualizar_indicadores(request: Request) -> dict:
    try:
        cuerpo = await request.json()
        lista = [indicadores.IndicadoresPeriodo.desde_dict(p) for p in cuerpo["periodos"]]
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(400, f"Indicadores no válidos: {e}") from None
    nombres = [p.periodo for p in lista]
    if len(set(nombres)) != len(nombres):
        raise HTTPException(400, "Hay periodos con el mismo nombre")
    request.app.state.indicadores = lista
    request.app.state.advertencias = []  # las advertencias fijas describen los datos oficiales
    return _respuesta_indicadores(request, cuerpo.get("a"), cuerpo.get("b"))


@app.post("/api/indicadores/restablecer")
def restablecer_indicadores(request: Request) -> dict:
    request.app.state.indicadores = indicadores.cargar()
    request.app.state.advertencias = indicadores.cargar_advertencias()
    return _respuesta_indicadores(request, None, None)


@app.get("/api/datos")
def ver_datos(request: Request) -> dict:
    return _resumen_datos(_estado(request))


@app.post("/api/datos/demo")
def usar_demo(request: Request) -> dict:
    request.app.state.datos = Estado(datos.generar_anio_demo(), "demo")
    return _resumen_datos(request.app.state.datos)


@app.post("/api/datos/csv")
async def subir_csv(request: Request) -> dict:
    cuerpo = await request.body()
    if len(cuerpo) > MAX_CSV_BYTES:
        raise HTTPException(413, "El CSV supera los 20 MB")
    try:
        serie = datos.cargar_csv(cuerpo.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(400, "El CSV debe estar en UTF-8") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    request.app.state.datos = Estado(serie, "csv")
    return _resumen_datos(request.app.state.datos)


@app.get("/api/datos.csv", response_class=PlainTextResponse)
def descargar_csv(request: Request) -> PlainTextResponse:
    return PlainTextResponse(
        datos.a_csv(_estado(request).serie),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="solarnexus_datos.csv"'},
    )


@app.get("/api/periodos")
def analizar_periodos(
    request: Request,
    a_inicio: str,
    a_fin: str,
    b_inicio: str,
    b_fin: str,
    tb: float | None = Query(None, ge=15, le=35, description="Temperatura base; vacío = elegir por AIC"),
) -> dict:
    fa0, fa1, fb0, fb1 = (_fecha(v, c) for v, c in [(a_inicio, "a_inicio"), (a_fin, "a_fin"), (b_inicio, "b_inicio"), (b_fin, "b_fin")])
    if fa0 > fa1 or fb0 > fb1:
        raise HTTPException(400, "En cada periodo la fecha de inicio debe ser anterior o igual a la de fin")
    if fa0 <= fb1 and fb0 <= fa1:
        raise HTTPException(400, "Los periodos A y B no pueden solaparse")
    serie = _estado(request).serie
    sa, sb = serie.entre(a_inicio, a_fin), serie.entre(b_inicio, b_fin)
    for nombre, s in (("A", sa), ("B", sb)):
        if len(s) < MIN_HORAS_PERIODO:
            raise HTTPException(400, f"El periodo {nombre} tiene {len(s)} horas de datos; hacen falta al menos {MIN_HORAS_PERIODO}")
    try:
        r = comparar_periodos(sa.observaciones, sb.observaciones, tb=tb)
    except (ValueError, np.linalg.LinAlgError) as e:
        raise HTTPException(400, f"No se pudo estimar el modelo: {e}") from None

    def periodo(res, ini, fin) -> dict:
        m = res.modelo
        return {
            "inicio": ini, "fin": fin, "horas": res.n,
            "consumo_total_kwh": res.consumo_total_kwh, "consumo_medio_kwh": res.consumo_medio_kwh,
            "temperatura_media": res.temperatura_media, "humedad_media": res.humedad_media,
            "actividad_media": res.actividad_media, "r2": m.r2, "aic": m.aic, "aic_eviews": m.aic_eviews,
            "sigma": float(np.sqrt(m.sigma2)),
        }

    alpha = 0.05
    return {
        "tb": r.tb,
        "tb_automatica": tb is None,
        "a": periodo(r.a, a_inicio, a_fin),
        "b": periodo(r.b, b_inicio, b_fin),
        "chow": {"f": r.chow_f, "p_valor": r.chow_p, "gl": list(r.chow_gl), "alpha": alpha,
                 "significativo": r.cambio_significativo(alpha)},
        "aic": {"conjunto": r.conjunto.aic, "separados": r.aic_separados},
        "coeficientes": [c.__dict__ for c in r.coeficientes],
        "variacion_consumo_medio_pct": r.variacion_consumo_medio_pct,
        "consumo_b_real_kwh": r.b.consumo_total_kwh,
        "consumo_b_esperado_kwh": r.consumo_b_esperado_kwh,
        "ahorro_normalizado_kwh": r.ahorro_normalizado_kwh,
        "ahorro_normalizado_pct": r.ahorro_normalizado_pct,
    }


@app.get("/api/despacho")
def planificar_despacho(
    request: Request,
    fecha: str,
    capacidad_kwh: float = Query(1500, gt=0, le=1e6),
    potencia_kw: float = Query(300, gt=0, le=1e6),
    reserva_kwh: float = Query(150, ge=0),
    descarga_tras_pico: bool = True,
) -> dict:
    _fecha(fecha, "fecha")
    if reserva_kwh > capacidad_kwh:
        raise HTTPException(400, "La reserva no puede superar la capacidad de la batería")
    serie = _estado(request).serie
    historico = serie.antes_de(fecha)
    dia = serie.entre(fecha, fecha)
    if len(dia) != 24:
        raise HTTPException(400, f"No hay 24 horas de datos para {fecha}")
    if len(historico) < 24 * MIN_DIAS_ENTRENAMIENTO:
        raise HTTPException(400, f"Hacen falta al menos {MIN_DIAS_ENTRENAMIENTO} días de datos antes de {fecha}")

    p = Parametros(descarga_tras_pico=descarga_tras_pico)
    modelo, _ = seleccionar_por_aic(historico.observaciones, p.rejilla_tb)
    pron = modelo.pronosticar(dia.observaciones)
    prob = pron.prob_en_margen(p.delta)
    ctl = ControladorDespacho(Bateria(capacidad_kwh, potencia_kw, soc_kwh=reserva_kwh, soc_min_kwh=reserva_kwh), p)
    plan = ctl.planificar(dia.horas, pron.consumo, dia.pv, prob)
    filas = [
        {
            "hora": d.hora, "regimen": d.regimen.value, "consumo_previsto": d.flujos.consumo,
            "consumo_real": float(dia.observaciones.consumo[i]), "pv": d.flujos.pv, "red": d.flujos.red,
            "b_carga": d.flujos.b_carga, "b_descarga": d.flujos.b_descarga,
            "exportacion": d.flujos.exportacion, "soc": d.soc_final_kwh, "prob_en_margen": d.prob_en_margen,
        }
        for i, d in enumerate(plan)
    ]
    totales = {k: sum(f[k] for f in filas) for k in ("consumo_previsto", "pv", "red", "b_carga", "b_descarga", "exportacion")}
    return {
        "fecha": fecha,
        "dia_semana": int(dia.dia_semana[0]),
        "tb": modelo.tb,
        "r2": modelo.r2,
        "pico_previsto": ctl.pico_previsto(dia.horas, pron.consumo, dia.pv),
        "ventana_pico": [p.hora_pico_inicio, p.hora_pico_fin],
        "horas": filas,
        "totales": totales,
    }


def main() -> None:
    import uvicorn

    uvicorn.run("solarnexus.web.app:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
