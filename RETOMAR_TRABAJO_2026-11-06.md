# Retomar el trabajo: IA multitarea, texto del paciente y WhatsApp (corte del 2026-11-06, 16:51)

> **Para Claude en otra PC.** Lee este archivo completo antes de hacer nada. Resume una sesión larga para que no repitas auditorías ya hechas. Contesta al usuario en español. Al paciente se le trata **siempre de usted**: lo ordenó el usuario.

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
