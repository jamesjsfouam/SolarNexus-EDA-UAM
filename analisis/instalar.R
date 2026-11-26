# Instala los paquetes del análisis. Ejecutar una vez: Rscript instalar.R
paquetes <- c(
  "sandwich",    # errores estándar HAC de Newey-West
  "lmtest",      # coeftest, Durbin-Watson, Breusch-Godfrey, Breusch-Pagan
  "tseries",     # Jarque-Bera, ADF, KPSS
  "strucchange", # quiebres estructurales de Bai-Perron y supF
  "jsonlite",    # leer el reporte de Python
  "knitr",       # tablas del informe
  "rmarkdown"    # motor de R para Quarto
)
faltan <- setdiff(paquetes, rownames(installed.packages()))
if (length(faltan) > 0) {
  install.packages(faltan, repos = "https://cloud.r-project.org")
} else {
  message("Todos los paquetes ya están instalados.")
}
invisible(lapply(paquetes, function(p) stopifnot(requireNamespace(p, quietly = TRUE))))
message("Listo: ", paste(paquetes, collapse = ", "))
