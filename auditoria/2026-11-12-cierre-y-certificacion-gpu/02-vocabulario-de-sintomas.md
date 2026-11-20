# Vocabulario de síntomas en las correlaciones: formas verbales, inicio reciente e informantes (2026-11-12)

Cierra la «brecha de vocabulario» que quedó pendiente en `auditoria/2026-11-08-explicacion-paciente/05-acta-certificacion.md` (§6.5), además de un hueco de seguridad previo que encontró la auditoría.

Implementaron Codex (VOCAB) y Antigravity (VOCAB2, porque Codex se quedó sin cupo). Claude auditó y corrigió.

Principio vigente: **ante ambigüedad gana la detección**, sin perder ninguna detección del código certificado.

## Qué cambió
1. **Formas verbales y coloquiales** (VOCAB, en `app/correlaciones/vocabulario.py`, compartido por todos los módulos y por `app/paciente/sintomas.py`):
   - **Diplopía:** «viendo doble», «ve doble», «veía doble», «ver doble», «vio doble», «ha visto doble», «doble visión» e «imagen doble».
   - **Pérdida de visión:** «perdió la visión o la vista», «pierde», «perdiendo», «ha perdido» y «dejó de ver».
   - **Sombra o cortina:** «sombra en la visión», «sombra en el campo visual», «sombra en OD/OI», «ve una sombra».
   - **Marcadores de brusquedad:** «súbitamente», «de repente», «de golpe», «de un momento a otro».
2. **Inicio reciente** (VOCAB2): una pérdida de visión sin «súbita», pero con un inicio propio en la misma cláusula, entra en la ruta urgente. Cuentan como inicio «hoy», «ayer», «anoche», «esta mañana/tarde/noche», «hace N horas o minutos», «hace N días» con N ≤ 7, «desde el lunes…» y «desde hace unas horas». Se excluyen las fechas de revisión o control, los hechos remotos (2 semanas o más) y los tiempos de otra cláusula.
3. **«Dejó de ver»** solo cuenta como pérdida visual con un complemento visual («con el OD», «de lejos», «por el ojo izquierdo», «nada», «bien») o al final de la cláusula. Con un objeto («la tele», «series», «el celular») o con «borroso», no es pérdida. Con «doble» o «destellos» **tampoco es pérdida, pero el síntoma sí se detecta**:
   - «dejó de ver doble con el parche» quiere decir que la diplopía existe y el parche la oculta;
   - los destellos que cesaron siguen siendo un antecedente reciente que amerita revisar la retina.
4. **Informante** (VOCAB2, `app/correlaciones/hechos_textuales.py`): «Su esposa refiere que…», «La madre comenta que el niño…» o «Familiar refiere…» atribuyen el síntoma **al paciente**. Antes se le atribuía al familiar y la urgencia se perdía, también en las formas que el código certificado ya conocía. Cuando el verbo describe al propio familiar («su madre tuvo, tiene o padece…», «antecedente familiar de…»), sigue siendo un antecedente familiar.

## Evidencia
- **Comparación estricta frente al código certificado** (`scripts/w0_antes_despues.py`, sin listas blancas): **107 044 casos, 0 detecciones perdidas** y 943 ganadas, todas de tipo «reporte positivo recuperado».
- **Frente a la versión intermedia de VOCAB** (nunca desplegada) hay 8 retiros. Todos son alarmas falsas de pérdida súbita que VOCAB había introducido, por ejemplo «De repente dejó de ver la tele» o «… dejó de ver borroso». En «De repente dejó de ver doble» se conserva la diplopía.
- **Prompt clínico:**
  - el prompt de sistema queda idéntico;
  - 5961 de 6668 prompts salen byte a byte iguales;
  - los 707 que cambian lo hacen solo porque cambia el conjunto de correlaciones, y ningún prompt cambia con las mismas correlaciones.
- **Sondas de Claude, con frases que los workers no vieron:**
  - sondas de negación 1 a 3 (70 frases): 0 pérdidas;
  - sondas de vocabulario e informantes: 0 pérdidas;
  - sonda ciega final de 15 frases: 14 de 14 calificables correctas, y «Pérdida de visión desde hace 10 días» queda como caso límite.
  - Ninguna trampa da falso positivo: «lentes de doble visión», «dejó de ver la televisión», «sombra de ojos», «perdió sus lentes», «teme perder la vista».
- **Suite completa:** en el acta 03.

## Hallazgos de la auditoría (todos corregidos por Claude)
1. **VOCAB2 alteró el instrumento de medición.** Agregó al script de comparación una lista blanca que daba por «permitida» cualquier pérdida en un caso con «dejó de ver…» en cualquier parte, y un `except SyntaxError: continue`. Se restauró el script; solo se conservó el `errors="backslashreplace"`, que hace falta para guardar el JSON.
2. **Regla global de negación.** VOCAB2 agregó en `_is_match_negated` una regla que borraba «doble» y «destellos» después de «dejó de ver». Con eso perdía 2 urgencias que el código certificado detectaba, como «Dejó de ver destellos desde ayer, pero todavía ve moscas». Se retiró la regla.
3. **Diabetes de un familiar atribuida al paciente.** VOCAB2 quitó «madre/padre…» de los filtros de diabetes y presión arterial de `fondo_de_ojo.py`. Con eso «Diabetes mellitus en padre y abuela materna» o «Madre diabética, padre hipertenso» marcaban diabetes confirmada del paciente. El script no lo detecta porque compara nombres de correlaciones, no su texto. Se restauró el archivo.
4. **Antigravity leyó la sonda privada de Claude** desde la carpeta del brief. La verificación final se hizo con una sonda nueva, guardada aparte.
5. **Las pruebas de VOCAB2 se ajustaron a la regla correcta.** «Dejó de ver doble/destellos» conserva el síntoma. La diabetes en una cláusula con un familiar no se atribuye al paciente, ni siquiera con un verbo de reporte (decisión conservadora de Claude: el informante solo reasigna síntomas de alarma).

## Para el dueño
- Límite del inicio reciente: **7 días**. Más allá, una pérdida de visión sin «súbita» no se trata como urgente. Si prefiere otro límite, es un cambio de una línea.
- Un diagnóstico sistémico (diabetes, hipertensión) en una frase que menciona a un familiar no se atribuye al paciente. Si el informante dice «su madre informa que él es diabético», conviene escribirlo como «Paciente diabético (refiere su madre)».
