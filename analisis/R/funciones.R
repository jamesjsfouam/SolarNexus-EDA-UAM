# Funciones del análisis econométrico de SolarNexus (modelo 3P de ASHRAE).
#
# Replica en R la especificación del paquete de Python (src/solarnexus/oraculo.py y
# src/solarnexus/estadistica/) para que ambos lenguajes den los mismos números:
#
#   ln C = b0 + b1·CDD(Tb) + b2·HUM + b3·ln ACT + b4·ln AREA + e
#
# Convenciones compartidas con Python:
#   - CDD horario = max(T - Tb, 0) (grados-hora).
#   - Humedad en fracción [0, 1] (se convierte si viene en %).
#   - Actividad acotada a >= 0.01 antes del logaritmo.
#   - AIC: R cuenta sigma como parámetro (k = 6); Python no (k = 5). AIC_R = AIC_Python + 2.
#   - HAC: Newey-West con núcleo de Bartlett, rezagos floor(4 (n/100)^(2/9)),
#     sin preblanqueo ni ajuste por grados de libertad.

# tseries carga quantmod, que avisa de un método S3 sobrescrito: se silencia.
suppressPackageStartupMessages(invisible(requireNamespace("tseries", quietly = TRUE)))

ZONA <- "America/Managua"
ACTIVIDAD_MINIMA <- 0.01
CRITERIOS_ASHRAE <- list(
  horario = c(cv_rmse = 30, nmbe = 10),
  diario  = c(cv_rmse = 25, nmbe = 10),
  mensual = c(cv_rmse = 15, nmbe = 5)
)

# ---------------------------------------------------------------- datos

leer_datos <- function(ruta, desde = NULL) {
  d <- read.csv(ruta, stringsAsFactors = FALSE)
  faltan <- setdiff(c("fecha", "temperatura", "humedad", "actividad", "area", "consumo"), names(d))
  if (length(faltan) > 0) stop("Faltan columnas en el CSV: ", paste(faltan, collapse = ", "))
  # Acepta "2026-01-05T14", "2026-01-05T14:00" y "2026-01-05 14:00".
  texto <- substr(gsub(" ", "T", d$fecha), 1, 13)
  d$fecha <- as.POSIXct(texto, format = "%Y-%m-%dT%H", tz = ZONA)
  if (anyNA(d$fecha)) stop("Hay fechas que no se pudieron leer")
  if (!"pv" %in% names(d)) d$pv <- 0
  if (max(d$humedad, na.rm = TRUE) > 1) d$humedad <- d$humedad / 100
  d$actividad <- pmax(d$actividad, ACTIVIDAD_MINIMA)
  d <- d[order(d$fecha), ]
  if (any(duplicated(d$fecha))) stop("Hay horas repetidas")
  d$dia <- as.Date(format(d$fecha, "%Y-%m-%d"))
  d$hora <- as.integer(format(d$fecha, "%H"))
  d$laborable <- as.integer(format(d$fecha, "%u")) <= 5
  if (!is.null(desde)) d <- d[d$dia >= as.Date(desde), ]
  rownames(d) <- NULL
  d
}

agregar_diario <- function(d, tb) {
  d$cdd <- cdd(d$temperatura, tb)
  dia <- aggregate(
    cbind(consumo, cdd, pv) ~ dia, data = d, FUN = sum
  )
  medias <- aggregate(cbind(temperatura, humedad, actividad, area) ~ dia, data = d, FUN = mean)
  dia <- merge(dia, medias, by = "dia")
  dia$laborable <- as.integer(format(dia$dia, "%u")) <= 5
  dia[order(dia$dia), ]
}

# ---------------------------------------------------------------- modelo 3P

cdd <- function(temperatura, tb) pmax(temperatura - tb, 0)

ajustar_3p <- function(d, tb) {
  d$cdd <- cdd(d$temperatura, tb)
  m <- lm(log(consumo) ~ cdd + humedad + log(actividad) + log(area), data = d)
  attr(m, "tb") <- tb
  m
}

seleccionar_tb <- function(d, rejilla = 22:30) {
  modelos <- lapply(rejilla, function(tb) ajustar_3p(d, tb))
  tabla <- data.frame(
    tb = rejilla,
    aic = sapply(modelos, AIC),
    # EViews y Python solo cuentan los coeficientes (k = 5): (AIC_R - 2) / n
    aic_eviews = sapply(modelos, function(m) (AIC(m) - 2) / nobs(m)),
    r2 = sapply(modelos, function(m) summary(m)$r.squared)
  )
  mejor <- which.min(tabla$aic)
  list(modelo = modelos[[mejor]], tb = rejilla[mejor], tabla = tabla)
}

rezagos_newey_west <- function(n) floor(4 * (n / 100)^(2 / 9))

coeficientes_hac <- function(m) {
  L <- rezagos_newey_west(nobs(m))
  v <- sandwich::NeweyWest(m, lag = L, prewhite = FALSE, adjust = FALSE)
  ct <- lmtest::coeftest(m, vcov. = v)
  data.frame(
    coeficiente = c("b0", "b1_cdd", "b2_hum", "b3_ln_act", "b4_ln_area"),
    valor = unname(coef(m)),
    ee_mco = unname(sqrt(diag(vcov(m)))),
    ee_hac = unname(ct[, 2]),
    t_hac = unname(ct[, 3]),
    p_hac = unname(ct[, 4]),
    row.names = NULL
  )
}

diagnosticos <- function(m, rezagos_bg = 24) {
  e <- residuals(m)
  dw <- lmtest::dwtest(m)
  bg <- lmtest::bgtest(m, order = rezagos_bg, type = "Chisq", fill = 0)
  bp <- lmtest::bptest(m, studentize = TRUE)
  jb <- tseries::jarque.bera.test(e)
  pruebas <- data.frame(
    prueba = c("Durbin-Watson", paste0("Breusch-Godfrey (", rezagos_bg, " rezagos)"), "Breusch-Pagan", "Jarque-Bera"),
    estadistico = c(unname(dw$statistic), unname(bg$statistic), unname(bp$statistic), unname(jb$statistic)),
    p_valor = c(dw$p.value, bg$p.value, bp$p.value, jb$p.value),
    hipotesis_nula = c("sin autocorrelación de orden 1", "sin autocorrelación", "varianza constante", "residuos normales")
  )
  list(pruebas = pruebas, factor_duan = mean(exp(e)), rezagos_hac = rezagos_newey_west(length(e)))
}

predecir_kwh <- function(m, nuevos, factor_duan) {
  nuevos$cdd <- cdd(nuevos$temperatura, attr(m, "tb"))
  exp(predict(m, newdata = nuevos)) * factor_duan
}

# ---------------------------------------------------------------- ASHRAE Guideline 14

metricas_ashrae <- function(real, estimado, p = 0, frecuencia = "horario") {
  n <- length(real)
  e <- real - estimado
  media <- mean(real)
  cv <- 100 * sqrt(sum(e^2) / (n - p)) / media
  nmbe <- 100 * sum(e) / ((n - p) * media)
  crit <- CRITERIOS_ASHRAE[[frecuencia]]
  data.frame(
    frecuencia = frecuencia, n = n, cv_rmse_pct = cv, nmbe_pct = nmbe,
    r2 = 1 - sum(e^2) / sum((real - media)^2),
    mape_pct = 100 * mean(abs(e) / abs(real)),
    cumple = cv <= crit[["cv_rmse"]] && abs(nmbe) <= crit[["nmbe"]]
  )
}

# ---------------------------------------------------------------- series de tiempo

# Bai-Perron sobre datos diarios: ¿cuándo cambió la relación consumo-clima-actividad?
quiebres_diarios <- function(diario, h = 0.1) {
  f <- log(consumo) ~ cdd + humedad + log(actividad) + log(area)
  bp <- strucchange::breakpoints(f, data = diario, h = h)
  fs <- strucchange::Fstats(f, data = diario, from = h)
  supf <- strucchange::sctest(fs, type = "supF")
  n_optimo <- length(stats::na.omit(bp$breakpoints))
  # strucchange devuelve la última observación del régimen anterior; el nuevo régimen
  # empieza el día siguiente, que es la fecha útil para la opción --desde de Python.
  fechas <- if (n_optimo > 0) diario$dia[bp$breakpoints + 1] else as.Date(character(0))
  ic <- if (n_optimo > 0) {
    ci <- confint(bp)$confint
    data.frame(
      inicio_nuevo_regimen = diario$dia[ci[, 2] + 1],
      ic95_desde = diario$dia[ci[, 1] + 1],
      ic95_hasta = diario$dia[pmin(ci[, 3] + 1, nrow(diario))]
    )
  } else NULL
  list(bp = bp, supf = supf, fechas = fechas, intervalos = ic, fs = fs)
}

raiz_unitaria <- function(x) {
  # tseries avisa cuando el p-valor cae fuera de su tabla (0,01–0,10); el informe lo explica.
  adf <- suppressWarnings(tseries::adf.test(x))
  kpss <- suppressWarnings(tseries::kpss.test(x, null = "Level"))
  data.frame(
    prueba = c("ADF (H0: raíz unitaria)", "KPSS (H0: estacionaria)"),
    estadistico = c(unname(adf$statistic), unname(kpss$statistic)),
    p_valor = c(adf$p.value, kpss$p.value)
  )
}
