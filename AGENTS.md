## Approach
- Think before acting. Read existing files before writing code.
- Be concise in output but thorough in reasoning.
- Prefer editing over rewriting whole files.
- Do not re-read files you have already read unless the file may have changed.
- Skip files over 100KB unless explicitly required.
- Suggest running /cost when a session is running long to monitor cache ratio.
- Recommend starting a new session when switching to an unrelated task.
- Test your code before declaring done.
- No sycophantic openers or closing fluff.
- Keep solutions simple and direct.
- User instructions always override this file.

## Clinical data contract
- Treat `DICCIONARIO_DATOS_RECETA.md` as the authoritative payload contract for this and all future clinical analyses. Do not assume undocumented fields, examinations, normal findings, diagnoses, or chronology.
- Correlations must describe supported findings that warrant further specialist evaluation, not invent or confirm diagnoses. Remove unsupported inference branches when the payload cannot justify them.

## Proyecto (estado 2026-11-20)
- API FastAPI que atiende tres tareas registradas en `app/tareas/definiciones/`: `receta-clinica` (impresión clínica), `explicacion-paciente` y `seguimiento-whatsapp` (contrato `seguimiento-whatsapp-v2`).
- Documentación vigente:
  - `README.md` (maestra);
  - `GUIA_CONEXION.md` (despliegue y túnel);
  - `PIPELINE_LLM.md`;
  - `SALIDA_DUAL.md`;
  - `CORRELACIONES_CLINICAS.md`;
  - `COMO_AGREGAR_UNA_TAREA.md`;
  - `DICCIONARIO_DATOS_RECETA.md` (contrato normativo);
  - `CATALOGO_WHATSAPP_Y_TRATO_AL_PACIENTE.md` (catálogo v2, pendiente de la firma del optometrista; una prueba exige que coincida con `app/seguimiento/catalogo.py`).
- `auditoria/` guarda **solo datos que leen las pruebas** (casos, órdenes y reproducciones). No agregues ahí actas ni informes.
- `scripts/`: `certificar_gpu.py` + `certificacion/` (kit de certificación en la PC con GPU), `probar_enrutado.py` (comprobación posterior al despliegue) y `catalogo_paciente.py` (genera el material de revisión del dueño).
- El dueño hace los commits. No hagas commit, push ni despliegues.

## WhatsApp de seguimiento (v2)
- Objetivo: que el paciente cuente cómo le han funcionado sus lentes; la cita es una opción suave. Siempre de usted.
- La clínica y el paciente son SOLO los marcadores `:clinica` y `:paciente`. Los llena opt con los datos del tenant y del paciente. Nunca pongas nombres reales en el código ni en los textos.
- `contexto_uso` (texto clínico) solo llega a la etapa `uso`, que devuelve una etiqueta cerrada. Nunca entra en la redacción, la verificación, la respuesta, los logs ni la clave de caché en claro: lo comprueba `tests/test_seguimiento_privacidad.py`.
- Cualquier cambio de texto va en `catalogo.py` y en el documento del catálogo a la vez. Si cambia la forma del request o del response, actualiza los fixtures compartidos con opt (`tests/fixtures/seguimiento_whatsapp/` ↔ `opt/tests/Fixtures/seguimiento-whatsapp/`, copia byte a byte) y `sha256.json`.

## Pruebas: alto valor, no volumen
- Niveles:
  - **FAST**: rutas explícitas de los archivos del módulo tocado (no `tests/ -k`: la colección completa cuesta unos 30 s);
  - **AFFECTED**: para `app/seguimiento/*`, `tests/test_seguimiento_*.py`, `tests/test_enrutado.py` y `tests/test_tareas.py`; para `app/correlaciones/*`, todas las de correlaciones, cierre, vocabulario, w0, ajustes y revalidación, incluida `test_cierre_contexto.py` (usa `runpy` y no aparece en los imports);
  - **FULL**: `venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`, unos 2 min, obligatorio si tocas `main.py`, `config.py`, `tareas/`, `schemas`, los fixtures compartidos o `conftest.py`;
  - **exhaustiva** de seguimiento: `IAAPI_EXHAUSTIVO=1`.
- Las pruebas no dependen del `.env` local: `tests/conftest.py` fija `OLLAMA_NUM_CTX` antes de importar `app`. Toda espera asíncrona en una prueba lleva tope.
- Antes de crear una prueba, busca las existentes (`rg "<función|regla>" tests/`) y amplía una si cubre lo mismo. Cada prueba nueva protege un comportamiento observable que ninguna otra protege.
- Prohibido el producto cartesiano completo de más de 3 dimensiones: usa una lista t=3 o representantes por clase, con la versión exhaustiva detrás de una variable de entorno.
- Nada de pruebas sin aserción relevante, que solo comprueben llamadas a mocks o que copien casos de auditoría.
- No elimines pruebas de seguridad, privacidad, contrato con opt ni regresión clínica sin evidencia de mutantes y aprobación del dueño.
- Mutación: solo dirigida a lógica clínica, de costo o de privacidad, con un presupuesto declarado. Nunca completa por un cambio trivial.
- En esta PC falta `tokenizers`: `test_certificar_gpu.py::test_corrida_completa_modo_rapido` falla por entorno.
