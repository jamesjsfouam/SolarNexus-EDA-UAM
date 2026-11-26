# Análisis econométrico en R

Esta carpeta contiene el **análisis** del consumo eléctrico de la UAM. El **pronóstico operativo**
que se envía cada día al backend sigue en Python (`src/solarnexus/estadistica/`).

| Pieza | Dónde | Para qué |
| --- | --- | --- |
| Análisis econométrico | `analisis/` (R) | Elegir el modelo, buscar quiebres estructurales, diagnósticos y el informe |
| Pronóstico diario | `src/solarnexus/estadistica/` (Python) | Validar, calibrar y enviar pronósticos a `POST /api/v1/forecasts` |
| Contraste | `analisis/contraste_python.R` | Comprobar que Python y R estiman exactamente lo mismo |

## Instalación (una vez)

1. Instala **R** (4.3 o posterior) desde <https://cran.r-project.org/bin/windows/base/>.
2. Instala **RStudio** desde <https://posit.co/download/rstudio-desktop/>; incluye Quarto para generar el informe.
3. En una terminal dentro de `analisis/`:

```powershell
Rscript instalar.R
```

## Flujo de trabajo

Desde la raíz del repositorio, exporta los datos que leerá R (por defecto, el año sintético de demostración):

```powershell
python -m solarnexus.estadistica exportar --salida analisis/datos/solarnexus_datos.csv
```

Con datos reales, añade `--csv archivo.csv` o `--api http://localhost:8000`.

### Informe completo

Abre `informe.qmd` en RStudio y pulsa **Render**, o desde `analisis/`:

```powershell
quarto render informe.qmd -P desde:2026-08-01 -P inicio_prueba:2026-10-01
```

Secciones del informe:

1. Datos y consumo diario.
2. Temperatura base $T_b$ por mínimo AIC.
3. Coeficientes con errores HAC de Newey-West (`sandwich`, `lmtest`).
4. Diagnósticos: Durbin-Watson, Breusch-Godfrey, Breusch-Pagan y Jarque-Bera; ACF y Q-Q de residuos.
5. Validación ASHRAE Guideline 14 dentro y fuera de muestra (*ex post*).
6. Quiebres estructurales de Bai-Perron y prueba supF (`strucchange`) sobre datos diarios.
7. Raíz unitaria: ADF y KPSS (`tseries`).
8. Conclusiones automáticas, incluida la fecha sugerida para `--desde`.

### Contraste con Python

```powershell
python -m solarnexus.estadistica validar --csv analisis/datos/solarnexus_datos.csv --desde 2026-08-01 --inicio-prueba 2026-10-01 --salida analisis/datos/reporte_python.json
```

Python tiene que leer **el mismo CSV** que R (`--csv`): el CSV redondea los valores, y con los datos sin
redondear los coeficientes difieren a partir de la cuarta o quinta cifra.

```powershell
cd analisis; Rscript contraste_python.R datos/solarnexus_datos.csv datos/reporte_python.json
```

Imprime una tabla R frente a Python (coeficientes, errores MCO y HAC, R², AIC, pruebas de diagnóstico,
factor de Duan y métricas ASHRAE) y termina con `OK` si todo coincide dentro de la tolerancia.

## Convenciones compartidas con Python

- CDD horario = max(T − Tb, 0); humedad en fracción; actividad acotada a ≥ 0,01 antes del logaritmo.
- **AIC:** R cuenta σ como parámetro, Python y EViews no: AIC de R = AIC de Python + 2. La elección de $T_b$ no cambia.
- **HAC:** núcleo de Bartlett con floor(4·(n/100)^(2/9)) rezagos, sin preblanqueo ni ajuste de grados de libertad
  (`NeweyWest(m, lag = L, prewhite = FALSE, adjust = FALSE)`).
- **Breusch-Godfrey** con 24 rezagos (un día de datos horarios) y rezagos iniciales rellenados con 0.
- Hora local de Managua (UTC−6, sin horario de verano).

Los CSV y los JSON de `analisis/datos/` no se suben al repositorio (pueden contener datos reales de la UAM).
