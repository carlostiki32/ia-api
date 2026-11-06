===== antigravity (ok, 255.3s) =====
### 1. Tabla de Votación

| Decisión / Fase | Voto | Comentario / Ajuste |
|---|---|---|
| **C1** | **ACEPTO** | Esencial: desliga la explicación de la transposición y calibra cifras exactas con la tabla del PDF. |
| **C2** | **ACEPTO** | Saca la explicación de Qwen; 100 % CPU ahorra prefill crítico y elimina fallos 413. |
| **C3** | **ACEPTO** | Corrige la discordancia de tono con la óptica (cero tuteo). |
| **C4** | **ACEPTO** | Ojo plano descrito por prescripción (0.00 de lejos), sin asumir salud ni usar léxico prohibido. |
| **C5** | **ACEPTO** | Indispensable: el `.env` local tiene 4096; en producción con GPU debe fijarse `OLLAMA_NUM_CTX >= 8192`. |
| **C6** | **ACEPTO** | Depreca el borrador histórico con inferencias no autorizadas ("ojos saludables"). |
| **D-1** | **ACEPTO** | Endpoints tipados y separados (`receta-clinica` y `seguimiento-whatsapp`) sin magia de autodetección. |
| **D-2** | **ACEPTO con ajuste menor: manejo de cancelación** | Al cancelar el cliente HTTP, FastAPI debe propagar la cancelación al request de Ollama para abortar el cómputo y no retener la GPU en vacío antes de ceder el turno. |
| **D-3** | **ACEPTO** | Parámetros y caché particionados por tarea; logs limpios de datos clínicos o sensibles. |
| **D-4** | **ACEPTO** | Pipeline defensivo estricto: el LLM nunca calcula ni inventa hechos clínicos. |
| **D-5** | **ACEPTO** | Resuelve la falta de `IA_API_BASE_URL` en Laravel y aísla la carga en worker `ia` con timeout coherente. |
| **D-6** | **ACEPTO** | Vista previa inmediata sin bloquear al personal; personalización en segundo plano con Livewire. |
| **D-7** | **ACEPTO** | Preparación por lote pospuesta a ventana controlada tras conocer métricas del piloto. |
| **D-8** | **ACEPTO** | Multi-tenant seguro en CLI/colas con `tenant_id` explícito; no pisa ediciones manuales. |
| **D-9** | **ACEPTO** | Desacopla la apertura del enlace de la confirmación real de envío en `paciente_mensajes_ia`. |
| **D-10** | **ACEPTO** | Minimización rigurosa de datos hacia la API (reutiliza `build_patient_profile` sin PII). |
| **D-11** | **ACEPTO** | Prohíbe "progresión" y limita ADD a "apoyo de cerca" sin atribuir edad o presbicia. |
| **D-12** | **ACEPTO** | Hechos clínicos cerrados, firmados y con reglas deterministas de activación. |
| **D-13** | **ACEPTO** | Síntesis robusta: modelo aporta redacción cálida, pero los hechos clínicos son substrings literales exactos. |
| **D-14** | **ACEPTO** | Validador léxico y estructural determinista que rechaza cualquier término clínico fuera de las frases autorizadas. |
| **D-15** | **ACEPTO** | Segunda pasada de auditoría con Qwen a temp 0 como salvaguarda complementaria. |
| **D-16** | **ACEPTO** | Degradación transparente al texto genérico corregido ante cualquier fallo o rechazo. |
| **D-17** | **ACEPTO** | Cumplimiento LFPDPPP: consentimiento registrado y demostrable antes de enviar datos a la API. |
| **D-18** | **ACEPTO** | Menores reciben exclusivamente plantilla genérica al no existir campo ni verificación de tutor legal. |
| **D-19** | **ACEPTO** | Persuasión ética y de servicio; prohíbe explícitamente infundir miedo o urgencia falsa. |
| **D-20** | **ACEPTO** | Exclusión total de patologías o correlaciones en mensajes de seguimiento comercial/preventivo. |
| **F0** | **ACEPTO** | Prioridad correcta: certificar primero la explicación del paciente antes de tocar nuevas rutas. |
| **F1** | **ACEPTO** | Formaliza catálogo firmado, consentimiento y corrección del genérico en Laravel. |
| **F2** | **ACEPTO** | Implementación y regresión HTTP completa en `ia-api`. |
| **F3** | **ACEPTO** | Migración, jobs y vista previa no bloqueante en Laravel. |
| **F4** | **ACEPTO** | Piloto supervisado en GPU real para medir latencias, colisiones de cola y calidad. |
| **F5** | **ACEPTO** | Automatización anticipada condicionada estrictamente a la justificación del piloto. |

---

### 2. Errores de hecho que sigan en la v2

**Ninguno detectado.** Se contrastaron las referencias contra el código:
- [informe_clinico.blade.php](file:///C:/Users/Uriel%20Rojo/Documents/opt/resources/views/recetas/pdf/informe_clinico.blade.php#L490-L531): la tabla de resultado refractivo prescrito (OD/OI con ESF, CIL, EJE, ADD) se ubica exactamente en las líneas 490–531.
- [whatsapp.php](file:///C:/Users/Uriel%20Rojo/Documents/opt/lang/es/whatsapp.php#L9-L12): los textos actuales prometen «garantizar» y `con_costo` no explicita el costo.
- [IndexPage.php](file:///C:/Users/Uriel%20Rojo/Documents/opt/app/Livewire/Pacientes/IndexPage.php#L75-L106): `notificarWhatsApp` asigna `seguimiento_notificado_at = now()` previo al despacho del evento `abrir-enlace-externo`.
- [PacienteSeguimientoEstado.php](file:///C:/Users/Uriel%20Rojo/Documents/opt/app/Enums/PacienteSeguimientoEstado.php#L13-L23): los 6 estados del semáforo coinciden con el enum (`vencido`, `proximo`, `al_dia`, `con_cita`, `descartado`, `sin_seguimiento`).
- [.env](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/.env#L6): `OLLAMA_NUM_CTX=4096` en línea 6.
- [PROPUESTA_RESUMEN_PACIENTE.md](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/PROPUESTA_RESUMEN_PACIENTE.md#L176): contiene la redacción histórica a descartar en la línea 176.
- [schemas.py](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/schemas.py#L51-L52): `_USO_PANTALLAS` utiliza exactamente las claves `("lt2", "btw2_6", "gt6")`.
- [services.php](file:///C:/Users/Uriel%20Rojo/Documents/opt/config/services.php#L34-L43): carece de `IA_API_BASE_URL` (usa endpoints directos).

---

CONSENSO: SÍ

