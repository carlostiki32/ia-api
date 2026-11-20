# Contrato normativo `seguimiento-whatsapp-v1` (ia-api ↔ Laravel `optica`)

Fecha: 2026-11-07 · Autor: Claude (orquestador). **Consenso: Codex, Antigravity y Claude votaron SÍ (ronda 2, sin bloqueos; la ronda 1 de Codex aportó los cambios de §7-costo, §10 y §12).** **Este archivo es la fuente única del contrato. No lo modifiques.** Si un worker cree que algo aquí es contradictorio o inviable, lo reporta en su entrega; no lo cambia por su cuenta.

Repos: `C:\dev\ia-api` (FastAPI + Ollama `qwen3.5:9b`) y `C:\dev\optica` (Laravel 13 + Livewire 4.4, es el repo que los documentos llaman `opt`).
Documentos de origen: `C:\dev\ia-api\PROPUESTA_IA_MULTITAREA_WHATSAPP.md` (decisiones D-1…D-20) y `C:\dev\ia-api\CATALOGO_WHATSAPP_Y_TRATO_AL_PACIENTE.md` (catálogo v1-revisado).

---

## 0. Decisiones del dueño del 2026-11-07 (no se discuten)

1. **Consentimiento (D-17):** el dueño declara que la IA es local y que ya tiene acuerdos con sus pacientes. No se exige un registro de consentimiento dentro del sistema para personalizar. Queda documentado como decisión del dueño.
2. **Flujo:** en el listado de pacientes, al pulsar «Invitar a cita por WhatsApp» se abre de inmediato un diálogo con el mensaje preliminar **editable**; el mensaje se personaliza solo; al pulsar **Aceptar** se abre WhatsApp con el texto que quedó en el diálogo. Sin Aceptar no se abre nada.
3. Se conservan: D-10 (minimización), D-11 (sin «progresión», sin presbicia deducida), D-12…D-16 (catálogo cerrado, ensamblado por el servidor, validador, verificación, respaldo), D-18 (menores: solo genérico), D-19, D-20 (nunca patologías por WhatsApp). Trato de **usted** siempre.

## 1. Endpoint (ia-api)

`POST /v1/inferencia/seguimiento-whatsapp` · `Authorization: Bearer <API_KEY>` (la misma de `/inferencia/impresion-clinica`) · JSON.

- 200: respuesta del §3 (siempre que el request sea válido; un fallo del modelo **no** es error HTTP: se responde `estado="plantilla"`).
- 401: sin token o token inválido (igual que el endpoint clínico). 500 si `API_KEY` no está configurada (igual que el clínico).
- 422: request inválido (validación pydantic, `contrato_version` distinto, campos fuera de catálogo, campos extra).

## 2. Request (`extra="forbid"`; todos los campos son obligatorios salvo que diga «opcional»)

```json
{
  "contrato_version": "seguimiento-whatsapp-v1",
  "paciente_ref": "3f9a1c0b7d2e4a51",
  "tramo_edad": "18_39",
  "estado_seguimiento": "proximo",
  "meses_desde_ultima_receta": 11,
  "recetas_previas": 2,
  "costo": "incluida",
  "ya_notificado_en_ciclo": false,
  "variante": 0,
  "rx_lejos": {"od": {"esfera": -2.25, "cilindro": -0.5, "add": null},
               "oi": {"esfera": -2.0, "cilindro": 0.0, "add": null}},
  "tipo_lente": "monofocal",
  "uso_pantallas": "gt6",
  "usa_armazon": null
}
```

| Campo | Tipo / valores | Origen en Laravel |
|---|---|---|
| `contrato_version` | literal `"seguimiento-whatsapp-v1"` | constante |
| `paciente_ref` | string `^[a-f0-9]{16}$` | `substr(hash_hmac('sha256', tenant_id.':'.paciente_id, config('app.key')), 0, 16)`; solo para correlacionar logs |
| `tramo_edad` | `"18_39"` \| `"40_59"` \| `"60_mas"` | edad a hoy desde `pacientes.fecha_nacimiento`. **Menores y edad desconocida nunca se envían** (Laravel usa el genérico) |
| `estado_seguimiento` | `"proximo"` \| `"vencido"` | `PacienteSeguimientoEstado` del paciente (los demás estados nunca se envían) |
| `meses_desde_ultima_receta` | int 0..600 \| null | meses completos entre `fecha_receta` de la última receta y hoy; null si no hay recetas |
| `recetas_previas` | int 0..1000 | número de recetas del paciente (tenant) |
| `costo` | `"incluida"` \| `"con_costo"` | `pacientes.proxima_evaluacion_con_costo` (true → `con_costo`) |
| `ya_notificado_en_ciclo` | bool | `pacientes.seguimiento_notificado_at !== null` |
| `variante` | int 0..1000 | 0 al abrir el diálogo; «Regenerar con IA» manda un valor nuevo 1..1000 |
| `rx_lejos` | objeto \| null | graduaciones OD/OI (`esfera`, `cilindro`, `add`, como float o null) de la **última receta** (`fecha_receta` desc, `id` desc). null si esa receta no tiene filas de graduación. Si falta una fila, ese ojo va con los tres valores null |
| `tipo_lente` | `"monofocal"` \| `"bifocal"` \| `"progresivo"` \| `"otro"` \| null | `recetas.tipo_lente` de **la misma receta**: `monofocal`→`monofocal`; `bifocal_blended`/`flat_top`→`bifocal`; `progresivo`→`progresivo`; otro valor no vacío→`otro`; vacío→null |
| `uso_pantallas` | `"lt2"` \| `"btw2_6"` \| `"gt6"` \| null | `receta_clinicas.uso_pantallas` de **la misma receta** |
| `usa_armazon` | bool \| null | **v1: Laravel siempre manda null** (el dato no existe de forma confiable; el catálogo §6.6 lo exige). ia-api acepta true/false/null |

Nunca viajan: nombre, teléfono, folio, fechas exactas, ocupación, motivo de consulta, notas, impresión clínica, correlaciones, patologías, AKR, eje, agudeza visual.

ia-api normaliza `rx_lejos` con la misma lógica ya auditada de la Rx (rangos, transposición de cilindro positivo, `add <= 0` = sin adición): reutiliza `app.schemas.Refraccion`/`GraduacionOjo`.

## 3. Respuesta 200

```json
{
  "status": "ok",
  "contrato_version": "seguimiento-whatsapp-v1",
  "estado": "generada",
  "mensaje": "<apertura>\n\n<hecho1> <hecho2>\n\n<invitacion>\n\nSi prefiere no recibir estos recordatorios, solo díganoslo.",
  "partes": {"apertura": "...", "hechos": ["miopia_lejos", "pantallas_muchas"], "invitacion": "...",
             "baja": "Si prefiere no recibir estos recordatorios, solo díganoslo."},
  "motivo": null,
  "hechos_elegibles": ["miopia_ajuste", "..."],
  "generacion": {"origen": "llm", "modelo": "qwen3.5:9b", "catalogo_version": "v1-revisado-2026-11-06",
                 "prompt_version": "seguimiento-whatsapp-prompt-v1", "base_hash_api": "<64 hex>", "cached": false}
}
```

Reglas:
- `estado`: `"generada"` (Qwen redactó apertura/invitación y eligió hechos; pasó validador y verificación) o `"plantilla"` (mensaje 100 % del catálogo armado por el servidor, §8).
- `generacion.origen`: `"llm"` si `estado="generada"`; `"catalogo"` si `estado="plantilla"`. `modelo` es string con `origen="llm"` y null con `"catalogo"`.
- `motivo`: null si `generada`; si `plantilla`, uno de: `ia_ocupada`, `ia_timeout`, `ollama_error`, `json_invalido`, `validacion:<regla>` (p. ej. `validacion:palabras`, `validacion:tuteo`, `validacion:lexico`, `validacion:costo`, `validacion:combinacion`, `validacion:placeholders`, `validacion:pregunta`, `validacion:cifras`), `verificacion`.
- `mensaje` = `apertura + "\n\n" + " ".join(frases de los hechos en el orden de partes.hechos) + "\n\n" + invitacion + "\n\n" + baja`. Si `hechos` está vacío: `apertura + "\n\n" + invitacion + "\n\n" + baja`.
- Orden de `partes.hechos`: primero el del grupo A y después el del B; si los dos son del B, en el orden de prioridad del §8. (Si Qwen los devuelve en otro orden, el servidor los reordena antes de ensamblar.)
- `hechos_elegibles` va en el orden en que el catálogo lista los hechos (§2 del .md: primero los 12 del grupo A, luego los 8 del B).
- `mensaje` contiene **exactamente una vez** `:paciente` y **exactamente una vez** `:clinica`, ambos dentro de `apertura`. Ningún otro marcador `:palabra`. Longitud ≤ 2000 caracteres. Termina con la línea de baja.
- `generacion.base_hash_api`: sha256 hex (64) de la clave de caché del request.
- `cached`: true si salió de la caché de ia-api (solo se cachean respuestas `generada`).

Laravel valida esta forma de manera estricta; cualquier desviación → mensaje genérico local con motivo `respuesta_invalida`.

## 4. Catálogo en código (ia-api) — texto **literal** de `CATALOGO_WHATSAPP_Y_TRATO_AL_PACIENTE.md` §2 y §3

- `CATALOGO_VERSION = "v1-revisado-2026-11-06"`, `PROMPT_VERSION = "seguimiento-whatsapp-prompt-v1"`, `VERIFICACION_VERSION = "seguimiento-verificacion-v1"`, `CONTRATO_VERSION = "seguimiento-whatsapp-v1"`.
- Los 20 hechos con su id, grupo (A/B), tema y texto **idéntico carácter por carácter** al catálogo (una prueba debe leer el .md y comparar).
- Aperturas A1–A10, invitaciones I1–I10 y la línea de baja, también literales.
- Temas (para «nunca dos del mismo tema»): `miopia` {miopia_ajuste, miopia_lejos}, `hipermetropia` {hipermetropia_ajuste, hipermetropia_cerca}, `astigmatismo` {astigmatismo_detalle, astigmatismo_comodidad}, `cerca` {cerca_adecuado, cerca_distancias}, `progresivo` {progresivo_zonas, progresivo_ajuste}, `bifocal` {bifocal_zonas}, `armazon` {ajuste_armazon}, `pantallas` {pantallas_muchas, pantallas_ratos}, `vencida` {vencida_retomar}, `costo` {incluida_sin_costo, con_costo_claro}, `comodidad` {comodidad_general}, `periodica` {general_periodica}, `traer` {traer_lentes}.

## 5. Elegibilidad (determinista, en ia-api)

Perfil de corrección: el de `app/patient_profile.py` (refactor mínimo para aceptar una `Refraccion`; `build_patient_profile(req)` delega en la nueva función y su comportamiento NO cambia). «Incluye miopía/hipermetropía/astigmatismo» = algún ojo la nombra. «Apoyo de cerca» = algún ojo con ADD > 0. Si el perfil es `datos_incompletos` o `rx_lejos` es null: ningún hecho del grupo A es elegible. **Antimetropía** (un ojo nombra miopía y el otro hipermetropía): ningún hecho que nombre una condición (`miopia_*`, `hipermetropia_*`, `astigmatismo_*`) es elegible. «Tipo de lente registrado» = `tipo_lente` no null.

| id | Elegible si |
|---|---|
| miopia_ajuste | incluye miopía |
| miopia_lejos | incluye miopía y tipo de lente registrado |
| hipermetropia_ajuste | incluye hipermetropía |
| hipermetropia_cerca | incluye hipermetropía |
| astigmatismo_detalle | incluye astigmatismo |
| astigmatismo_comodidad | incluye astigmatismo y `usa_armazon is True` |
| cerca_adecuado | apoyo de cerca |
| cerca_distancias | apoyo de cerca |
| progresivo_zonas | `tipo_lente == "progresivo"` y apoyo de cerca |
| progresivo_ajuste | igual que progresivo_zonas y `usa_armazon is True` |
| bifocal_zonas | `tipo_lente == "bifocal"` y apoyo de cerca |
| ajuste_armazon | `tipo_lente in ("monofocal", "bifocal")` y `usa_armazon is True` |
| pantallas_muchas | `uso_pantallas == "gt6"` y tipo de lente registrado |
| pantallas_ratos | `uso_pantallas in ("btw2_6", "gt6")` |
| vencida_retomar | `estado_seguimiento == "vencido"` |
| incluida_sin_costo | `costo == "incluida"` |
| con_costo_claro | `costo == "con_costo"` |
| comodidad_general | tipo de lente registrado |
| general_periodica | tipo de lente registrado |
| traer_lentes | siempre |

## 6. Combinación (válida para la elección de Qwen y para el respaldo)

1. 0, 1 o 2 hechos; sin duplicados; nunca dos del mismo tema.
2. Máximo 1 del grupo A. Del grupo B, máximo 1 si hay uno del A; hasta 2 si no hay ninguno del A.
3. Parejas prohibidas (`PUEDE_CAMBIAR = {miopia_ajuste, hipermetropia_ajuste, astigmatismo_detalle}`):
   - PUEDE_CAMBIAR × {pantallas_muchas, pantallas_ratos}
   - PUEDE_CAMBIAR × {vencida_retomar}
   - vencida_retomar × con_costo_claro
   - {cerca_adecuado, cerca_distancias} × {progresivo_zonas, progresivo_ajuste, bifocal_zonas}
   - dos de {astigmatismo_comodidad, progresivo_ajuste, ajuste_armazon, comodidad_general}
   - general_periodica × PUEDE_CAMBIAR
   - general_periodica × traer_lentes, salvo que esos dos sean los únicos hechos elegibles
4. Todo id elegido debe estar en `hechos_elegibles`.

## 7. Validador determinista del mensaje ensamblado (D-14)

Se aplica a lo que escribió Qwen (`apertura`, `invitacion`) y al mensaje completo. Falla → `estado="plantilla"`, `motivo="validacion:<regla>"`.
- `palabras`: 50–110 palabras en `apertura + hechos + invitacion` (sin la baja), contando con `app.patient_profile.word_count` sobre el texto con los marcadores tal cual (`:paciente` cuenta 1). `apertura` y `invitacion` no vacías, sin saltos de línea, ≤ 300 caracteres cada una.
- `placeholders`: `:paciente` y `:clinica` exactamente una vez cada uno y solo en `apertura`; ningún otro `:[a-z_]+`; sin `{`, `}`, `<`, `>`, `*`, `http`, `www`.
- `cifras`: ningún dígito en `apertura` ni en `invitacion`.
- `pregunta`: `invitacion` termina en `?` y contiene `¿`.
- `tuteo`: en apertura e invitación, ninguna palabra completa de `\b(tú|tu|tus|te|ti|contigo|tienes|puedes|quieres|necesitas|estás|eres|vienes|haces|sabes|ven|dime|avísanos|escríbenos|cuéntanos)\b` (insensible a mayúsculas). «agenda» NO está en la lista: A8 la usa como sustantivo («su agenda»).
- `lexico`: sobre apertura e invitación en minúsculas y **sin acentos**; cada término se busca como **inicio de palabra** (`\b` + término) y los de varias palabras como frase; nunca como subcadena suelta (así «revision» no dispara «vision»). Términos: miopia, hipermetropia, astigmatismo, presbicia, catarata, glaucoma, enfermedad, diagnostic, patolog, sintoma, borros, empeor, progres, sano, sana, normal, riesgo, urgen, grave, peligr, dano, perder la vista, ceguera, garantiz, promet, perfect, gratis, descuento, promocion, oferta, precio, pago, ultima oportunidad, ultimo lugar, quedan pocos, solo esta semana, hoy mismo, antes de que, debe, tiene que, es necesario, no lo deje, atrasad, retras, se le paso, descuid, no nos ha respondido, sin respuesta, ignor, mayoria, todos nuestros pacientes, edad, anos, mayor, abuel; más el carácter `$`. Además están prohibidas como **palabra completa** `vista`, `vision`, `ojo`, `ojos`, `graduacion`, `graduaciones` (Qwen no opina sobre la vista; eso lo dicen los hechos). «revisión visual» y «lentes» sí están permitidas (I7 dice «Si usa lentes, puede traerlos»).
- Las 10 aperturas y las 10 invitaciones de muestra del catálogo deben pasar `tuteo`, `lexico`, `cifras` y `placeholders` (prueba obligatoria; si alguna no pasa, el validador está mal).
- `costo`: **el mensaje siempre comunica la condición de costo, y una sola vez**: o por el hecho de costo, o por la invitación.
  - `costo == "con_costo"`: apertura e invitación sin «incluida», «sin costo», «gratis». Si `con_costo_claro` no está entre los hechos, la invitación contiene «costo»; si sí está, la invitación no contiene «costo».
  - `costo == "incluida"`: apertura e invitación sin «tiene costo», «tiene un costo», «monto», «cobr». Si `incluida_sin_costo` no está entre los hechos, la invitación contiene «incluida»; si sí está, la invitación no contiene «incluida» ni «costo».
- `combinacion`: §6.
- `hechos`: las frases del mensaje son el texto literal del catálogo, en el orden de `partes.hechos`.

## 8. Respaldo determinista (`estado="plantilla"`, `origen="catalogo"`)

Se usa cuando Qwen no está disponible o su salida no pasa §7 o la verificación. Debe pasar el validador §7 en el 100 % de los perfiles (prueba de matriz).

**Selección de hechos.** Orden de temas del grupo A: `progresivo`, `bifocal`, `cerca`, `miopia`, `hipermetropia`, `astigmatismo`, `armazon`. Dentro de cada tema, si `recetas_previas` es par va primero la primera frase del catálogo y si es impar va primero la segunda (alternancia entre ciclos). Grupo B por prioridad: `pantallas_muchas`, `vencida_retomar`, `pantallas_ratos`, el hecho de costo que aplique, `comodidad_general`, `general_periodica`, `traer_lentes`. Rango = posición entre los **elegibles** de su grupo (0 = mejor).
- Si hay elegibles del A: entre todas las parejas válidas (a, b) y los singletes válidos (a) se elige la de menor `rango(a) + rango(b)` (un hecho ausente cuenta como `len(elegibles_B)`); empate → menor `rango(a)`, luego menor `rango(b)`.
- Si no hay del A: la pareja válida de B con menor suma de rangos; si no hay pareja válida, el mejor singlete.

**Apertura** (la primera que aplique): `vencido` → A4; `ya_notificado_en_ciclo` → A3; `tramo_edad == "60_mas"` y `recetas_previas >= 2` → A6; `costo == "con_costo"` → A9; si no → A1.

**Invitación**: `con_costo` sin `con_costo_claro` → I3; `incluida` sin `incluida_sin_costo` → I2; si no → I1.

## 9. Verificación con Qwen (D-15)

Segunda llamada, temperatura 0, `format` JSON schema `{"afirma_algo_de_salud": boolean}` (requerido). Pregunta si la **apertura** o la **invitación** (no los hechos) afirman algo sobre la salud, la vista, los ojos, la graduación o los lentes de la persona. `true`, JSON inválido, error o timeout → `plantilla` con `motivo="verificacion"`.

## 10. Prioridad de GPU (D-2)

Un solo turno de GPU en el proceso. Prioridades: `interactiva` (receta clínica) y `fondo` (seguimiento). Las interactivas en espera siempre pasan antes que las de fondo.
- **Admisión de fondo (atómica, bajo el candado del planificador):** si una interactiva **ocupa** el turno o hay alguna interactiva **en espera**, la llamada de fondo falla de inmediato (sin esperar) y el seguimiento responde `plantilla` con `motivo="ia_ocupada"`. Si el turno está libre, entra. Si lo ocupa otra llamada de **fondo**, espera en FIFO como máximo `FONDO_QUEUE_WAIT_TIMEOUT` segundos (por omisión 10); si mientras espera llega una interactiva, la interactiva pasa primero; si se agota la espera → `ia_ocupada`.
- El seguimiento pide turno **por cada llamada** al modelo (redacción y verificación por separado), así que una receta puede entrar entre ambas; si al pedir el turno de la verificación hay una interactiva ocupando o esperando, el resultado es `plantilla` con `motivo="ia_ocupada"`.
- La receta clínica conserva su comportamiento actual (un turno para toda su cadena, mismos códigos 503/504/413/502).

## 11. Casos dorados (ambos repos los usan como fixtures; el resultado del respaldo es normativo)

### G1 — request
```json
{"contrato_version":"seguimiento-whatsapp-v1","paciente_ref":"3f9a1c0b7d2e4a51","tramo_edad":"18_39","estado_seguimiento":"proximo","meses_desde_ultima_receta":11,"recetas_previas":2,"costo":"incluida","ya_notificado_en_ciclo":false,"variante":0,"rx_lejos":{"od":{"esfera":-2.25,"cilindro":-0.5,"add":null},"oi":{"esfera":-2.0,"cilindro":0.0,"add":null}},"tipo_lente":"monofocal","uso_pantallas":"gt6","usa_armazon":null}
```
Elegibles: `miopia_ajuste, miopia_lejos, astigmatismo_detalle, pantallas_muchas, pantallas_ratos, incluida_sin_costo, comodidad_general, general_periodica, traer_lentes`.
**Respaldo G1** (`estado="plantilla"`): hechos `["miopia_lejos", "pantallas_muchas"]`, apertura A1, invitación I2. `mensaje`:
```
Hola, :paciente, le saludamos de :clinica. Se acerca la fecha de su revisión visual de control y quisimos avisarle con tiempo.

En la revisión comprobamos si sus lentes le siguen dando una visión de lejos cómoda para sus actividades diarias. Si pasa muchas horas frente a pantallas, en la revisión podemos ver qué tan cómodos le resultan sus lentes para esas actividades.

La revisión está incluida en su atención. ¿Qué día de la semana le queda mejor para venir?

Si prefiere no recibir estos recordatorios, solo díganoslo.
```
**Generada G1** (respuesta del modelo simulado para pruebas): redacción
```json
{"apertura":"Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos escribirle con tiempo para que la organice a su ritmo.","hechos":["miopia_lejos","pantallas_muchas"],"invitacion":"La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus actividades. ¿Qué día de la semana le resulta más cómodo para venir?"}
```
y verificación `{"afirma_algo_de_salud": false}` → `estado="generada"`, `motivo=null`, `mensaje` = apertura + `\n\n` + las dos frases literales + `\n\n` + invitación + `\n\n` + baja.

### G2 — request
```json
{"contrato_version":"seguimiento-whatsapp-v1","paciente_ref":"c0ffee00c0ffee00","tramo_edad":"60_mas","estado_seguimiento":"vencido","meses_desde_ultima_receta":19,"recetas_previas":3,"costo":"con_costo","ya_notificado_en_ciclo":true,"variante":0,"rx_lejos":{"od":{"esfera":1.25,"cilindro":-0.75,"add":2.25},"oi":{"esfera":1.0,"cilindro":0.0,"add":2.25}},"tipo_lente":"progresivo","uso_pantallas":null,"usa_armazon":null}
```
Elegibles: `hipermetropia_ajuste, hipermetropia_cerca, astigmatismo_detalle, cerca_adecuado, cerca_distancias, progresivo_zonas, vencida_retomar, con_costo_claro, comodidad_general, general_periodica, traer_lentes`.
**Respaldo G2**: hechos `["progresivo_zonas", "vencida_retomar"]`, apertura A4, invitación I3. `mensaje`:
```
Hola, :paciente, le saludamos de :clinica. Sabemos que el tiempo se va rápido entre tantas ocupaciones; cuando usted quiera, retomamos su revisión visual.

En sus lentes progresivos revisamos que la zona de lejos, la intermedia y la de cerca sigan acomodándose a sus actividades. Si ha pasado un tiempo desde su última revisión, retomarla es sencillo y la hacemos a su ritmo, sin prisas.

La revisión tiene un costo; si lo desea, con gusto le compartimos el detalle antes de agendar. ¿Le gustaría que veamos juntos un horario?

Si prefiere no recibir estos recordatorios, solo díganoslo.
```

### G3 — request
```json
{"contrato_version":"seguimiento-whatsapp-v1","paciente_ref":"0123456789abcdef","tramo_edad":"40_59","estado_seguimiento":"proximo","meses_desde_ultima_receta":null,"recetas_previas":0,"costo":"incluida","ya_notificado_en_ciclo":false,"variante":0,"rx_lejos":null,"tipo_lente":null,"uso_pantallas":null,"usa_armazon":null}
```
Elegibles: `incluida_sin_costo, traer_lentes`.
**Respaldo G3**: hechos `["incluida_sin_costo", "traer_lentes"]`, apertura A1, invitación I1. `mensaje`:
```
Hola, :paciente, le saludamos de :clinica. Se acerca la fecha de su revisión visual de control y quisimos avisarle con tiempo.

Su revisión de seguimiento está incluida en su atención, sin ningún costo adicional para usted. Si usa lentes, le sugerimos traerlos a la consulta, así podemos revisarlos junto con su graduación.

Nosotros le buscamos un horario que le acomode. ¿Le gustaría que le apartemos una cita?

Si prefiere no recibir estos recordatorios, solo díganoslo.
```

## 12. Laravel: aplicabilidad local y uso de la respuesta

- Se personaliza solo si: teléfono válido (si no, el error actual), estado del semáforo `vencido` o `proximo`, `fecha_nacimiento` presente y edad ≥ 18, integración IA habilitada (`services.ia_api.enabled`, key y endpoint), y `IaApiService::checkHealth()` listo. Si no, se usa el **genérico corregido** (§4 del catálogo, `lang/es/whatsapp.php` claves `seguimiento.sin_costo` / `seguimiento.con_costo`) con un motivo local: `estado_no_aplica`, `sin_fecha_nacimiento`, `menor_de_edad`, `ia_deshabilitada`, `ia_no_disponible`, `ia_error`, `respuesta_invalida`, `limite`, `en_curso`.
- Endpoint de ia-api: `services.ia_api.seguimiento_whatsapp_endpoint` (`IA_API_SEGUIMIENTO_WHATSAPP_ENDPOINT`); si está vacío se deriva de `impresion_clinica_endpoint` como ya hace `resolveHealthEndpoint()`: `scheme://host[:port]/v1/inferencia/seguimiento-whatsapp`. Timeout `services.ia_api.seguimiento_timeout` (`IA_API_SEGUIMIENTO_TIMEOUT`, por omisión 60 s).
- Laravel sustituye `:paciente` por `trim($paciente->nombre)` y `:clinica` por `$tenant->nombreComercial()` (con `strtr`, una sola pasada) solo al mostrar o aprobar. En base de datos guarda el texto con marcadores.
- `base_hash` local = sha256 de `json_encode([tenant_id, paciente_id, telefono_normalizado, nombre_paciente_sustituido, nombre_comercial_sustituido, estado_semaforo, costo, payload sin "variante" ni "paciente_ref" o null])`. Se calcula al abrir el diálogo y se vuelve a calcular al Aceptar: si cambió (teléfono, nombre, clínica, cita, costo, estado, Rx…), no se abre WhatsApp, se avisa que los datos cambiaron y el diálogo se vuelve a preparar para que el operador revise y acepte otra vez.
- El diálogo muestra siempre el destinatario: nombre del paciente y teléfono normalizado al que se abrirá WhatsApp.
- Logs del flujo de seguimiento sin contenido: nunca el payload, el mensaje ni el nombre; solo estado, motivo, status HTTP, duración y `paciente_ref`.
