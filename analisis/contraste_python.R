# Contraste R ↔ Python: ¿el componente de Python estima lo mismo que R?
#
# Uso (desde la carpeta analisis/):
#   python -m solarnexus.estadistica exportar --salida analisis/datos/solarnexus_datos.csv
#   python -m solarnexus.estadistica validar --csv analisis/datos/solarnexus_datos.csv --desde 2026-08-01 \
#       --salida analisis/datos/reporte_python.json
#   Rscript contraste_python.R datos/solarnexus_datos.csv datos/reporte_python.json
#
# Python debe leer el MISMO CSV que R (--csv): el CSV redondea los valores y, con los datos
# sin redondear, los coeficientes difieren en la cuarta o quinta cifra.
#
# Compara coeficientes, errores MCO y HAC, R², AIC, pruebas de diagnóstico, factor de Duan
# y métricas ASHRAE dentro de muestra. Termina con código 1 si alguna diferencia supera
# la tolerancia, para poder usarlo en integración continua.

suppressPackageStartupMessages({
  library(jsonlite)
})
source("R/funciones.R")

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) stop("Uso: Rscript contraste_python.R <datos.csv> <reporte_python.json>")
py <- fromJSON(args[2], simplifyVector = TRUE)

desde <- py$backtest$inicio_entrenamiento
d <- leer_datos(args[1], desde = desde)
entreno <- d[d$dia < as.Date(py$backtest$inicio), ]

sel <- seleccionar_tb(entreno, 22:30)
m <- ajustar_3p(entreno, py$modelo$tb)
hac <- coeficientes_hac(m)
diag <- diagnosticos(m)
dentro <- metricas_ashrae(entreno$consumo, predecir_kwh(m, entreno, diag$factor_duan), p = length(coef(m)))
pruebas_py <- py$diagnosticos$pruebas

fila <- function(concepto, r, python, tolerancia) {
  dif <- abs(r - python) / max(abs(python), 1e-12)
  data.frame(concepto = concepto, R = r, Python = python, dif_relativa = dif, ok = dif <= tolerancia)
}

comparacion <- rbind(
  data.frame(concepto = "Tb elegida por AIC", R = sel$tb, Python = py$modelo$tb,
             dif_relativa = abs(sel$tb - py$modelo$tb), ok = sel$tb == py$modelo$tb),
  fila("observaciones", nobs(m), py$modelo$n, 0),
  fila("R²", summary(m)$r.squared, py$modelo$r2, 1e-8),
  fila("AIC (R − 2)", AIC(m) - 2, py$modelo$aic, 1e-8),
  do.call(rbind, lapply(seq_len(nrow(hac)), function(i) rbind(
    fila(paste(hac$coeficiente[i], "valor"), hac$valor[i], py$coeficientes$valor[i], 1e-6),
    fila(paste(hac$coeficiente[i], "e.e. MCO"), hac$ee_mco[i], py$coeficientes$ee_mco[i], 1e-6),
    fila(paste(hac$coeficiente[i], "e.e. HAC"), hac$ee_hac[i], py$coeficientes$ee_hac[i], 1e-4)
  ))),
  fila("Durbin-Watson", diag$pruebas$estadistico[1], py$diagnosticos$durbin_watson, 1e-6),
  fila("Breusch-Godfrey", diag$pruebas$estadistico[2], pruebas_py$estadistico[pruebas_py$nombre == "Breusch-Godfrey"], 1e-4),
  fila("Breusch-Pagan", diag$pruebas$estadistico[3], pruebas_py$estadistico[pruebas_py$nombre == "Breusch-Pagan"], 1e-4),
  fila("Jarque-Bera", diag$pruebas$estadistico[4], pruebas_py$estadistico[pruebas_py$nombre == "Jarque-Bera"], 1e-4),
  fila("factor de Duan", diag$factor_duan, py$diagnosticos$factor_duan, 1e-8),
  fila("CV(RMSE) dentro", dentro$cv_rmse_pct, py$dentro_muestra$cv_rmse_pct, 1e-6),
  fila("NMBE dentro", dentro$nmbe_pct, py$dentro_muestra$nmbe_pct, 1e-4)
)

options(width = 120)
cat(sprintf("Muestra de estimación: %s → %s (%d horas)\n\n", min(entreno$dia), max(entreno$dia), nrow(entreno)))
print(transform(comparacion, R = signif(R, 8), Python = signif(Python, 8), dif_relativa = signif(dif_relativa, 2)),
      row.names = FALSE)
fallos <- sum(!comparacion$ok)
cat(sprintf("\n%s: %d de %d comparaciones dentro de tolerancia.\n",
            if (fallos == 0) "OK" else "DIFERENCIAS", nrow(comparacion) - fallos, nrow(comparacion)))
quit(status = if (fallos == 0) 0 else 1)
