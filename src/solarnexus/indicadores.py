"""Indicadores anuales de sostenibilidad del campus y su comparación entre periodos.

Los valores de partida (2024 y 2025) están en `indicadores_uam.json` y proceden del
Informe de Sostenibilidad 2025 de la UAM (infografías). Ver
docs/investigacion-sistema-electrico-uam.md para las inconsistencias encontradas.

Corrección metodológica: la UAM publica unas "emisiones per cápita" que en realidad
son (brutas + evitadas) / comunidad, es decir, las emisiones que habría si toda la
energía viniera de la red. Aquí se calculan por separado:
  - per cápita real      = emisiones brutas / comunidad
  - per cápita (método UAM) = (brutas + evitadas) / comunidad, solo como referencia
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

RUTA_POR_DEFECTO = Path(__file__).with_name("indicadores_uam.json")


@dataclass(frozen=True)
class Definicion:
    clave: str
    nombre: str
    unidad: str
    mejor_si: str             # "sube", "baja" o "neutro"
    porcentaje: bool = False  # el cambio se expresa en puntos porcentuales
    derivado: bool = False    # calculado a partir de otros indicadores
    nota: str = ""


DEFINICIONES: tuple[Definicion, ...] = (
    Definicion("pct_solar", "Energía de Solar Jaguar en la matriz eléctrica", "%", "sube", porcentaje=True,
               nota="Valor publicado por la UAM."),
    Definicion("solar_implicita_pct", "Parte solar implícita en el CO₂", "%", "sube", porcentaje=True, derivado=True,
               nota="Evitadas / (brutas + evitadas). Debería coincidir con el % publicado."),
    Definicion("intensidad_kwh_m2", "Intensidad energética", "kWh/m²/año", "baja"),
    Definicion("emisiones_brutas_kg", "Emisiones brutas de CO₂ (energía de la red)", "kg CO₂/año", "baja"),
    Definicion("co2_evitado_kg", "CO₂ evitado por Solar Jaguar", "kg CO₂/año", "sube"),
    Definicion("emisiones_netas_kg", "Emisiones netas (brutas − evitadas)", "kg CO₂/año", "baja", derivado=True),
    Definicion("exportacion_kwh", "Excedente solar inyectado al SIN", "kWh", "sube"),
    Definicion("comunidad_personas", "Comunidad UAM", "personas", "neutro"),
    Definicion("per_capita_real_kg", "Emisiones per cápita reales (brutas / comunidad)", "kg CO₂/persona", "baja",
               derivado=True),
    Definicion("per_capita_uam_kg", "Per cápita con el método de la UAM ((brutas + evitadas) / comunidad)",
               "kg CO₂/persona", "neutro", derivado=True,
               nota="Mide las emisiones que habría sin paneles; sigue al consumo, no a las emisiones reales."),
    Definicion("emisiones_sin_solar_kg", "Emisiones si toda la energía viniera de la red", "kg CO₂/año", "neutro",
               derivado=True, nota="Brutas + evitadas; es proporcional al consumo total."),
)
CLAVES_EDITABLES = tuple(d.clave for d in DEFINICIONES if not d.derivado)


def _div(a: float | None, b: float | None) -> float | None:
    return None if a is None or not b else a / b


@dataclass(frozen=True)
class IndicadoresPeriodo:
    periodo: str
    pct_solar: float | None = None
    intensidad_kwh_m2: float | None = None
    emisiones_brutas_kg: float | None = None
    co2_evitado_kg: float | None = None
    exportacion_kwh: float | None = None
    comunidad_personas: float | None = None
    nota: str = ""

    @property
    def emisiones_sin_solar_kg(self) -> float | None:
        if self.emisiones_brutas_kg is None or self.co2_evitado_kg is None:
            return None
        return self.emisiones_brutas_kg + self.co2_evitado_kg

    @property
    def emisiones_netas_kg(self) -> float | None:
        if self.emisiones_brutas_kg is None or self.co2_evitado_kg is None:
            return None
        return self.emisiones_brutas_kg - self.co2_evitado_kg

    @property
    def solar_implicita_pct(self) -> float | None:
        r = _div(self.co2_evitado_kg, self.emisiones_sin_solar_kg)
        return None if r is None else 100 * r

    @property
    def per_capita_real_kg(self) -> float | None:
        return _div(self.emisiones_brutas_kg, self.comunidad_personas)

    @property
    def per_capita_uam_kg(self) -> float | None:
        return _div(self.emisiones_sin_solar_kg, self.comunidad_personas)

    def valor(self, clave: str) -> float | None:
        return getattr(self, clave)

    def a_dict(self) -> dict:
        d = asdict(self)
        d.update({x.clave: self.valor(x.clave) for x in DEFINICIONES if x.derivado})
        return d

    @classmethod
    def desde_dict(cls, d: dict) -> IndicadoresPeriodo:
        periodo = str(d.get("periodo", "")).strip()
        if not periodo:
            raise ValueError("Cada periodo necesita un nombre")
        valores = {}
        for clave in CLAVES_EDITABLES:
            v = d.get(clave)
            if v is None or v == "":
                valores[clave] = None
                continue
            try:
                v = float(v)
            except (TypeError, ValueError):
                raise ValueError(f"{clave} debe ser numérico en {periodo}") from None
            if v < 0:
                raise ValueError(f"{clave} no puede ser negativo en {periodo}")
            valores[clave] = v
        if valores["pct_solar"] is not None and valores["pct_solar"] > 100:
            raise ValueError(f"pct_solar no puede superar 100 en {periodo}")
        return cls(periodo=periodo, nota=str(d.get("nota", "")), **valores)


def cargar(ruta: Path = RUTA_POR_DEFECTO) -> list[IndicadoresPeriodo]:
    with open(ruta, encoding="utf-8") as f:
        return [IndicadoresPeriodo.desde_dict(p) for p in json.load(f)["periodos"]]


def cargar_advertencias(ruta: Path = RUTA_POR_DEFECTO) -> list[str]:
    with open(ruta, encoding="utf-8") as f:
        return list(json.load(f).get("advertencias", []))


def comparar(a: IndicadoresPeriodo, b: IndicadoresPeriodo) -> list[dict]:
    """Una fila por indicador con el cambio absoluto, relativo y si es una mejora."""
    filas = []
    for d in DEFINICIONES:
        va, vb = a.valor(d.clave), b.valor(d.clave)
        cambio = None if va is None or vb is None else vb - va
        relativo = None if cambio is None or not va else 100 * cambio / va
        if cambio is None or d.mejor_si == "neutro" or cambio == 0:
            mejora = None
        else:
            mejora = (cambio > 0) == (d.mejor_si == "sube")
        filas.append({
            "clave": d.clave, "nombre": d.nombre, "unidad": d.unidad, "mejor_si": d.mejor_si,
            "porcentaje": d.porcentaje, "derivado": d.derivado, "nota": d.nota,
            "a": va, "b": vb, "cambio": cambio, "cambio_relativo_pct": relativo, "mejora": mejora,
        })
    return filas


def advertencias_calculadas(a: IndicadoresPeriodo, b: IndicadoresPeriodo, tolerancia_pp: float = 3.0) -> list[str]:
    """Incoherencias detectables con los propios datos (p. ej. % solar publicado vs implícito)."""
    avisos = []
    for p in (a, b):
        if p.pct_solar is not None and p.solar_implicita_pct is not None:
            dif = p.solar_implicita_pct - p.pct_solar
            if abs(dif) > tolerancia_pp:
                avisos.append(
                    f"{p.periodo}: el % solar publicado ({p.pct_solar:.0f} %) no cuadra con el implícito en el CO₂ "
                    f"({p.solar_implicita_pct:.1f} %)."
                )
    return avisos
