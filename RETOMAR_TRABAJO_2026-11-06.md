# Retomar el trabajo: IA multitarea, texto del paciente y WhatsApp (corte del 2026-11-06, 16:51)

> **Para Claude en otra PC.** Lee este archivo completo antes de hacer nada. Resume una sesión larga para que no repitas auditorías ya hechas. Contesta al usuario en español. Al paciente se le trata **siempre de usted**: lo ordenó el usuario.

## 0-ter. Corte del 2026-11-13: las tres funciones listas para desplegar (léase primero)
- **Estado:** impresión clínica, explicación al paciente y WhatsApp están **certificadas sin GPU**. Lo que falta solo se mide con Qwen real, y para eso está el kit `scripts/certificar_gpu.py` (guía en `scripts/certificacion/LEEME.md`). Los umbrales se firmaron antes de medir y el kit da APTO o NO APTO por perfil: A, todo activo; B, paciente con plantilla; C, WhatsApp con catálogo; D, solo clínico.
- **Expediente:** `auditoria/2026-11-12-cierre-y-certificacion-gpu/`:
  - `00`: umbrales firmados;
  - `01`: compatibilidad entre versiones;
  - `02`: vocabulario de síntomas;
  - `03`: **acta de cierre y despliegue paso a paso**.
- **Nuevo en este corte:**
  - el interruptor `SEGUIMIENTO_LLM_HABILITADO`, con `motivo=ia_deshabilitada`, que Laravel acepta;
  - `CACHE_MAX_SIZE=0` ya no da 500;
  - formas verbales de síntomas, inicio reciente de hasta 7 días y síntomas que refiere un acompañante: 0 detecciones perdidas en 107 044 casos frente al código certificado.
- **Pruebas:** ia-api 24 953 passed con el tokenizador oficial; Laravel 655 OK; JS 37/37.
- **Siguiente paso del dueño:**
  - commits;
  - en la PC con GPU, correr el kit, marcar las hojas y cerrar;
  - desplegar según el `03` §5.

## 0-bis. Corte del 2026-11-12: explicación al paciente con Qwen (léase primero)
- **Hecho y certificado sin GPU:** la explicación para el paciente ya la redacta Qwen **en el mismo proceso** que la impresión clínica. Primero el clínico certificado, sin cambios; luego la redacción con el clínico final y hechos deterministas, un validador, una verificación con Qwen y el ensamblado CPU con las acciones obligatorias primero. Si algo falla, queda la plantilla. Es decisión del dueño del 2026-11-07, que corrige la separación del 2026-11-06.
- **Corregido de paso:** el 413 en modo dual (antes daba 502) y la negación coordinada de las correlaciones, sin perder ninguna detección (principio «ante ambigüedad gana la detección»).
- **Expediente:** `auditoria/2026-11-08-explicacion-paciente/` (requerimiento, diseño v2.1, catálogo y prompts para revisión del dueño, correcciones documentales, contrato del corpus y `05-acta-certificacion.md`).
- **Pruebas:** ia-api 23226 passed + 3 xfail (brecha de vocabulario conocida); Laravel 654 OK; de punta a punta con un Ollama simulado y el tokenizador oficial, y prueba en navegador, sin fallos.
- **Pendiente:** commits; en la PC con GPU, calidad real, latencias y cancelación (ver §5 del acta); revisión del catálogo de acciones y del glosario; decisión sobre `PRESUPUESTO_RECETA_SIN_EXACTO`; brecha de vocabulario («perdió la visión», «viendo doble»…). Vuelta atrás sin desplegar: `PACIENTE_LLM_HABILITADO=false`.

## 0. Corte del 2026-11-07 (léase primero)
- **Hecho:** pendiente 2 (re-certificación C1–C6: CERTIFICADO; C5 falta confirmarlo en la PC con GPU) y F1–F3 de los mensajes de WhatsApp personalizados (contrato `seguimiento-whatsapp-v1`, endpoint en ia-api, diálogo editable en Laravel con aprobación humana, planificador de GPU con prioridad, `GET /v1/tareas` y `scripts/probar_enrutado.py`). Todo en `auditoria/2026-11-07-recertificacion-y-seguimiento/`.
- **Decisiones del dueño del 2026-11-07:** no se exige registro de consentimiento (acuerdos con sus pacientes, IA local); flujo: clic → diálogo editable inmediato → personalización automática → Aceptar abre WhatsApp.
- **Pruebas:** ia-api 22151 passed; Laravel 620 OK; JS 37/37; prueba cruzada real Laravel ↔ ia-api y prueba en navegador sin fallos (Qwen simulado).
- **Registro de tareas escalable (2026-11-07, tarde):** agregar una función de IA ya no toca `main.py` (ver `COMO_AGREGAR_UNA_TAREA.md`); guardián de 8k tokens en cada envío a Qwen con conteo exacto del tokenizador del modelo (Qwen2 y Qwen3.5), verificado al arrancar. Acta: `auditoria/2026-11-07-recertificacion-y-seguimiento/03-registro-de-tareas.md`. Pruebas: ia-api 22190 passed; Laravel 636 OK.
- **Decisión pendiente del dueño:** si la PC con GPU no verifica el conteo exacto, ¿la receta sigue con la cota conservadora (valor actual) o se bloquea (`PRESUPUESTO_RECETA_SIN_EXACTO=estricto`)? Tras desplegar, revisar en `/health` que `modo_conteo` diga `exacto`.
- **Pendiente del dueño:** commits de ambos repos; desplegar ia-api y Laravel juntos; en la PC con GPU, `OLLAMA_NUM_CTX=8192` y `scripts/probar_enrutado.py --modo real --url http://HOST:PUERTO --api-key-env IA_API_KEY`; piloto F4 con umbrales fijados antes; `graphify update .` en Laravel (no está instalado en esta PC).

## 1. Quién y qué
- El usuario es optometrista en México, dueño del sistema.
- **Laravel** (repo `opt`, carpeta `Documents/opt` en la PC original): SaaS de recetas, expediente, citas y seguimiento por WhatsApp. Producción en un VPS con Redis y supervisor.
- **ia-api** (este repo, `Documents/ia-api`): FastAPI + Ollama `qwen3.5:9b` en una RTX 3070 Ti de 8 GB. Está en la PC gamer del usuario y Laravel la alcanza por Cloudflare Tunnel.
- La PC de desarrollo **no tiene GPU ni el modelo**: nunca intentes inferencia real ahí.
- PHP temporal en la PC original: `C:\Users\Uriel Rojo\Downloads\php-8.4.22-nts-Win32-vs17-x64\php.exe`. MySQL local con la base de pruebas `laravel_testing`. Python: `venv/Scripts/python.exe` dentro de ia-api.
- **Reglas del usuario:**
  - Claude no hace commits; el usuario los hace a mano.
  - Implementación y arreglos se delegan a Codex y Antigravity (agy) con la skill `cli-agents`: su `route.py` prueba Codex primero y agy de respaldo. Claude diseña, audita y certifica.
  - Antes de delegar, guardar una foto de los archivos; después, revisar el diff y correr pruebas propias, sin confiar en lo que el delegado reporta.
  - Las decisiones importantes se discuten con Codex y agy hasta que los tres estén de acuerdo.

## 2. Qué se hizo el 2026-11-06

| Paso | Resultado | Dónde |
|---|---|---|
| Auditoría del texto simple para el paciente (Codex + agy) y certificación por un agente independiente | **NO CERTIFICADO**: era seguro, pero no explicaba la graduación (−0.25 y −12 daban el mismo texto), tuteaba, omitía el ojo sin graduación y Qwen no aportaba nada. Se fijaron las condiciones C1–C6. | `auditoria/2026-11-06-texto-paciente-y-propuesta/01..03` |
| Propuesta de arquitectura multitarea y WhatsApp personalizado | Consenso **SÍ** de Codex, agy y Claude tras 3 rondas | `PROPUESTA_IA_MULTITAREA_WHATSAPP.md`, rondas en `auditoria/.../04..09` |
| Catálogo de WhatsApp y técnicas de trato al paciente (agentes Psicólogo, Atención al paciente y Evidencia Clínica) | **BORRADOR v1-revisado, sin firmar** | `CATALOGO_WHATSAPP_Y_TRATO_AL_PACIENTE.md`, fuentes en `auditoria/.../10..12` |
| **F0, autorizada por el usuario**: cumplir C1–C6 | Implementada en ambos repos; falta cerrar la verificación (sección 3) | ver abajo |

### F0 en ia-api (implementó Codex; verificado por Claude)
- El modo `clinica-paciente-v1` hace la **misma llamada clínica** que `clinica-v1`, sin esquema JSON ni bloque educativo en el prompt.
- `explicacion_paciente` sale **solo** de `build_patient_template` (CPU). El contrato HTTP no cambió: el estado normal ahora es `plantilla`/`plantilla`.
- Todo el catálogo de `app/patient_profile.py` está en usted.
- El ojo sin graduación (ESF y CIL explícitamente 0) se menciona así: «En el ojo izquierdo, su receta de lejos marca 0.00: ese lado no lleva corrección para ver de lejos.».
- Cuando los ojos difieren, la apertura es una sola oración.
- Las versiones de caché subieron: `DUAL_PROMPT_VERSION=educacion-plantilla-usted-v3` y `PATIENT_PROFILE_VERSION=refraccion-final-lejos-v2`.
- Al arrancar, si `OLLAMA_NUM_CTX < 8192`, se escribe una advertencia en el log.
- Se marcó `PROPUESTA_RESUMEN_PACIENTE.md` como histórico.
- **Verificado:** `pytest` dio **6321 passed**. Una matriz propia de 195 perfiles (7 tipos por ojo × ADD) dio 0 fallos, 60–82 palabras, cero tuteo, cero palabras prohibidas y el ojo sin graduación siempre mencionado.
- Archivos: `app/{inference,patient_profile,dual_contract,prompt_builder,cache,config,main}.py`, `app/providers/ollama.py`, `tests/{test_patient_profile,test_dual_output,test_prompt_builder,test_main}.py`, `tests/conftest.py` (nuevo: bloquea el HTTP real en las pruebas), `SALIDA_DUAL.md`, `README.md`, `PIPELINE_LLM.md`, `PROPUESTA_RESUMEN_PACIENTE.md`.

### F0 en Laravel (implementó agy; Claude corrigió 2 defectos)
- Nuevo `app/Support/Recetas/LecturaRecetaPaciente.php` y `lang/es/receta_lectura.php`. Generan el bloque **«Cómo leer su receta»** en el PDF (`resources/views/recetas/pdf/informe_clinico.blade.php`, sección II, debajo de la tabla):
  - Una línea por ojo con las mismas cifras de la tabla, formateadas con `DioptriaFormatter` y sin transponer.
  - Una comparación neutral entre ojos.
  - Una leyenda de ESF, CIL, EJE, ADD y dioptría.
- La celda ADD de la tabla ahora usa `$fmtDiop`. El título de la sección pasó a «Explicación para el paciente».
- El estado `plantilla` ya no se trata como respaldo: cambiaron `FormEditor.php`, `IaTextContext.php` y `resources/js/recetas/ia-text-state.js`. Se actualizó `docs/estados-textos-ia.md`.
- **Defectos corregidos por Claude** (primero se escribió una prueba que fallaba):
  1. Solo cuentan como ojo sin graduación ESF **y** CIL explícitamente en 0; un cilindro faltante no es un cero.
  2. Una ADD distinta entre ojos hace que las graduaciones cuenten como distintas.
- Pruebas: `tests/Unit/Support/LecturaRecetaPacienteTest.php` y `tests/Feature/RecetaLecturaPdfTest.php` son nuevas; se ajustaron `RecetaIaPatientExplanationTest`, `RecetaIaPdfTest`, `RecetaIaTextStateTest` y `tests/Js/ia-text-state.test.mjs`.
- `graphify-out/` se regeneró porque el `AGENTS.md` del repo lo exige.
- **Verificado:** pruebas unitarias 12/12, JS 26/26 (`node --test tests/Js/*.test.mjs`) y `pint --test` en verde.
- **Suite completa de Laravel después de F0: 586 passed, 0 fallos** (antes de F0: 572).

## 3. Pendientes, en este orden
1. ~~Suite completa de Laravel~~: hecha a las 16:52, **586 passed**.
2. **Re-certificar C1–C6** con un agente `Reality Checker`, usando como contexto `auditoria/.../03-certificacion-agente.md`. Debe:
   - repetir la matriz de perfiles de ia-api (cero tuteo y cero palabras prohibidas);
   - renderizar el HTML real del PDF para −1/−8, cilindro positivo, ojo sin graduación con ADD y un ojo miope con el otro hipermétrope;
   - comprobar que cada cifra del bloque coincide con su celda y emitir el veredicto.
   Si sale CERTIFICADO, anotarlo en `auditoria/` y en la sección A de la propuesta.
3. **Commits del usuario.**
   - ia-api: los archivos de F0 en un commit y la documentación (propuesta, catálogo, `auditoria/`, este archivo) en otro.
   - Laravel: listo para commit (suite en verde).
   - **Desplegar ia-api y Laravel juntos.** Con el Laravel viejo, cada generación diría «plantilla de respaldo».
4. **En la PC con GPU:** `OLLAMA_NUM_CTX=8192` en el `.env` de ia-api. Con 4096, una receta con AKR da 413.
5. **F1** (cuando el usuario firme el catálogo, sección 6 de `CATALOGO_WHATSAPP_Y_TRATO_AL_PACIENTE.md`):
   - contrato `seguimiento-whatsapp` en `DICCIONARIO_DATOS_RECETA.md`;
   - catálogo firmado en código;
   - genérico corregido en `opt/lang/es/whatsapp.php`;
   - consentimiento demostrable (D-17);
   - exclusión de menores (D-18).
   Después vienen F2–F5 según la tabla C.6 de la propuesta.

## 4. Decisiones ya cerradas (no reabrir sin el usuario)
- Endpoints separados y tipados; Laravel declara el tipo de solicitud y ningún LLM lo «detecta».
- Una sola generación a la vez, con prioridad para la receta sobre las tareas de fondo; un único worker de uvicorn.
- El WhatsApp se ensambla en el servidor: Qwen escribe `{apertura, hechos:[ids], invitacion}` y las frases clínicas salen literales del catálogo firmado. Un humano aprueba el texto completo antes de abrir WhatsApp, y editarlo invalida esa aprobación.
- Al modelo viaja solo lo mínimo: nunca nombre, teléfono, patologías ni impresión clínica.
- Patologías por WhatsApp: nunca. Menores: solo el genérico. Fuera de lo personal, nada de «progresión» ni de presbicia deducida de la ADD.
- Primero el piloto en la GPU (F4) con umbrales fijados antes de empezar; el lote anticipado (F5) solo si el piloto lo justifica.
- Explicación del paciente: 100 % determinista. Las cifras jamás pasan por un LLM.

## 5. Lo que no viaja a otra PC
Las fotos de los repos de antes de F0 (`base-f0-iaapi.tar`, `base-f0-opt.tar`) y los logs de las corridas quedaron en el scratchpad temporal de la PC original. Para ver los cambios de F0 usa `git diff` en ambos repos; los commits del usuario son la referencia.
