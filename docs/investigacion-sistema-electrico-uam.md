# Sistema eléctrico de la UAM y sus reportes de sostenibilidad

*Investigación del 26 de noviembre de 2026 para SolarNexus-EDA-UAM. Fuentes: los informes de sostenibilidad 2024 y 2025 de la UAM (incluidas sus infografías), la página UAM Verde, notas de prensa y la normativa eléctrica nicaragüense. Las cifras marcadas como **(derivado)** son cálculos propios a partir de los datos publicados, no cifras oficiales.*

## 1. Resumen

- La UAM consume unos **1,4 GWh al año**. En 2024 fueron 1.415.000 kWh: 75 % de la red y 25 % de la planta **Solar Jaguar**. En 2025 la parte solar subió al **34 %**.
- La planta solar se construyó en dos etapas (2022 y junio de 2024). La prensa de 2026 le atribuye **730 kW instalados**. En diciembre de 2024 tenía **437 paneles**, lo que equivale a unos 220–240 kWp. Probablemente los 730 kW incluyen el techo del edificio Copérnico, inaugurado en octubre de 2025.
- Desde **junio de 2025** hay un contrato para inyectar excedentes al Sistema Interconectado Nacional (SIN). En 2025 se inyectaron **60.200 kWh**. Ninguna fuente menciona baterías.
- La UAM tiene las certificaciones **ISO 14001:2015 e ISO 50001:2018**, auditadas por AENOR en julio de 2025. La estación meteorológica Copérnico es una **Davis Vantage Pro2**.
- Los reportes son **páginas web con infografías, no PDF**, y no siguen ningún estándar (ni GRI ni GHG Protocol). **Tienen contradicciones importantes en las cifras de CO₂ y de intensidad energética** (sección 5).
- Hallazgo clave para el modelo: la UAM calcula el CO₂ con un factor de unos **0,23 kg CO₂/kWh** (derivado). Es un factor de red promedio, no el factor marginal de **0,68** que usa el whitepaper. Ese 0,68 salió de leer como "evitadas" una cifra que en realidad eran emisiones netas.

## 2. Infraestructura eléctrica

| Elemento | Dato | Fuente |
| --- | --- | --- |
| Consumo anual 2024 | 1.415.000 kWh (75 % red, 25 % solar) | [Informe 2024](https://www.uam.edu.ni/sostebilidad-uam/) |
| Consumo anual 2025 | No publicado. **(Derivado)** unos 1,44 GWh, a partir del CO₂ y el factor implícito | [Informe 2025](https://www.uam.edu.ni/informe-sostenibilidad-2025/) |
| Solar Jaguar, 1.ª etapa | 2022 | [Informe 2024](https://www.uam.edu.ni/sostebilidad-uam/) |
| Solar Jaguar, 2.ª etapa | Construcción desde enero de 2024; inaugurada el 8 de junio (año 2024, deducido de la ruta de la imagen) | [UAM Verde](https://www.uam.edu.ni/uam-verde-principal/), [UAM 2024](https://www.uam.edu.ni/uam-2024-un-ano-verde-de-innovacion-y-compromiso/) |
| Paneles | 437 (diciembre de 2024, total) | [E&N BrandLab, dic. 2024](https://www.revistaeyn.com/eyn-brandlab/uam-comprometida-con-el-medioambiente-y-la-sostenibilidad-en-nicaragua-CC22755676) |
| Capacidad instalada | 730 kW, "cerca del 50 % del consumo" | [Vida y Éxito, ago. 2026](https://www.vidayexito.net/top-news/uam-una-marca-que-educa-innova-y-transforma/), [Vida y Éxito, may. 2026](https://www.vidayexito.net/aliado-estrategico/universidad-americana-uam-mejor-universidad-verde-de-nicaragua-2025-reafirma-su-compromiso-con-la-sostenibilidad/) |
| Edificio Copérnico | Obra iniciada en 2023 e inaugurada en octubre de 2025. Tres pisos (24 o 26 aulas según la fuente), techo reflectante, aislamiento, climatización eficiente y parque fotovoltaico en el techo ("60 % de la energía limpia", proyectado). Observatorio astronómico, estación meteorológica y sismógrafo | [E&N, abr. 2025](https://www.revistaeyn.com/eyn-brandlab/uam-pionera-en-sostenibilidad-y-educacion-superior-en-nicaragua-IC25367791), [UAM Verde](https://www.uam.edu.ni/uam-verde-principal/) |
| Inyección al SIN | Contrato firmado en junio de 2025; 60.200 kWh inyectados en 2025 | Infografía "Inyección a la red", [Informe 2025](https://www.uam.edu.ni/informe-sostenibilidad-2025/) |
| Almacenamiento | Ninguna fuente menciona baterías | — |
| Estación meteorológica | Davis Vantage Pro2. Mide temperatura, humedad, presión, viento, UV, lluvia y radiación solar. Se publica como página con gráficos, sin datos descargables | [Boletín meteorológico](https://www.uam.edu.ni/boletin-meteorologico-uam/) |
| Certificaciones | ISO 14001:2015 e ISO 50001:2018 (auditoría externa de AENOR, julio de 2025); además ISO 9001 e ISO 21001 | [Informe 2025](https://www.uam.edu.ni/informe-sostenibilidad-2025/), [UAM Verde](https://www.uam.edu.ni/uam-verde-principal/) |
| Responsable | Dirección de Gestión Ambiental y Energética (director: Carlos Germán Meza González) | [Vida y Éxito, may. 2026](https://www.vidayexito.net/aliado-estrategico/universidad-americana-uam-mejor-universidad-verde-de-nicaragua-2025-reafirma-su-compromiso-con-la-sostenibilidad/) |

**Comprobación de la planta (derivado).** 437 paneles de unos 500–550 W suman unos 220–240 kWp. Con un rendimiento típico de techo de ~1.500 kWh/kWp al año, salen unos 350 MWh, muy cerca de los 353.750 kWh (25 % de 1.415.000) de 2024. En cambio, 730 kW funcionando todo el año darían más de 1 GWh, lo que encaja con el "cerca del 50 %" de la prensa de 2026 pero no con el 34 % de 2025. Lo más probable es que la potencia completa entrara a finales de 2025, con Copérnico.

## 3. Contexto de la red nacional

- **Distribuidora:** Managua la abastece Disnorte-Dissur. La participación de TMI pasó por ley al Estado, y en junio de 2026 el MEM cambió su junta directiva ([La Prensa](https://www.laprensani.com/2026/06/29/politica/3725620-santiago-bermudez-pierde-poder-energia), [Leybook](https://www.leybook.com/doc/9846/pdf)).
- **Tarifa:** un cliente como la UAM probablemente esté en una tarifa **binomia**, que cobra la energía (C$/kWh) y la **demanda máxima** (C$/kW-mes). La demanda máxima es la mayor potencia promedio en 15 minutos del mes ([Normativa de Servicio Eléctrico](https://rise.esmap.org/sites/default/files/library/nicaragua/Renewable%20Energy/Nicaragua%20-%20Electric%20Sector%20Norm.pdf)). Como referencia, el pliego de agosto de 2025 para Bluefields da 4,41 C$/kWh y 463,63 C$/kW-mes en la tarifa general mayor; la tabla está desordenada y hay que verificarla ([INE](https://www.ine.gob.ni/wp-content/uploads/2025/08/bluefields_agosto25_pliego_tarifa_enatrel.pdf)). El precio final para negocios ronda los 7,77 C$/kWh, unos US$0,21 ([GlobalPetrolPrices](https://www.globalpetrolprices.com/Nicaragua/electricity_prices/)).
- **Excedentes:** la Normativa de Generación Distribuida Renovable para Autoconsumo (Acuerdo Ministerial 063-DGERR-002-2017) permite hasta 5 MW e inyectar excedentes con contrato con la distribuidora. Los excedentes se pagan al **80 % del precio más bajo de la banda de referencia** ([texto oficial](https://cdn.climatepolicyradar.org/navigator/NIC/2017/regulation-on-the-generation-of-renewable-energy-for-self-consumption-ministerial-agreement-no-063-dgerr-002-2017_8185d0a67e777c2ec5e072b603388358.pdf), [pv magazine](https://www.pv-magazine.com/2018/01/11/nicaraguas-new-net-metering-regulations-come-into-force/)). El contrato de junio de 2025 encaja con este régimen: **exportar vale bastante menos que autoconsumir**, que es justo la premisa del despacho de SolarNexus.
- **Matriz:** un 62 % renovable en 2024 según datos de Ember, con una intensidad de unos 301 g CO₂/kWh ([Ecoki](https://ecoki.com/data/electricity-mix-by-country/nicaragua/)); un 73 % en 2025 según el MEM ([teleSUR](https://www.telesurtv.net/nicaragua-impulsa-fuentes-renovables-energia/)). No encontré un factor de emisión oficial del SIN publicado por el CNDC o el MEM.

## 4. Cómo son los reportes de la UAM

| | Informe 2024 | Informe 2025 |
| --- | --- | --- |
| Formato | [Página web](https://www.uam.edu.ni/sostebilidad-uam/) con texto y gráficos. Fue el "primer informe de sustentabilidad" (diciembre de 2024) | [Página web](https://www.uam.edu.ni/informe-sostenibilidad-2025/) con infografías en imagen (las cifras no están como texto) |
| Secciones | Logros clave; matriz energética y huella de carbono; agua; papel; investigación; pilares; residuos; grupos de interés; acciones; hitos | Mensajes de autoridades; energía y Solar Jaguar (solar, inyección a la red, gestión energética); emisiones de CO₂ (brutas, evitadas, per cápita); papel; residuos; agua; educación; publicaciones; reconocimientos |
| Indicadores de energía | Consumo total, % solar, kWh/m²·año (88) | % solar, kWh/m²·año (104 → 102), kWh inyectados |
| Indicadores de CO₂ | Emisiones netas y evitadas | Emisiones brutas, evitadas, netas y per cápita |
| Metodología | No se publica. No cita GRI, GHG Protocol, ISO 14064 ni el factor de emisión | Igual |
| Comparación | Un solo año | 2024 frente a 2025, variación absoluta y relativa |

Índice: [Reportes de sostenibilidad](https://www.uam.edu.ni/reportes-de-sostenibilidad/). Las notas de prensa de E&N son contenido pagado ("E&N Brand Lab para UAM"), y las de Vida y Éxito aparecen en la sección "Aliado estratégico".

### Cifras del informe 2025 (infografías)

| Indicador | 2024 | 2025 | Variación según la UAM |
| --- | --- | --- | --- |
| Solar en la matriz eléctrica | 25 % | 34 % | +9 puntos |
| Intensidad energética | 104 kWh/m²·año | 102 kWh/m²·año | −1,92 % |
| Emisiones brutas de CO₂ | 239.659,39 kg | 184.907,58 kg | — |
| Emisiones evitadas | 83.697,97 kg (77.394,36 en otra infografía) | 143.785,35 kg | +66.390,99 kg |
| Impacto neto (brutas − evitadas) | 155.961,42 kg **(derivado)** | 41.122,23 kg | presentado como "41.122,23 kg/año menos" |
| Comunidad UAM | 6.288 personas | 7.225 personas | +14,9 % |
| Emisiones per cápita | 51,43 kg | 45,49 kg | −11,51 % (con estas cifras sale −11,55 %) |
| Inyección al SIN | — | 60.200 kWh | contrato de junio de 2025 |

## 5. Contradicciones e inconsistencias

1. **CO₂ evitado en 2024: cuatro valores distintos.**
   - 239.299 kg ("CO₂ evitados" en el titular del informe 2024).
   - 84.000 kg (gráfico de huella del mismo informe, donde 239.299 kg aparecen como emisiones netas).
   - 83.697,97 kg (infografía de emisiones brutas de 2025).
   - 77.394,36 kg (infografía de emisiones evitadas de 2025).
2. **Las emisiones "per cápita" suman las evitadas.**
   - 51,43 × 6.288 = 323.392 kg, que coincide con brutas + evitadas de 2024 (323.357 kg).
   - 45,49 × 7.225 = 328.665 kg, que coincide con brutas + evitadas de 2025 (328.693 kg).
   - Es decir, el indicador mide las emisiones que habría si toda la energía viniera de la red, no las emisiones reales. Sigue el consumo total, que creció un 1,65 % **(derivado)**.
   - Con las emisiones brutas, el per cápita real bajó de **38,1 a 25,6 kg CO₂/persona (−33 %)** **(derivado)**. Es un resultado mucho mejor que el −11,5 % publicado.
3. **El texto contradice el gráfico de emisiones brutas.** El texto habla de un "aumento en emisiones brutas", pero el gráfico muestra que bajan de 239.659 a 184.908 kg.
4. **El "impacto neto" está mal rotulado.** 41.122,23 kg es el impacto neto de 2025, no la reducción. La reducción real es de 114.839 kg **(derivado)**.
5. **La parte solar no cuadra con el CO₂.**
   - En 2024, evitadas / (brutas + evitadas) = 25,9 %, coherente con el 25 % publicado.
   - En 2025 la misma razón da 43,7 %, frente al 34 % publicado.
   - O cambió el factor de emisión, o la exportación se cuenta como evitada, o el 34 % usa otra base.
6. **Intensidad energética de 2024: 88 frente a 104 kWh/m²·año.** Con 1.415.000 kWh, eso implica áreas de 16.080 m² frente a 13.606 m² **(derivado)**.
7. **Parte solar en otras fuentes:** 25 % (informe 2024), "más del 50 %" (E&N, diciembre de 2024), 75 % (nota UAM 2024) y "cerca del 50 %" (prensa 2026).
8. **Fecha de las ISO:** en 2024 figuraban como meta; la página UAM Verde las da a la vez como "en proceso" y "obtenidas"; la auditoría de AENOR fue en julio de 2025.

**Factor de emisión implícito (derivado):** 323.357 kg / 1.415.000 kWh ≈ **0,229 kg CO₂/kWh**. La infografía de 77.394 kg da 0,219 sobre 353.750 kWh solares. Es un factor promedio de red. El 0,68 del whitepaper ("coherente con el informe UAM") se apoyaba en leer 239.299 kg como emisiones evitadas, y eso es un error del propio informe de la UAM.

## 6. Implicaciones para SolarNexus

1. **El modelo de datos necesita brutas, evitadas y netas por separado**, además del per cápita real (brutas / comunidad). Tal como lo calcula la UAM, el per cápita no sirve como KPI.
2. **Factor de emisión:** usar ~0,23 kg/kWh para reproducir los reportes de la UAM. El factor marginal térmico (~0,7) solo como escenario y declarado como estimación propia.
3. **Ventana pico:** el despacho supone 14–17 h. Hay que confirmar en la factura de la UAM si su tarifa tiene horario punta y cuál es. El ahorro real del *peak shaving* está en el **cargo por demanda máxima (kW-mes)**, no solo en los kWh.
4. **Exportar vale poco:** los excedentes se pagan al 80 % de la banda más baja, así que cargar baterías y autoconsumir rinde más que exportar. Esto valida la regla de carga. Pero la UAM no tiene baterías, así que el módulo de despacho es hoy una propuesta de inversión.
5. **Datos horarios:** la estación Copérnico (Davis Vantage Pro2) guarda datos de alta frecuencia en su consola o en WeatherLink, aunque la web solo publica gráficos. Pedir la exportación a Gestión Ambiental y Energética, junto con el historial del inversor y las facturas con demanda máxima.

## 7. Datos que faltan, para pedirlos a la Dirección de Gestión Ambiental y Energética

- Facturas mensuales: kWh, kW de demanda máxima, tipo de tarifa y periodos horarios.
- Historial del inversor de Solar Jaguar: generación cada 15 minutos o cada hora, potencia instalada por etapa y fecha de entrada de Copérnico.
- Registro de la inyección al SIN: kWh mensuales y precio del contrato de junio de 2025.
- Factor de emisión y metodología de los informes. Explicar las cifras 88/104 kWh/m² y 77.394/83.698/84.000/239.299 kg.
- Área construida y climatizada por año.
- Exportación de los datos de la estación Copérnico.
