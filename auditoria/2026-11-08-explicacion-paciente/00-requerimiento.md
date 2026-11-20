# Requerimiento — Explicación al paciente inferida por Qwen dentro del mismo proceso de la impresión clínica

Fecha: 2026-11-07. Orquesta: Claude. Debate: Codex + Antigravity (agy) hasta consenso de los tres. Repos: `C:\dev\ia-api` (FastAPI + Ollama `qwen3.5:9b`) y `C:\dev\optica` (Laravel 13 + Livewire 4).

## 1. Palabras del dueño (textuales)

> «Si pues la idea es que qwen haga un trabajo de inferencia simplificando el texto al paciente lo más entendible posible. En teoría se supone que el procesamiento de la impresión clínica contiene el contexto suficiente con los datos necesarios para dar la explicación al paciente, así lo había determinado yo en un principio. Creo que el modelo anterior no lo hizo así. La idea [es] que aprovechara el contexto de la impresión clínica que ya pasa por las correlaciones ultra deterministas y de ahí simplificar todo en explicarle al paciente qué es lo que ve etc. Parecería que me separaste las funciones cuando en teoría debían ser un único proceso.»

Antes había dicho: «la definición es que se use ese modelo para explicar de manera simple su diagnóstico del paciente en forma: "Usted ve de lejos las letras pequeñas etc."».

## 2. Situación actual (verificada por Claude; confírmenla y amplíenla)

- Una petición `POST /inferencia/impresion-clinica` (alias `/v1/inferencia/receta-clinica`) con `salida_version=clinica-paciente-v1` entra a `app/main.py:crear_impresion_clinica` → turno GPU `interactiva` → `app/inference.py:run_inference` → **una** llamada a Qwen que redacta la impresión clínica (tercera persona, lenguaje clínico) con el prompt de `app/prompt_builder.py`. Ese prompt ya contiene: contexto del paciente (edad, ocupación, motivo de consulta), refracción final por ojo (Esf/Cil/Eje/Add/AV), AKR y queratometría, campos clínicos (pantallas, anexos, pupilas, motilidad, campos, fondo de ojo, Amsler, BUT, cover test, PPC), diseño de lente y el bloque **«Correlaciones clínicas aplicables»** de `evaluar_correlaciones` (deterministas, con «Hallazgo urgente:» cuando aplica).
- Después: `_postprocess`, `clean_impresion`, `_purgar_no_sustentado`, `_ensure_emergency_preserved`, `_ensure_follow_up_last` (texto clínico final depurado).
- **`explicacion_paciente` NO pasa por Qwen**: sale de `app/patient_profile.py:build_patient_template` (CPU, catálogo cerrado, solo Rx final de lejos: miopía/hipermetropía/astigmatismo + ADD). Estado y origen `plantilla`. El mismo texto para −0.25 y −8.00. No usa la impresión clínica, ni las correlaciones, ni el motivo de consulta.
- Esa separación se decidió el 2026-11-06 (commit `4f4b2ea`, auditoría `C:\dev\ia-api\auditoria\2026-11-06-texto-paciente-y-propuesta\`) y se recertificó el 2026-11-07 (C2 en `auditoria\2026-11-07-recertificacion-y-seguimiento\01-recertificacion-c1-c6.md`). Motivos de entonces: el LLM solo escogía frases de un catálogo cerrado (no aportaba), costaba ~880 tokens con `num_ctx` 4096, y «las cifras jamás pasan por un LLM».
- El «modelo anterior» (commit `39c8cb5`, 2026-10-12, «resumen paciente») generaba la explicación en la misma llamada con un bloque «PERFIL EDUCATIVO» y la limitaba a frases del catálogo: no aprovechaba la impresión clínica. La visión original del dueño está en `C:\dev\ia-api\PROPUESTA_RESUMEN_PACIENTE.md` (histórico; su ejemplo «Tus ojos se encuentran saludables» está prohibido): traducir dioptrías y pruebas a lo que se vive en el día a día, con recomendaciones prácticas, sin diagnósticos alarmistas.
- Laravel ya acepta `explicacion_paciente_estado=generada` con `origen_explicacion=llm` (`IaApiService.php`, `FormEditor.php`, `IaGenerationContext.php`). El optometrista revisa, puede editar y aprueba antes del PDF. El PDF trae además «Cómo leer su receta» (`app/Support/Recetas/LecturaRecetaPaciente.php`, determinista, con las cifras de cada ojo).
- Infraestructura nueva del 2026-11-07 (sin commit): registro de tareas `app/tareas/` (fichas `receta-clinica`, `explicacion-paciente` [hoy `cpu`], `seguimiento-whatsapp`), guardián de 8k en `app/providers/ollama.py` con conteo exacto (`app/tareas/presupuesto.py`), planificador GPU `app/gpu_scheduler.py`, `scripts/probar_enrutado.py`, guía `COMO_AGREGAR_UNA_TAREA.md`. El seguimiento de WhatsApp (`app/seguimiento/`) ya resolvió un problema parecido: Qwen redacta, validador determinista, segunda pasada de verificación, respaldo del catálogo.

## 3. Requerimiento

- **R1. Un único proceso.** La explicación al paciente nace en la misma petición y del mismo contexto que la impresión clínica, después de que esta pasó por las correlaciones deterministas y la depuración. No es una función aparte con datos propios.
- **R2. Qwen hace la inferencia.** Qwen traduce el contenido clínico a lenguaje del paciente, lo más entendible posible. Explica qué significa su graduación y sus hallazgos en la vida diaria («qué es lo que ve»: de lejos, de cerca, letras pequeñas, pantallas, de noche…) y qué se le recomienda y por qué. Trato de usted, frases cortas, sin tecnicismos o explicándolos.
- **R3. Fidelidad total.** No afirma nada que no esté sustentado por la impresión clínica final o por los datos y correlaciones deterministas del caso. No contradice la impresión clínica. No diagnostica más allá de ella. No promete resultados. No dice «sano», «normal», «no necesita» ni equivalentes.
- **R4. Urgencias.** Si hay hallazgo urgente o derivación, se comunica de forma clara, sin alarmar y sin diluirla.
- **R5. El clínico manda.** El texto clínico certificado no cambia de comportamiento (misma salida clínica ante la misma respuesta del modelo) y nunca se pierde por culpa del texto del paciente.
- **R6. Respaldo.** Si la parte del paciente falla, tarda, excede el presupuesto o no pasa la validación, se entrega la plantilla CPU actual (estado `plantilla`) y el clínico sale igual.
- **R7. 8k.** Toda llamada pasa por el guardián del proveedor: prompt + num_predict ≤ 7782 con `num_ctx` 8192.
- **R8. Tiempo.** La receta es interactiva: tope de tiempo para la parte del paciente y timeouts coherentes entre ia-api y Laravel (hoy `IA_API_TIMEOUT=15` en Laravel).
- **R9. Revisión humana.** Se conserva: el optometrista ve, edita y aprueba antes del PDF; la UI distingue texto de la IA y plantilla.
- **R10. Escalable.** La ficha del registro, `/v1/tareas`, `/v1/metricas` y `probar_enrutado.py` reflejan las llamadas reales.

## 4. Restricciones del entorno (obligatorias en propuestas e implementación)

- No correr Ollama real (no hay GPU aquí): pruebas con Ollama simulado; tokenizador oficial de Qwen3.5-9B para medir: `C:\Users\carlo\AppData\Local\Temp\claude\ff364ab545173299\55dde339-7bed-4855-989c-de526444904c\scratchpad\descargas-qwen\tokenizer.json` (con `C:\dev\ia-api\.venv`, `tokenizers` y `app.tareas.presupuesto.renderizar`).
- Base de datos: el MySQL de XAMPP que el dueño ya tiene corriendo (no arrancarlo ni apagarlo). Nada de SQLite. PHPUnit solo con una base exclusiva propia (`optica_<tema>_testing_20261107`), verificando la conexión efectiva; nunca `laravel` ni `laravel_testing`; nunca dos PHPUnit a la vez en el mismo árbol.
- Archivos en UTF-8; ia-api con CRLF; optica con LF. Escribir desde Python, no desde PowerShell 5.1.
- Sin commits, sin push, sin borrar ramas, sin tocar `.env`, sin imprimir secretos. Logs sin contenido clínico (solo tamaños, estados, motivos).
- Los dos repos tienen trabajo sin commit del 2026-11-07: no revertirlo ni reformatearlo.
