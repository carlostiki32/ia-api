# Correcciones de coherencia documental

Comparación contra el estado de los archivos al iniciar esta revisión; conserva los cambios previos del repositorio.
Cada apartado enumera las correcciones y muestra el diff completo para comprobar el antes y el después.
Los plazos, estados y motivos ya coincidentes con el código se conservaron; los valores operativos no se cambiaron.

## .env.example

Fuentes: [app/config.py](../../app/config.py), [app/paciente/integracion.py](../../app/paciente/integracion.py), [app/paciente/ensamblado.py](../../app/paciente/ensamblado.py).

- Aclarar que OLLAMA_DUAL_NUM_PREDICT está inactivo.
- Precisar la excepción de error con el interruptor apagado.

```diff
--- .env.example (inicio)
+++ .env.example
@@ -3,7 +3,8 @@
 OLLAMA_TIMEOUT=120.0
 OLLAMA_TEMPERATURE=0.2
 OLLAMA_NUM_PREDICT=1024
-# Salida dual; no altera el presupuesto legacy.
+# Compatibilidad con configuraciones existentes; ya no se usa.
+# Ambos modos clínicos usan OLLAMA_NUM_PREDICT.
 OLLAMA_DUAL_NUM_PREDICT=1024
 OLLAMA_NUM_CTX=8192
 OLLAMA_REPEAT_PENALTY=1.0
@@ -44,4 +45,5 @@
 PLAZO_GLOBAL_RECETA_S=85
 PACIENTE_OMITIR_SI_ESPERA=true
 # Plazos positivos. Reserva CPU fija: 0.1 s. Global desde llegada, incluida cola.
-# false evita llamadas y prosa cacheada del paciente; motivo nulo en respaldo.
+# false evita llamadas y prosa cacheada del paciente; motivo nulo en respaldo
+# salvo fallo de ensamblado (rechazada/error).
```

## SALIDA_DUAL.md

Fuentes: [app/paciente/prompts.py](../../app/paciente/prompts.py), [app/paciente/servicio.py](../../app/paciente/servicio.py), [app/paciente/integracion.py](../../app/paciente/integracion.py), [app/paciente/validador.py](../../app/paciente/validador.py), [app/paciente/ensamblado.py](../../app/paciente/ensamblado.py).

- Precisar cuándo se usa el conteo estricto.
- Documentar la regla revisada de lente y los efectos sustentados por Rx.
- Precisar el motivo error que prevalece al apagar el interruptor.
- Hacer consistente la descripción operativa del interruptor.
- Enlazar el catálogo generado y distinguir el conteo aislado del glosario.

```diff
--- SALIDA_DUAL.md (inicio)
+++ SALIDA_DUAL.md
@@ -22,12 +22,16 @@
 La redacción explica graduación y hallazgos en la vida diaria con frases cortas,
 lenguaje cotidiano y traducciones del glosario. Efectos no referidos: «puede» o
 «podría». No confirma diagnósticos ni añade exploraciones o normalidad.
+El hecho `lente` solo autoriza su descripción CPU: monofocal no determina una
+distancia de uso. Se admiten efectos de la graduación y ayuda de los lentes
+cuando los hechos los sustentan; atribuir lejos, cerca o lectura al diseño
+monofocal en la misma frase infringe la regla `lente`.
 Salida JSON: una a cuatro frases y hasta 120 palabras; 384 tokens de salida,
 temperatura 0.2 y semilla 42. Verificación JSON: solo `{"valido":true}` aprueba;
 32 tokens, temperatura 0 y semilla 42. Una tentativa por etapa, `think=false`.
 El proveedor determina `num_ctx=min(OLLAMA_NUM_CTX,LIMITE_CONTEXTO_TOKENS,8192)`.
 
-Ambas llamadas usan siempre presupuesto estricto sin contador exacto. La llamada
+Sin contador exacto, ambas llamadas usan siempre política de presupuesto estricta. La llamada
 clínica conserva `PRESUPUESTO_RECETA_SIN_EXACTO`: `estricto` usa bytes UTF-8 como
 cota demostrable (una receta típica puede dar 413); `conservador` usa heurística,
 con advertencia y sin garantía exacta. Un caso mínimo puede caber incluso en
@@ -35,8 +39,11 @@
 
 Techos de entrada: 7000/7400; entrada más salida: 7384/7432, por debajo de 7782
 con contexto efectivo 8192. Conteo oficial del system: redacción 1012 tokens
-(incluye objetivo y glosario), verificación 174. Cada llamada cuenta la entrada
-completa con roles y envoltura; el esquema no se concatena al prompt. No existe
+(incluye objetivo y glosario), verificación 174. El glosario aislado cuenta 419.
+El [material generado para revisión](auditoria/2026-11-08-explicacion-paciente/02-catalogo-y-prompts-para-revision.md)
+contiene los textos literales y las versiones; se regenera con
+`python scripts/catalogo_paciente.py --salida RUTA.md --tokenizer RUTA_TOKENIZER_JSON`.
+Cada llamada cuenta la entrada completa con roles y envoltura; el esquema no se concatena al prompt. No existe
 un máximo finito de longitud del clínico final: un contexto excesivo usa respaldo.
 
 ## Respuesta
@@ -79,7 +86,8 @@
 `generada/llm`. Si falla, las acciones aún se entregan; sin ellas se conserva
 el estado del perfil. AKR nunca completa el perfil educativo.
 
-`motivo_explicacion`: nulo al generar con éxito o con el interruptor apagado;
+`motivo_explicacion`: nulo al generar con éxito o con el interruptor apagado
+(salvo fallo de ensamblado, que conserva `error`);
 ante respaldo por fallo: `validacion`, `verificacion`, `abstencion`, `timeout`,
 `presupuesto`, `ocupado` o `error`. La explicación ensamblada admite hasta 2000
 puntos de código. Si no cabe, se descarta toda la prosa, nunca se corta una acción.
@@ -104,7 +112,8 @@
 exigen valores positivos. Cada etapa usa el mínimo entre techo y plazo restante.
 `PACIENTE_OMITIR_SI_ESPERA=true` cede antes de cada etapa si espera otra interactiva.
 `PACIENTE_LLM_HABILITADO=false` evita ambas llamadas y entrega acciones + plantilla,
-con motivo nulo; también evita servir prosa LLM del paciente ya cacheada.
+con motivo nulo salvo fallo de ensamblado; también evita servir prosa LLM del
+paciente ya cacheada.
 Cambiar configuración requiere recargar el proceso para aplicar los settings.
 
 ## Caché, registro y métricas
```

## README.md

Fuentes: [app/main.py](../../app/main.py), [app/config.py](../../app/config.py), [app/inference.py](../../app/inference.py), [app/correlaciones/registry.py](../../app/correlaciones/registry.py).

- Aclarar el turno del paciente tras caché clínica parcial.
- Corregir el registro DEBUG de prompts.
- Evitar afirmar que .env.example enumera todos los settings.
- Exponer el interruptor del paciente en la configuración.
- Corregir módulos de dominio de cristalino, motilidad y diplopía.
- Actualizar el contenido real de auditoria, incluido el catálogo del dueño.
- Describir las cuatro reglas corneales sin confirmar diagnósticos.
- Precisar el alcance de pupilas_motilidad frente al módulo de motilidad.

```diff
--- README.md (inicio)
+++ README.md
@@ -16,7 +16,7 @@
 |---|---|
 | `POST /v1/inferencia/receta-clinica` | Alias del handler de `/inferencia/impresion-clinica`: mismos contratos y caché. Prioridad interactiva. |
 | `POST /v1/inferencia/seguimiento-whatsapp` | Contrato `seguimiento-whatsapp-v1`: catálogo determinista, redacción y verificación JSON en fondo; cualquier fallo del modelo devuelve HTTP 200 con `estado=plantilla` y `motivo`. |
-| `GET /v1/tareas` | Tabla calculada con los settings activos: endpoints, prioridades, llamadas, versiones, opciones y respaldos. La explicación es una tarea hija: redacción (384) y verificación (32), en el turno clínico; respaldo en CPU. |
+| `GET /v1/tareas` | Tabla calculada con los settings activos: endpoints, prioridades, llamadas, versiones, opciones y respaldos. La explicación es una tarea hija: redacción (384) y verificación (32), en el turno clínico o en un turno propio si solo falta el paciente tras un acierto parcial de caché; respaldo en CPU. |
 
 `GET /health` conserva sus claves y añade `gpu` con ocupación, prioridad del ocupante
 y esperas separadas. El planificador es local al proceso: **un worker de uvicorn y
@@ -144,7 +144,7 @@
 | `app/providers/ollama.py` | Cliente HTTP hacia Ollama (`/api/chat`), parámetros de sampling, reintentos, monitoreo de contexto. |
 | `app/cache.py` | Cache en memoria (TTL + tamaño máximo) para no repetir inferencias idénticas. |
 | `tests/` | Suite de pytest (más de 6000 pruebas): correlaciones (incluye golden tests de texto exacto), prompt builder, schemas, inferencia, endpoint principal y el corpus de casos históricos. |
-| `auditoria/` | Solo datos y scripts de referencia que leen las pruebas: corpus `2026-09-21/casos.json` y las órdenes/matrices de `conformidad-2026-09-29/` y `certificacion-2026-09-29/`. No es código de la API. |
+| `auditoria/` | Material de revisión, corpus y scripts de referencia, incluidas las matrices consumidas por las pruebas y el catálogo generado para el dueño. |
 | `start_linux.sh` | Script de arranque para Ubuntu: valida `.env`, levanta Ollama si hace falta, descarga el modelo si falta, activa el venv, corre uvicorn. |
 | `.env` / `.env.example` | Configuración real / plantilla. Ver [§9](#9-configuración-env). |
 
@@ -228,9 +228,12 @@
 | `fondo_de_ojo.py` | Hallazgos de fondo de ojo (glaucoma, DMAE, vascular, periférico...) |
 | `refractivas.py` | Miopía magna, hipermetropía alta, anisometropía, AV limitada... |
 | `akr.py` | Correlación entre autorrefractómetro y refracción final |
-| `corneal.py` | Queratocono/ectasia y astigmatismo corneal vs refractivo (queratometría como disparador) |
-| `anexos_cristalino.py` | Anexos oculares, opacidad de cristalino |
-| `pupilas_motilidad.py` | Reflejos pupilares, motilidad ocular |
+| `corneal.py` | Valores queratométricos elevados o planos, discrepancias con Rx y asimetría entre ojos |
+| `anexos_cristalino.py` | Anexos oculares |
+| `segmento_anterior.py` | Opacidad del cristalino y riesgo de glaucoma secundario |
+| `motilidad.py` | Motilidad ocular |
+| `sintomas_agudos.py` | Diplopía aguda |
+| `pupilas_motilidad.py` | Reflejos pupilares y combinaciones de pupilas/motilidad |
 | `campos_amsler.py` | Campos visuales, rejilla de Amsler |
 | `binocularidad.py` | Cover test, PPC, forias/tropias |
 | `superficie_ocular.py` | BUT (ojo seco) |
@@ -261,7 +264,7 @@
 
 ## 9. Configuración (`.env`)
 
-La plantilla completa es [.env.example](.env.example); cada parámetro de sampling/contexto de Ollama está comentado con su justificación (incluidas mediciones en la 3070 Ti) en [app/config.py](app/config.py). Las variables que más te importan para tu flujo:
+La plantilla de configuración es [.env.example](.env.example); cada parámetro de sampling/contexto de Ollama está comentado con su justificación (incluidas mediciones en la 3070 Ti) en [app/config.py](app/config.py). Las variables que más te importan para tu flujo:
 
 | Variable | Para qué |
 |---|---|
@@ -273,7 +276,8 @@
 | `API_KEY` | El token que Postman debe mandar en `Authorization: Bearer`. **Cámbialo del placeholder** (el script de arranque lo exige). |
 | `HOST` / `PORT` | Dónde escucha uvicorn (default `0.0.0.0:8888`, para que Postman le pueda pegar desde otra máquina en tu red). Los lee `start_linux.sh`. |
 | `MAX_CONCURRENT` | Déjalo en `1` — tu GPU procesa una inferencia a la vez. |
-| `LOG_LEVEL` | `INFO` normal; `DEBUG` imprime además el prompt completo renderizado antes de cada inferencia (útil para depurar). |
+| `PACIENTE_LLM_HABILITADO` | `true` por omisión; `false` omite redacción/verificación y la prosa paciente cacheada, con respaldo CPU. No cambia la llamada clínica. |
+| `LOG_LEVEL` | `INFO` normal; `DEBUG` registra tamaños de system/user y estimaciones de tokens, sin imprimir los prompts completos. |
 
 ---
```

## DICCIONARIO_DATOS_RECETA.md

Fuentes: [app/schemas.py](../../app/schemas.py), [app/clinical_data.py](../../app/clinical_data.py), [app/main.py](../../app/main.py), [app/paciente/contexto.py](../../app/paciente/contexto.py), [app/paciente/validador.py](../../app/paciente/validador.py), [app/paciente/integracion.py](../../app/paciente/integracion.py), [app/paciente/ensamblado.py](../../app/paciente/ensamblado.py).

- Completar la normalización de ADD fuera de rango.
- Documentar transposición de la Rx final y conservación de nulos.
- Precisar el contrato educativo del tipo de lente.
- Corregir la activación mínima: AKR por ojo sí; metadata sola no.
- Corregir el eje transpuesto del AKR.
- Precisar estados nulos, rechazo y comportamiento del interruptor.
- Distinguir límites de recepción y captura para textos clínicos.
- Alinear ADD del seguimiento con el schema compartido.
- No equiparar un cero aislado con normalidad.
- Distinguir detail estructurado de validación 422 e incluir el error 500.

```diff
--- DICCIONARIO_DATOS_RECETA.md (inicio)
+++ DICCIONARIO_DATOS_RECETA.md
@@ -77,9 +77,14 @@
 | `esfera` | `number \| null` | DROPDOWN | `nullable\|numeric\|decimal:0,2\|between:-30,30` | Dropdown de **+20.00 a -20.00 D en pasos de 0.25** (161 opciones exactas generadas por `OpticaOptions::esfera()`). Default en creación: `0.00`. Rango de BD admite hasta ±30.00 D para alta miopía y afaquia extrema. |
 | `cilindro` | `number \| null` | DROPDOWN | `nullable\|numeric\|decimal:0,2\|between:-30,30` | Dropdown de **0.00 a -8.00 D en pasos de 0.25** (33 opciones en `OpticaOptions::cilindro()`). Siempre convención negativa (`≤ 0.00`). Default en creación: `0.00`. |
 | `eje` | `integer \| null` | NUM LIBRE | `nullable\|integer\|between:0,180` | **Validado formalmente entre 0 y 180 grados**. Pydantic conserva valores de 0 a 180; valores atípicos se normalizan módulo 180. Un eje nulo permanece nulo; no se necesita para nombrar los componentes educativos. |
-| `add` | `number \| null` | NUM LIBRE | `nullable\|numeric\|decimal:0,2\|between:0,30` | Entrada numérica con `step="0.25"`. El SaaS prohíbe negativos (`between:0,30`). Clínicamente oscila entre `+0.75` y `+3.50` D. Si llega `≤ 0.00`, la IA lo coerciona a `None` (sin adición). |
+| `add` | `number \| null` | NUM LIBRE | `nullable\|numeric\|decimal:0,2\|between:0,30` | Entrada numérica con `step="0.25"`. El SaaS prohíbe negativos (`between:0,30`). Clínicamente oscila entre `+0.75` y `+3.50` D. Si llega `≤ 0.00` o `> 30.00`, la IA lo coerciona a `None` (sin adición). |
 | `av_sc` | `string \| null` | DROPDOWN | `nullable\|string\|max:20` | Catálogo cerrado Snellen en pies (`OpticaOptions::av()`): `""` (vacío/guion), `20/10`, `20/15`, `20/20`, `20/25`, `20/30`, `20/40`, `20/50`, `20/60`, `20/70`, `20/80`, `20/100`, `20/120`, `20/160`, `20/200`, `20/400`, `20/600`. |
 | `av_cc` | `string \| null` | DROPDOWN | `nullable\|string\|max:20` | Mismo catálogo exacto de 16 valores Snellen de `av_sc`. |
+
+La API descarta ESF/CIL fuera de ±30.00 D. Si recibe cilindro positivo,
+también transpone la Rx final a cilindro negativo, conservando esfera o eje
+nulos cuando falten. El eje transpuesto usa `((eje + 90) % 180) or 180`;
+la esfera resultante vuelve a comprobarse contra el rango permitido.
 
 *Campos de graduación que NO viajan a la IA:* `dnp` (`decimal:0,2|between:0,100`), `altura_montaje` (`decimal:0,2|between:0,100`).
 
@@ -134,6 +139,11 @@
 
 ---
 
+La API normaliza los textos clínicos conservando límites de línea y colapsando
+espacios dentro de cada línea; los trunca a 500 caracteres, salvo
+`recomendacion_seguimiento`, cuyo límite es 60000. Son límites de recepción de
+`app/schemas.py`; los máximos de captura del SaaS siguen siendo los de la tabla.
+
 ### 1.5 `tipo_lente`
 
 * **Tipo JSON:** `string`
@@ -146,6 +156,12 @@
 
 ---
 
+En la explicación para paciente solo se admite la descripción CPU de cada diseño
+en `app/paciente/contexto.py`. Monofocal no determina uso de lejos o cerca;
+la regla `lente` rechaza atribuirle esas distancias o lectura en la misma frase.
+Los efectos de la graduación y la ayuda de los lentes requieren respaldo en los
+hechos del caso, sin deducir adaptación, materiales ni tratamientos.
+
 ### 1.6 Campos de la Receta que NUNCA viajan a la IA
 
 La receta del SaaS gestiona el expediente y la venta integral en ópticas, pero `IaApiService::buildPayload()` filtra estrictamente para no enviar a la IA:
@@ -172,7 +188,7 @@
 ```
 
 > **Regla para Generación de Payloads Ficticios:**
-> Un payload que únicamente envíe el bloque `paciente` (edad, ocupación, motivo) SIN refracción ni pruebas clínicas **será rechazado inmediatamente con error HTTP 422**. Todo caso de prueba válido debe tener al menos una esfera, cilindro, o prueba clínica registrada. El valor `0.00` en esfera o cilindro es considerado un dato clínico válido (emétrope o sin astigmatismo).
+> Un payload que únicamente envíe el bloque `paciente` (edad, ocupación, motivo) SIN refracción ni pruebas clínicas **será rechazado inmediatamente con error HTTP 422**. Todo caso de prueba válido debe tener al menos un valor en refracción, en `akr.od`/`akr.oi` o en clínica. La metadata AKR sola (`ticket_id`, `taken_at`, `pd`, `vd`, `ker_index`) no satisface `has_clinical_data`. El valor `0.00` en esfera o cilindro es un dato explícito válido; por sí solo no acredita normalidad del examen.
 
 ---
 
@@ -185,7 +201,7 @@
 3. **Aplanado de Motilidad Ocular:**  
    En base de datos los 4 subcampos se guardan con saltos de línea (`\n`). `IaApiService::normalizeSingleLineString` colapsa todos los saltos de línea y múltiples espacios a un solo espacio antes de emitir el JSON.
 4. **Transposición de Cilindro Positivo en AKR:**  
-   El autorrefractómetro físico puede estar configurado en convención plus-cyl (`+cyl`). Si `ia-api` detecta cilindro positivo en `akr.od` o `akr.oi`, aplica automáticamente la transposición óptica (`esf' = esf + cil`, `cil' = -cil`, `eje' = (eje + 90) % 180`) para que las correlaciones clínicas puedan compararlo limpiamente contra la refracción final en convención minus-cyl.
+   El autorrefractómetro físico puede estar configurado en convención plus-cyl (`+cyl`). Si `ia-api` detecta cilindro positivo en `akr.od` o `akr.oi`, aplica automáticamente la transposición óptica (`esf' = esf + cil`, `cil' = -cil`, `eje' = ((eje + 90) % 180) or 180`) para que las correlaciones clínicas puedan compararlo limpiamente contra la refracción final en convención minus-cyl.
 
 ---
 
@@ -195,7 +211,11 @@
 `explicacion_paciente`, `explicacion_paciente_estado`, `salida_version`, `cached`
 booleano y `generacion` con origen/modelo/versiones/hash. El campo clínico válido
 se conserva si falla solo el educativo, con respaldo determinista `plantilla`
-tras redacción y verificación opcionales de la explicación. Detalles y excepción urgente sin origen LLM en
+tras redacción y verificación opcionales de la explicación. Si no hay plantilla
+ni acciones, la explicación puede ser nula con el estado del perfil;
+un fallo de ensamblado devuelve `rechazada` y motivo `error`.
+`PACIENTE_LLM_HABILITADO=false` omite ambas llamadas del paciente y su prosa
+cacheada; entrega respaldo CPU con motivo nulo salvo fallo de ensamblado. Detalles y excepción urgente sin origen LLM en
 [SALIDA_DUAL.md](SALIDA_DUAL.md). Los textos generados/corregidos y la metadata
 de revisión son **destinos**, nunca insumos para la siguiente inferencia.
 
@@ -213,7 +233,7 @@
 
 * **Consumo en Laravel:** Extrae `$response->json('impresion_clinica')`. Si es un string no vacío, lo asigna en tiempo real al componente Livewire:  
   `$this->form->clinica['impresion_clinica_plan'] = $resultado['impresion_clinica'];`
-* **Manejo de Errores:** En caso de error (HTTP 401, 413, 422, 502, 503, 504), la API devuelve `{"detail": "Mensaje de error"}`. Laravel extrae dicho `detail` y lo muestra al optometrista en un banner de alerta para permitirle continuar la captura manual.
+* **Manejo de Errores:** Los errores HTTP 401, 413, 500, 502, 503 y 504 devuelven `{"detail": "Mensaje de error"}`. Un 422 por validación estructural de FastAPI/Pydantic lleva una lista en `detail`; el rechazo por falta de datos clínicos lleva un mensaje. Laravel extrae dicho `detail` y lo muestra al optometrista en un banner de alerta para permitirle continuar la captura manual.
 
 ---
 
@@ -351,7 +371,7 @@
 
 Nunca viajan: nombre, teléfono, folio, fechas exactas, ocupación, motivo de consulta, notas, impresión clínica, correlaciones, patologías, AKR, eje, agudeza visual.
 
-ia-api normaliza `rx_lejos` con la misma lógica ya auditada de la Rx (rangos, transposición de cilindro positivo, `add <= 0` = sin adición): reutiliza `app.schemas.Refraccion`/`GraduacionOjo`.
+ia-api normaliza `rx_lejos` con la misma lógica ya auditada de la Rx (rangos, transposición de cilindro positivo, `add <= 0` o `add > 30` = sin adición): reutiliza `app.schemas.Refraccion`/`GraduacionOjo`.
 
 
 ### Respuesta, estados y motivos
```

## app/paciente/README.md

Fuentes: [app/paciente/integracion.py](../../app/paciente/integracion.py), [app/paciente/servicio.py](../../app/paciente/servicio.py), [app/paciente/validador.py](../../app/paciente/validador.py), [app/paciente/ensamblado.py](../../app/paciente/ensamblado.py).

- Actualizar el estado de integración del núcleo.
- Retirar el rótulo de interfaz futura.
- Distinguir versiones en caché y metadatos efectivamente publicados.
- Documentar la regla revisada, el interruptor vigente y el material regenerable.

```diff
--- app/paciente/README.md (inicio)
+++ app/paciente/README.md
@@ -1,14 +1,14 @@
-# Núcleo de explicación al paciente (W1a)
+# Núcleo de explicación al paciente (integrado en W1b)
 
 W1b integra este paquete desde inferencia, main y registro mediante `integracion.py`. Reutiliza el perfil CPU y la negación W0; no modifica constructores clínicos. La explicación validada no altera el clínico final que recibe.
 
-## Interfaz para W1b
+## Interfaz integrada
 
 `contexto_desde_receta(req, impresion_clinica_final, correlaciones)` recibe correlaciones efectivas como objetos con `nombre` y `texto`. Produce hechos con fuentes canónicas, ocurrencias personales con offsets originales, acciones y el perfil CPU. `construir_contexto(**caso)` permite al adaptador del oráculo construir exactamente los mismos hechos a partir de su contrato: los ids de síntomas aportados en ese contrato son la verdad del oráculo.
 
 `await servicio.generar(contexto, llamar, llegada=..., reloj=..., hay_interactiva_esperando=..., plazos=...)` no adquiere GPU. `llegada` debe preceder a la cola y compartir base monotónica con `reloj`. `llamar(LlamadaPaciente)` ejecuta una única llamada con esquema, opciones, política estricta, timeout, think=False y tarea/etapa declarados; devuelve JSON, `RespuestaEtapa` o `(raw, metadata)`. El adaptador debe cumplir la cancelación de su transporte. El núcleo aplica además `asyncio.wait_for` y revalida el plazo después del conteo de presupuesto.
 
-El resultado contiene `texto`, `estado`, `origen`, `motivo`, `regla` y `acciones_sin_mapear`. W1b debe trasladar las versiones de cada módulo a la clave de caché y los metadatos sin cachear respaldos transitorios. `integracion.py` implementa esas integraciones; el proveedor cuenta intentos físicos.
+El resultado contiene `texto`, `estado`, `origen`, `motivo`, `regla` y `acciones_sin_mapear`. `integracion.py` incluye en la clave de caché las versiones de servicio, contexto, prompt, esquema, glosario, validador, verificador, acciones y respaldo, además del perfil; la respuesta publica `paciente_version`. No se cachean respaldos transitorios. El proveedor cuenta intentos físicos.
 
 ## Decisiones locales
 
@@ -20,6 +20,23 @@
 - Ante más de 2000 puntos de código se elimina la prosa completa y se intenta solo el bloque de acciones. Si las acciones por sí solas exceden el límite, no existe una salida que cumpla simultáneamente integridad y longitud. La guarda extrema devuelve texto nulo, estado rechazada y motivo error, conservando el clínico. Esta decisión fue aceptada por Claude para W1b; no se trunca ninguna acción.
 - No hay máximo finito de longitud del clínico final recibido en el contrato del núcleo. La medición de estrés de 60000 caracteres y todas las variantes es una prueba de rechazo de presupuesto, no la afirmación de un máximo posible ni de una combinación clínica realizable.
 
+## Regla `lente` e interruptor
+
+El lente se describe con `contexto.LENTES`. Monofocal no determina una distancia
+de uso: `validar` rechaza lejos, cerca o lectura en la misma frase que monofocal.
+Sí se permiten efectos de la graduación y ayuda de los lentes sustentados por
+los hechos del caso, sujetos a las demás reglas; no se infieren adaptación,
+materiales ni tratamientos.
+
+`PACIENTE_LLM_HABILITADO` vale `true` por omisión. Con `false`, la integración
+omite redacción/verificación y no recupera prosa paciente cacheada; devuelve
+acciones + plantilla CPU, o el estado del perfil si no hay texto. El motivo es
+nulo salvo fallo de ensamblado (`rechazada`/`error`). El clínico sigue su flujo.
+
+El [material para el dueño](../../auditoria/2026-11-08-explicacion-paciente/02-catalogo-y-prompts-para-revision.md)
+se regenera desde el código con `scripts/catalogo_paciente.py`; incluye acciones,
+glosario, system prompts, descripciones CPU del lente y versiones.
+
 ## Oráculo independiente
 
 `tests/test_paciente_corpus.py` consume el corpus sin excepciones ni xfail. Tras el arbitraje independiente pasa 225/225. W1b no edita esos archivos. La fidelidad de paráfrasis sigue dependiendo del verificador y de la revisión clínica; los filtros léxicos no son una prueba semántica.
```

## COMO_AGREGAR_UNA_TAREA.md

Fuentes: [app/tareas/registro.py](../../app/tareas/registro.py), [app/tareas/definiciones/explicacion_paciente.py](../../app/tareas/definiciones/explicacion_paciente.py), [app/paciente/integracion.py](../../app/paciente/integracion.py).

- Distinguir las llamadas declaradas de las ejecutadas con el interruptor apagado.

```diff
--- COMO_AGREGAR_UNA_TAREA.md (inicio)
+++ COMO_AGREGAR_UNA_TAREA.md
@@ -118,3 +118,8 @@
 recuperarlo ante errores o timeout exterior cuando el contrato exija conservar
 la salida del padre. Versionar e independizar cachés y no guardar respaldos
 transitorios. Probar cola, cancelación, aciertos parciales y errores por HTTP.
+
+En la hija existente, `PACIENTE_LLM_HABILITADO=false` omite sus dos llamadas y
+la recuperación de prosa paciente cacheada; devuelve respaldo CPU. No elimina
+las llamadas declaradas en `/v1/tareas`: el descubrimiento conserva la ficha.
+El motivo es nulo salvo fallo de ensamblado (`rechazada`/`error`).
```

## PIPELINE_LLM.md

Fuentes: [app/main.py](../../app/main.py), [app/schemas.py](../../app/schemas.py), [app/inference.py](../../app/inference.py), [app/cache.py](../../app/cache.py), [app/providers/ollama.py](../../app/providers/ollama.py), [app/tareas/presupuesto.py](../../app/tareas/presupuesto.py), [app/correlaciones/registry.py](../../app/correlaciones/registry.py), [app/correlaciones/refraccion_utils.py](../../app/correlaciones/refraccion_utils.py), [app/correlaciones/queratometria.py](../../app/correlaciones/queratometria.py), [app/correlaciones/corneal.py](../../app/correlaciones/corneal.py).

- Corregir la llamada clínica vigente a build_system_prompt.
- Sustituir el semáforo retirado por el planificador vigente.
- Distinguir coerción tolerante y errores estructurales 422.
- Incluir salida_version en el schema raíz.
- Corregir ocupación: máximo 120 y nulabilidad.
- Corregir motivo: máximo 1000 y nulabilidad.
- Distinguir captura y rango efectivo de esfera ±30.
- Corregir rango del cilindro y transposición de Rx.
- Alinear la validación de eje con el diccionario.
- Completar el límite superior de ADD.
- Corregir el tratamiento de AV sub-Snellen.
- Corregir el rango de PD.
- Corregir transposición, eje, nulos y nombres actuales de reglas AKR.
- Corregir el rango de cilindro corneal.
- No asumir que cover test siempre está documentado.
- Retirar el default inventado de cover test.
- Corregir el límite de recomendación de seguimiento.
- Corregir conservación de líneas y límites de textos clínicos.
- Alinear la nota repetida sobre validación de ejes.
- Corregir máximo de edad.
- Corregir rangos refractivos del resumen.
- Distinguir límites de recepción y dropdowns.
- Alinear el resumen de ADD.
- Documentar los filtros sub-Snellen del resumen.
- Precisar datos clínicos mínimos de AKR.
- Actualizar el mapa de módulos clínicos.
- Corregir el helper de AV sub-Snellen.
- Retirar categorías de gravedad eliminadas de _av_categoria.
- Corregir la fórmula de equivalente esférico.
- No imputar cero a un componente refractivo ausente.
- Corregir helpers, selectores y cuatro reglas corneales sin inferir diagnósticos.
- Corregir el encabezado vigente del bloque AKR.
- Corregir la serialización independiente de AKR/Rx/queratometría.
- Precisar que max_retries cuenta intentos totales.
- Distinguir heurística preemptiva y verificación completa por envío.
- Corregir la sección DEBUG.
- Corregir el alcance del retry tras postprocesado vacío.
- Retirar la reducción de oraciones que ya no se ejecuta.
- Distinguir clave clínica compartida, base_hash_api y caché paciente.
- Corregir eviction clínica a LRU.
- Alinear la descripción final de logs DEBUG.
- Corregir la afirmación de contenido clínico en el resumen DEBUG.
- Alinear el interruptor, descubrimiento y regla revisada de lente.
- Precisar el retorno de run_inference en cada modo.
- Corregir el diagrama de las llamadas reales de postprocesado.
- Alinear el orden de operaciones de seguimiento con _ensure_follow_up_last.
- Precisar que el seguimiento puede normalizarse o suprimirse.

```diff
--- PIPELINE_LLM.md (inicio)
+++ PIPELINE_LLM.md
@@ -129,7 +129,7 @@
   v
 run_inference(req, httpx_client)
   |
-  |- build_system_prompt(effective_max)
+  |- build_system_prompt()
   |- build_user_prompt(req)
   |    |- serializa contexto, refraccion, AKR y hallazgos clinicos
   |    |- evaluar_correlaciones(req)
@@ -202,7 +202,7 @@
 El sistema usa:
 
 - `settings.max_concurrent = 1` (`MAX_CONCURRENT`)
-- un semaforo global `asyncio.Semaphore`
+- el planificador `GPUScheduler`, con colas FIFO por prioridad y un `asyncio.Lock`
 - una cola maxima de espera de `5` requests (`MAX_QUEUE_SIZE`)
 - `settings.queue_wait_timeout = 30.0` (`QUEUE_WAIT_TIMEOUT`; `<= 0` = espera sin limite)
 
@@ -239,7 +239,7 @@
 
 > **Fuente de verdad:** el SaaS (Laravel) es la unica fuente que construye el payload. Todos los tipos, rangos y enums aqui listados reflejan lo que el SaaS realmente puede enviar (catalogos en `OpticaOptions` + `RecetaFormOptions`, validacion en `RecetaValidationRules`, construccion en `IaApiService::buildPayload`). El mapeo campo-por-campo esta en [DICCIONARIO_DATOS_RECETA.md](DICCIONARIO_DATOS_RECETA.md).
 
-> **Politica de validacion: COERCION TOLERANTE (no rechazo).** El SaaS invoca este endpoint con el estado **crudo** del formulario, SIN pasar por `RecetaValidationRules` (el boton "Generar con IA" en `FormEditor::generateImpresionClinica` arma `toPayload()` y lo envia antes de guardar/validar). Por eso el schema **no** responde `422` ante un valor fuera de catalogo en un campo secundario: lo **descarta** (`None`) o lo **normaliza**, y lo registra en el log. Solo se responde `422` cuando no hay ningun dato clinico util (ver seccion 5). Esto evita que un eje de 190 o una K corrupta tumben toda la generacion.
+> **Politica de validacion: COERCION TOLERANTE (no rechazo).** El SaaS invoca este endpoint con el estado **crudo** del formulario, SIN pasar por `RecetaValidationRules` (el boton "Generar con IA" en `FormEditor::generateImpresionClinica` arma `toPayload()` y lo envia antes de guardar/validar). Por eso el schema **no** responde `422` ante un valor fuera de catalogo en un campo secundario: lo **descarta** (`None`) o lo **normaliza**, y lo registra en el log. También hay `422` ante errores de estructura/tipos o una `salida_version` inválida; la validación mínima rechaza solicitudes sin datos clínicos útiles (sección 5). Esto evita que un eje de 190 o una K corrupta tumben toda la generacion.
 
 ### Campos de primer nivel
 
@@ -251,14 +251,15 @@
 | `akr` | `AkrSnapshot` | Medicion del autorrefractometro en OD y OI, metadata de la sesion (PD, VD, indice queratometrico) y, desde 2026-07, los valores de queratometria (K1, K2, K promedio, cilindro corneal) capturados en el mismo ticket. |
 | `clinica` | `DatosClinica` | Hallazgos de examen clinico. |
 | `tipo_lente` | `str \| None` | Diseno de lente prescrito. |
+| `salida_version` | `Literal["clinica-v1", "clinica-paciente-v1"]` | Omitido usa `clinica-v1`; nulo u otro valor produce 422. |
 
 ### ContextoPaciente
 
 | Campo | Tipo | Restriccion real del SaaS |
 |---|---|---|
 | `edad` | `int \| None` | Calculada desde `paciente.fecha_nacimiento` con `Carbon::parse(...)->age`. Si no hay fecha de nacimiento, llega `None`. |
-| `ocupacion` | `str \| None` | `required\|max:255` en el SaaS. En la practica siempre llega con valor (nunca None). |
-| `motivo_consulta` | `str \| None` | `required\|max:255` en el SaaS. En la practica siempre llega con valor (nunca None). |
+| `ocupacion` | `str \| None` | Captura SaaS: `required\|max:120`. La API admite ausencia/nulo y trunca a 120 caracteres. |
+| `motivo_consulta` | `str \| None` | Captura SaaS: `required\|max:1000`. La API admite ausencia/nulo y trunca a 1000 caracteres, conservando límites de línea. |
 
 El SaaS **no envia** `nombre`, `telefono` ni `fecha_nacimiento`.
 
@@ -268,11 +269,11 @@
 
 | Campo | Tipo | Restriccion real del SaaS |
 |---|---|---|
-| `esfera` | `float \| None` | Dropdown `OpticaOptions::esfera`: `+20.00`..`-20.00` paso `0.25`. Fuera de `±20.00` → se descarta (`None`). Default `0.00`, sin opcion vacia (en `create` siempre llega valor) |
-| `cilindro` | `float \| None` | Dropdown `OpticaOptions::cilindro`: `0.00`..`-8.00` paso `0.25`, **siempre ≤ 0** (convencion negativa). Fuera de `\|8.00\|` → `None`. La Rx final **no** se transpone (el dropdown ya garantiza minus-cyl) |
-| `eje` | `int \| None` | Input libre; el SaaS **no** valida rango. El eje es ciclico: fuera de `0..180` se **normaliza modulo 180** (`225`→`45`), no se rechaza |
-| `add` | `float \| None` | Input libre. `add ≤ 0` (tecleado `0` o negativo) → `None`: "sin adicion" no cuenta como adicion prescrita |
-| `av_sc` | `str \| None` | Dropdown `OpticaOptions::av` (16 valores): `20/10`, `20/15`, `20/20`, `20/25`, `20/30`, `20/40`, `20/50`, `20/60`, `20/70`, `20/80`, `20/100`, `20/120`, `20/160`, `20/200`, `20/400`, `20/600`. El schema **canoniza** `20/xx` (colapsa espacios); notaciones legacy no-Snellen se conservan sin disparar |
+| `esfera` | `float \| None` | Dropdown `+20.00`..`-20.00`, paso `0.25`; la API admite ±30.00 D. Fuera de ese rango → `None`, también después de transponer. Default de captura `0.00`; ausencia en API permanece nula. |
+| `cilindro` | `float \| None` | Dropdown `0.00`..`-8.00`, paso `0.25`; la API admite ±30.00 D y descarta fuera de ese rango. La Rx final con cilindro positivo se transpone a negativo. |
+| `eje` | `int \| None` | Captura SaaS: `between:0,180`. La API conserva ese rango y normaliza los valores atípicos módulo 180 (`225`→`45`); nulo permanece nulo. |
+| `add` | `float \| None` | Input libre, `between:0,30` en SaaS. La API convierte `add ≤ 0` o `add > 30` a `None`. |
+| `av_sc` | `str \| None` | Dropdown `OpticaOptions::av` (16 valores): `20/10`, `20/15`, `20/20`, `20/25`, `20/30`, `20/40`, `20/50`, `20/60`, `20/70`, `20/80`, `20/100`, `20/120`, `20/160`, `20/200`, `20/400`, `20/600`. El schema **canoniza** `20/xx` (colapsa espacios); notaciones legacy no-Snellen se conservan; las categorías sub-Snellen reconocidas también pueden activar reglas de AV. |
 | `av_cc` | `str \| None` | Mismos valores que `av_sc` (tambien canonizados) |
 
 ### AkrSnapshot — metadata de sesion
@@ -282,7 +283,7 @@
 | Campo | Tipo | Restriccion real del SaaS |
 |---|---|---|
 | `ticket_id` | `int \| None` | Referencia al ticket de autorrefractometro/queratometro origen. `nullable\|integer\|exists:akr_tickets,id` |
-| `pd` | `float \| None` | Distancia interpupilar. `nullable\|numeric`, sin rango declarado |
+| `pd` | `float \| None` | Distancia interpupilar; `0..100`, fuera de rango → `None`. |
 | `vd` | `float \| None` | Distancia al vertice. `between:0,30`; fuera de rango → `None` |
 | `ker_index` | `float \| None` | Indice queratometrico usado por el equipo para convertir mm↔D. `between:1.3,1.4`; fuera de rango → `None` |
 
@@ -292,7 +293,7 @@
 
 Se usa en `akr.od` y `akr.oi`. Es un snapshot del autorrefractometro; **no** incluye `add`, `av_sc` ni `av_cc`. `pd` existe pero a nivel de sesion (`akr.pd`), no por ojo.
 
-> **Transposicion del AKR (solo AKR, no la Rx).** La convencion de cilindro del AKR la fija el **dispositivo** y puede ser plus-cyl. Si `akr.od/oi.cilindro > 0`, el schema transpone la lectura a convencion negativa (`esf' = esf + cil`, `cil' = -cil`, `eje' = (eje+90) % 180`) para que la comparacion esfera-a-esfera AR vs Rx (`ar_rx_espasmo/cambio/variabilidad`) quede en la misma convencion que la Rx final. La **Rx final NO se transpone**: su dropdown ya garantiza minus-cyl y transponerla alteraria el piso de esfera de `hipermetropia_alta`.
+> **Transposición de AKR y Rx final.** Ambos schemas convierten cilindro positivo a negativo: `esf' = esf + cil`, `cil' = -cil`, `eje' = ((eje + 90) % 180) or 180`. Si falta esfera o eje, se conserva nulo. La Rx final verifica además el rango de esfera después de la transposición. Las reglas AKR activas son `ar_rx_variabilidad_inespecifica` y `ar_detecta_astigmatismo_no_prescrito`; describen registros sin acreditar simultaneidad ni una causa clínica.
 
 Desde 2026-07 el SaaS captura tambien la prueba de queratometria en el mismo ticket AKR (dato nuevo, antes no se enviaba):
 
@@ -309,7 +310,7 @@
 | `k2_eje` | `int \| None` | Eje de K2. Ciclico: normalizado modulo 180 |
 | `k_promedio_d` | `float \| None` | K promedio en dioptrias. `25..80`; fuera → `None` |
 | `k_promedio_mm` | `float \| None` | K promedio en radio de curvatura. `4..12`; fuera → `None` |
-| `k_cilindro` | `float \| None` | Cilindro corneal (K2 - K1 con signo). `-20..20`; fuera → `None` |
+| `k_cilindro` | `float \| None` | Cilindro corneal (K2 - K1 con signo). `-30..30`; fuera → `None` |
 | `k_cilindro_eje` | `int \| None` | Eje del cilindro corneal. Ciclico: normalizado modulo 180 |
 
 ### DatosClinica
@@ -324,14 +325,14 @@
 | `fondo_de_ojo` | `str \| None` | Texto libre `max:255` |
 | `grid_de_amsler` | `str \| None` | Texto libre `max:255` |
 | `ojo_seco_but_seg` | `int \| None` | Dropdown `1..15` (segundos). Fuera → `None` |
-| `cover_test` | `str \| None` | `max:255`. **La UI compone siempre** `"OD: {tipo_od}[ y {sub_od}] \| OI: {tipo_oi}[ y {sub_oi}]"`. `tipo ∈ {Orto, Endo, Exo, Hiper, Hipo}` (radio, default `Orto`); `sub ∈ {Tropia, Foria}` (radio **SIN default, opcional**). Ejemplos reales: `"OD: Orto \| OI: Exo y Foria"`, `"OD: Endo y Tropia \| OI: Orto"`, y **tipo sin sub**: `"OD: Exo \| OI: Orto"`. La capa de correlaciones parsea el formato canonico y dispara tambien con el tipo sin clasificar (ver seccion 6). **No** se envian cadenas como `"exoforia"` unidas. |
+| `cover_test` | `str \| None` | `max:255`. **La UI compone, si se captura la prueba,** `"OD: {tipo_od}[ y {sub_od}] \| OI: {tipo_oi}[ y {sub_oi}]"`. `tipo ∈ {Orto, Endo, Exo, Hiper, Hipo}` (radio; si no se toca en receta nueva viaja nulo); `sub ∈ {Tropia, Foria}` (radio **SIN default, opcional**). Ejemplos reales: `"OD: Orto \| OI: Exo y Foria"`, `"OD: Endo y Tropia \| OI: Orto"`, y **tipo sin sub**: `"OD: Exo \| OI: Orto"`. La capa de correlaciones parsea el formato canonico y dispara tambien con el tipo sin clasificar (ver seccion 6). **No** se envian cadenas como `"exoforia"` unidas. |
 | `ppc_cm` | `int \| None` | Dropdown `1..15` (cm). Fuera → `None` |
-| `recomendacion_seguimiento` | `str \| None` | Texto libre (TEXT en DB, sin limite duro) |
+| `recomendacion_seguimiento` | `str \| None` | Texto libre (TEXT en DB); la API trunca a 60000 caracteres |
 
 ### Normalizaciones Pydantic relevantes
 
-- `motilidad_ocular`: colapsa saltos de linea y espacios duplicados (el SaaS ya envia una sola linea; la normalizacion es defensiva).
-- `cover_test`: reemplaza `" - "` por `" y "` y colapsa espacios. En la practica **el SaaS ya envia `" y "`** como separador entre tipo y subtipo; este normalize es defensivo.
+- Los textos clínicos conservan límites de línea, colapsan espacios dentro de cada línea y se truncan a 500 caracteres; `recomendacion_seguimiento` admite 60000. El prompt clínico aplana estos textos al serializarlos.
+- `cover_test` reemplaza además `" - "` por `" y "`. El SaaS ya envía `" y "`; la normalización es defensiva.
 
 ### Campos que existen en la receta del SaaS y que NO llegan
 
@@ -351,19 +352,17 @@
 
 - `refraccion.od/oi.eje` y todos los ejes de AKR (`eje`, `k1_eje`, `k2_eje`,
   `k_cilindro_eje`): el eje es **ciclico**; fuera de `0..180` se normaliza modulo 180
-  (`225`→`45`). El input del SaaS no valida rango, asi que normalizar (no rechazar) es
-  lo correcto para disparar `astig_oblicuo` con el eje real.
-- `paciente.edad`: `0..120`; fuera → `None` (comportamiento conservador de las reglas
+  (`225`→`45`). El contrato SaaS valida `0..180`; la API tolera valores atípicos.
+- `paciente.edad`: `0..125`; fuera → `None` (comportamiento conservador de las reglas
   que dependen de la edad).
-- `esfera` (`±20.00`), `cilindro` (`\|8.00\|`), `ojo_seco_but_seg`/`ppc_cm` (`1..15`),
+- `esfera` (`±30.00`), `cilindro` (`±30.00`), `ojo_seco_but_seg`/`ppc_cm` (`1..15`),
   `vd` (`0..30`), `ker_index` (`1.3..1.4`), K en dioptrias (`25..80`) y en mm (`4..12`):
-  fuera de catalogo → `None`. Estos rangos son los limites de los dropdowns/dispositivo;
-  un valor fuera es dato corrupto que no debe contar como hallazgo.
-- `add ≤ 0` → `None`: el input de add es libre y un `0` tecleado no es una adicion
+  fuera del rango de recepción → `None`. Los límites de esfera/cilindro admitidos por la API son más amplios que los dropdowns de captura.
+- `add ≤ 0` o `add > 30` → `None`: el input de add es libre y un `0` tecleado no es una adicion
   prescrita. Las correlaciones de presbicia por edad/ADD se retiraron el 22 de septiembre de 2026; ADD no acredita ese diagnóstico.
 - **Transposicion de AKR y Rx final**: ambos schemas convierten cilindro positivo a negativo y conservan esfera/eje nulos cuando faltan.
 - `av_sc` / `av_cc` se **canonizan**: `" 20 / 40 "` → `"20/40"`. Notaciones no-Snellen
-  legacy (p. ej. "cuenta dedos") se conservan sin disparar AV.
+  legacy se conservan; CD, MM, PL y NPL reconocidos usan centinelas internos para filtros de AV.
 - `uso_pantallas` es enum cerrado (`lt2`/`btw2_6`/`gt6`); un valor fuera → `None`.
 - `tipo_lente` se normaliza (espacio) pero **no** se cierra a enum: el catalogo canonico
   del SaaS es `monofocal | bifocal_blended | progresivo | flat_top`, pero puede crecer
@@ -385,7 +384,7 @@
 Antes de inferir, `has_clinical_data(req)` valida que exista al menos un valor no nulo dentro de:
 
 - `req.refraccion`
-- `req.akr`
+- `req.akr.od` o `req.akr.oi` (la metadata AKR sola no basta)
 - `req.clinica`
 
 No basta con enviar solo:
@@ -406,9 +405,9 @@
 La logica esta particionada por dominio clinico en el paquete
 [`app/correlaciones/`](app/correlaciones/):
 
-- Dominios (10 modulos): `fondo_de_ojo`, `refractivas`, `akr`, `corneal`,
-  `anexos_cristalino`, `pupilas_motilidad`, `campos_amsler`, `binocularidad`,
-  `superficie_ocular`, `contexto`.
+- Dominios: `fondo_de_ojo`, `refractivas`, `akr`, `corneal`,
+  `anexos_cristalino`, `segmento_anterior`, `pupilas_motilidad`, `motilidad`,
+  `sintomas_agudos`, `campos_amsler`, `binocularidad`, `superficie_ocular`, `contexto`.
 - Helpers compartidos: `base` (memoizacion + tipo `Correlacion`), `texto`
   (normalizacion y matching), `refraccion_utils` (Snellen, equivalente esferico),
   `queratometria` (lectura corneal).
@@ -451,7 +450,8 @@
 
 Extrae el denominador Snellen equivalente en pie a partir de las tres notaciones que
 emiten los frontends: pie (`20/40`), metrica (`6/12`) y decimal (`0.5` / `0,5`).
-Notaciones no interpretables (CF, MM, cuenta dedos) devuelven `None`.
+Las categorías sub-Snellen CD, MM, PL y NPL reconocidas usan centinelas internos
+para ordenamiento, sin equivalencia Snellen medida; las no interpretables devuelven `None`.
 
 #### `_av_es_limitada(av)`
 
@@ -463,30 +463,34 @@
 
 #### `_av_categoria(av)`
 
-Clasifica la reduccion de AV con correccion:
-
-- `26-30`: leve
-- `31-50`: moderada
-- `51-100`: marcada
-- `>100`: severa
+Devuelve `AV con correccion registrada inferior a 20/25; pendiente de verificacion`
+si el denominador supera 25, o `None` en los demás casos. No clasifica gravedad
+ni discapacidad.
 
 #### `_equivalente_esferico(esf, cil)`
 
 Calcula:
 
 ```python
-esfera + (cilindro or 0.0) / 2.0
-```
-
+esfera + cilindro / 2.0
+```
+
+Requiere ambos componentes registrados; si falta uno devuelve `None`.
 Se usa para anisometropia, miopia magna e hipermetropia alta.
 
 #### Helpers de queratometria
 
-Desde la integracion de datos de queratometria (`akr.od`/`akr.oi.k1_d`, `k2_d`, `k_promedio_d`, `k_cilindro`, `k_cilindro_eje`), el modulo agrega helpers para leer y clasificar esos valores: `_k_values`, `_has_keratometry`, `_k_max`, `_corneal_cyl_abs`, `_keratometry_axis`, `_keratometry_supports_astigmatism`, `_keratometry_axis_matches` y `_keratometry_suggests_corneal_irregularity` (curvatura corneal ≥ 47.20D como umbral de sospecha, ≥ 48.70D o cilindro corneal ≥ 4.00D como umbral de ectasia/irregularidad franca). Estos helpers alimentan las correlaciones refractivas y de AR como confirmacion/matiz, y ademas **disparan** las dos correlaciones del modulo `corneal.py` (`queratocono_ectasia_sospecha`, `astigmatismo_corneal_vs_refractivo`), unica excepcion a la regla "la queratometria no dispara".
-
-**Estado:** integrada. El detalle clinico de como cada una de las 47 correlaciones
-usa la queratometria (confirmacion/matiz en las refractivas, disparador propio en las
-dos corneales) esta documentado por correlacion en [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).
+Los helpers `_k_values`, `_has_keratometry`, `_k_steepest_d`, `_corneal_cyl_abs`,
+`_keratometry_axis`, `_keratometry_supports_astigmatism`, `_keratometry_axis_matches`
+y `_keratometry_suggests_corneal_irregularity` leen valores registrados sin
+establecer anatomía ni etiología. El selector de valores elevados exige K ≥ 48.70 D,
+o K ≥ 47.20 D junto con cilindro corneal ≥ 1.50 D, o cilindro corneal ≥ 4.00 D;
+rechaza queratometría contradictoria. Son criterios operativos de revisión.
+`corneal.py` contiene `queratocono_ectasia_sospecha`,
+`astigmatismo_corneal_vs_refractivo`, `cornea_plana_extrema` y
+`queratometria_asimetrica_interocular`. La Rx y la queratometría aportan registros
+independientes; no prueban un mecanismo refractivo o lenticular ni una causa de AV.
+El detalle está en [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).
 
 ### Matching de texto libre
 
@@ -615,7 +619,7 @@
 
 1. `Contexto del paciente`
 2. `Refraccion final`
-3. `Correlacion AKR/queratometria vs refraccion final`
+3. `Datos AKR/queratometria y refraccion final` (mediciones registradas sin inferir ajuste, causa ni identidad temporal)
 4. Bloques clinicos sueltos
 5. `Diseno de lente prescrito`
 6. `Correlaciones clinicas aplicables (hechos pre-evaluados del caso)`
@@ -660,7 +664,8 @@
 - `AKR OI: ...` / `Rx final OI: ...`
 - `Queratometria OI: ...`
 
-A diferencia de `AKR OD/OI` y `Rx final OD/OI` (que solo aparecen juntos), la linea `Queratometria {OD|OI}` se agrega de forma independiente por ojo si ese ojo tiene algun valor de K.
+Dentro del bloque, las líneas `AKR OD/OI`, `Rx final OD/OI` y
+`Queratometria OD/OI` se agregan independientemente si cada una tiene datos.
 
 #### Hallazgos clinicos sueltos
 
@@ -738,7 +743,8 @@
 
 La funcion central es `run_inference(payload, client)` en `app/inference.py`:
 construye los prompts, valida el contexto de forma preemptiva, llama a Ollama y
-aplica el postprocesado + guardarrailes. Devuelve el parrafo final.
+aplica el postprocesado + guardarraíles. En `clinica-v1` devuelve el párrafo;
+en dual publica el punto de control y devuelve `DualInferenceResult` tras la rama paciente.
 
 ### Cliente Ollama (`app/providers/ollama.py`)
 
@@ -756,7 +762,7 @@
 | `num_predict` | `1024` | Elimina el truncado (`done_reason=length`) en casos con 4+ correlaciones activas |
 | `num_ctx` | `8192` | El system prompt afinado pesa ~1595 tok y el payload maximo del diccionario ~3300 tok: con `num_predict=1024` no cabia en 4096 (daba `413`). Medido en la 3070 Ti: 4096→8192 solo sube el footprint 0.2 GB |
 | `seed` | `42` | Reproducibilidad (`-1` para variabilidad) |
-| `ollama_max_retries` | `2` | Reintentos ante timeout / respuesta vacia / 5xx |
+| `ollama_max_retries` | `2` | Número total de intentos del proveedor; reintenta ante ReadTimeout, contenido vacío/inválido o HTTP 500/503. |
 
 Cada valor esta comentado con su justificacion (incluidas las mediciones de VRAM en
 la 3070 Ti) en [app/config.py](app/config.py).
@@ -775,13 +781,15 @@
 `est_input` se estima con un heuristico calibrado de ~3.3 caracteres por token (español con
 tokenizer Qwen); el conteo real lo devuelve Ollama en `prompt_eval_count` despues de
 la inferencia. Si se excede, se lanza `ValueError` con prefijo `context_overflow:` →
-`413` en el cliente.
+`413` en el cliente. Después, el proveedor verifica también el presupuesto
+completo con roles y envoltura, la política activa y el contexto efectivo
+`min(OLLAMA_NUM_CTX, LIMITE_CONTEXTO_TOKENS, 8192)`; también se comprueba al
+reenviar con más salida. Véase «Registro y presupuesto de tareas».
 
 ### Logging del prompt renderizado
 
-Con `LOG_LEVEL=DEBUG`, `run_inference` imprime el system prompt y el user prompt
-completos (con conteo de caracteres y tokens estimados) antes de cada inferencia.
-Es la forma mas rapida de depurar por que el parrafo dice lo que dice.
+Con `LOG_LEVEL=DEBUG`, `run_inference` registra solo tamaños de system/user
+en caracteres y estimaciones de tokens, sin imprimir los prompts completos.
 
 ### Monitoreo de contexto (Ollama)
 
@@ -797,11 +805,13 @@
 
 ## 10. Postprocesamiento del output
 
-El texto crudo del modelo pasa por tres etapas, en este orden:
-
-```
-_postprocess(raw)  →  clean_impresion(text)  →  _ensure_follow_up_last(text, recomendacion)
-   (inference.py)       (prompt_builder.py)          (inference.py, seccion 11)
+El texto crudo del modelo pasa por limpieza estructural, depuración, filtro de
+fidelidad, preservación de urgencias y seguimiento, en este orden:
+
+```
+_postprocess(raw) → clean_impresion(text) → _purgar_no_sustentado(text, clinical_prompt)
+  → _ensure_emergency_preserved(text, payload)
+  → _ensure_follow_up_last(text, recomendacion, payload=payload)
 ```
 
 ### Etapa 1 — `_postprocess` (limpieza estructural)
@@ -817,7 +827,8 @@
 6. une todo en un solo parrafo;
 7. recompone oraciones con proteccion de abreviaturas;
 8. asegura punto final;
-9. si el resultado queda vacio, lanza `ValueError` (que dispara el retry del cliente Ollama).
+9. si el resultado queda vacío, lanza `ValueError` después de la llamada al proveedor;
+   no dispara su retry. En dual se convierte en `GeneracionIncompletaError`.
 
 #### Abreviaturas protegidas
 
@@ -865,21 +876,22 @@
 
 La recomendacion en `clinica.recomendacion_seguimiento` no se manda al modelo como parte del parrafo final. En su lugar:
 
-- el system prompt reserva espacio reduciendo el limite de oraciones;
+- `run_inference` usa `build_system_prompt()` con `settings.max_sentences`, sin reducirlo por seguimiento;
 - despues de la inferencia, `_ensure_follow_up_last()` la agrega al final.
 
 Esta funcion:
 
-1. normaliza la recomendacion;
-2. elimina una ultima oracion identica si el modelo ya la incluyo;
-3. elimina una ultima oracion muy parecida si la similitud es `>= 0.70`;
-4. agrega la recomendacion como ultima oracion.
+1. ante una urgencia, suprime el seguimiento rutinario incompatible o sus oraciones incompatibles;
+2. normaliza el seguimiento restante y asegura punto final;
+3. elimina una última oración idéntica si el modelo ya la incluyó;
+4. elimina una última oración muy parecida si la similitud es `>= 0.70`;
+5. agrega el seguimiento restante al final, si existe.
 
 Esto garantiza:
 
-- texto final exacto;
-- posicion final;
-- menos riesgo de parafrasis no deseadas.
+- texto del seguimiento normalizado y compatible con las urgencias activas;
+- posición final, si queda seguimiento;
+- menos riesgo de paráfrasis no deseadas.
 
 ---
 
@@ -904,13 +916,16 @@
 Detalles importantes:
 
 - `receta_id` no afecta el cache;
-- como la clave usa `payload.model_dump(mode="json")` completo, cualquier campo nuevo del schema (incluyendo los de queratometria) participa automaticamente en la clave sin cambios en `cache.py`;
+- `salida_version` participa en la clave. Para compartir la caché clínica, el handler dual usa una copia con `salida_version="clinica-v1"`; la caché paciente es independiente (véase SALIDA_DUAL.md);
+- el `base_hash_api` dual se calcula con el request dual y añade perfil, prompt, pipeline y opciones clínicas; no es la clave paciente;
+- los demás campos nuevos del schema participan automáticamente en la clave, salvo `receta_id`;
 - si cambia `OLLAMA_MODEL`, cambia la clave (no se sirven respuestas generadas por otro modelo);
 - si el caso tiene o no recomendacion, cambia la clave.
 
 ### Politica de eviction
 
-Si el cache esta lleno y entra una nueva clave, se elimina la entrada mas antigua.
+Si el cache está lleno y entra una nueva clave, se elimina la menos recientemente
+usada; cada acierto mueve su entrada al final.
 
 ---
 
@@ -1062,7 +1077,7 @@
    `CF-Connecting-IP` / `X-Forwarded-For` (detras de Cloudflare Tunnel el socket
    siempre es local).
 2. `Payload recibido [sid]: edad=45 rx=OD+OI akr=OD clinica=[fondo_de_ojo, ...]`
-   — QUE campos vienen, no su contenido (el texto clinico solo aparece en DEBUG).
+   — QUÉ campos vienen, no el contenido de sus textos.
 3. `Correlaciones activadas [sid] (n): [...]`.
 4. Cache hit/miss, cola (`queued`/`acquired`/`released`).
 5. Metricas de Ollama: tokens de entrada/salida, tok/s, duracion total y de
@@ -1079,8 +1094,8 @@
 el limite configurado) y cualquier excepcion no manejada con traceback completo
 en `logs/errors.log`.
 
-Con `LOG_LEVEL=DEBUG` se agrega el system/user prompt completo renderizado y el
-margen real de contexto que reporta Ollama. El logger `httpx` esta silenciado a
+Con `LOG_LEVEL=DEBUG` se agregan tamaños de system/user y el margen real de
+contexto que reporta Ollama; no se registran los prompts completos. El logger `httpx` esta silenciado a
 WARNING (duplicaba cada POST).
 
 La guia de conexion y debugging del despliegue completo (SaaS + Cloudflare +
@@ -1150,7 +1165,12 @@
 por omisión es 85 s. Redacción 15 s y verificación 5 s, ventanas mínimas 1 s y
 0.5 s, reserva 0.1 s; se aplican por tiempo restante. Antes de cada etapa se cede
 si espera otra interactiva (`PACIENTE_OMITIR_SI_ESPERA=true`). El interruptor
-`PACIENTE_LLM_HABILITADO=false` devuelve respaldo sin llamadas del paciente.
+`PACIENTE_LLM_HABILITADO=false` devuelve respaldo sin llamadas del paciente ni
+recuperación de su prosa cacheada; motivo nulo salvo fallo de ensamblado
+(`rechazada`/`error`). Las llamadas declaradas en `/v1/tareas` se conservan.
+La regla `lente` solo permite la descripción CPU del diseño: monofocal no
+determina lejos, cerca o lectura. Los efectos de la graduación y ayuda de los
+lentes se permiten cuando los hechos los sustentan.
 El modo clínico histórico mantiene su timeout actual.
 
 El clínico cacheado permite reintentar solo el paciente con turno interactivo;
```

