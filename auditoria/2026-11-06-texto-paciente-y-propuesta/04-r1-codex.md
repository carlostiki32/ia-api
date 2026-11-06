La dirección es viable, pero el borrador promete garantías que todavía no ofrece. Usar más GPU no es, por sí mismo, un objetivo de producto. Revisión estática, sin modificar archivos ni ejecutar inferencias.

**1. Errores de hecho y afirmaciones no acreditadas**

- **Las opciones no son completamente fijas:** el proveedor admite `num_predict` y `response_format` por llamada; ya registra tokens y duraciones. Falta distinguirlos por tarea. [ollama.py:31](<C:/Users/Uriel Rojo/Documents/ia-api/app/providers/ollama.py:31>), [ollama.py:95](<C:/Users/Uriel Rojo/Documents/ia-api/app/providers/ollama.py:95>).
- **Una receta no equivale necesariamente a una llamada:** existen reintentos por transporte, truncamiento y JSON inválido. La estimación de carga debe contemplarlos. [inference.py:881](<C:/Users/Uriel Rojo/Documents/ia-api/app/inference.py:881>).
- **La caché versionada descrita corresponde al modo dual:** las versiones de prompt/perfil/pipeline y sampling se agregan dentro de esa condición. [cache.py:37](<C:/Users/Uriel Rojo/Documents/ia-api/app/cache.py:37>).
- **`build_patient_profile` no construye el perfil propuesto:** interpreta Rx final y ADD; no edad, evolución, visitas ni pantallas. Tampoco admite directamente el nuevo payload. [patient_profile.py:55](<C:/Users/Uriel Rojo/Documents/ia-api/app/patient_profile.py:55>).
- **El respaldo actual incumple los límites propuestos:** promete “garantizar” graduación óptima y prevenir fatiga; además, `con_costo` no informa que existe costo. [whatsapp.php:10](<C:/Users/Uriel Rojo/Documents/opt/lang/es/whatsapp.php:10>).
- **“Notificado” no acredita envío:** se guarda antes de despachar la apertura. El enum incluye también `sin_seguimiento`. [IndexPage.php:90](<C:/Users/Uriel Rojo/Documents/opt/app/Livewire/Pacientes/IndexPage.php:90>), [PacienteSeguimientoEstado.php:22](<C:/Users/Uriel Rojo/Documents/opt/app/Enums/PacienteSeguimientoEstado.php:22>).
- **“Certificado” es injustificado:** la documentación dual declara simulaciones sin modelo real. Los “6319 tests verdes” necesitan evidencia vinculada al commit; no los certifiqué. [SALIDA_DUAL.md:3](<C:/Users/Uriel Rojo/Documents/ia-api/SALIDA_DUAL.md:3>).

**2. Desacuerdos**

1. **IMPORTANTE — API y abstracción.** Prefiero endpoints separados, tipados, para las dos funciones actuales. `/v1/tareas/{tipo}` es viable con esquemas explícitos en OpenAPI, pero un registro dinámico añade complejidad prematura. Un único endpoint con discriminador `tipo` también funciona mediante unión discriminada; aporta menos claridad operativa. Laravel debe declarar el tipo: ningún LLM debe “detectarlo”. Conservaría el endpoint clínico mediante un adaptador mínimo.

2. **BLOQUEANTE — Prioridad no significa interrupción.** Una receta puede esperar detrás del lote **ya iniciado**. El semáforo actual es local al proceso; sustituirlo por otra cola local no resuelve múltiples workers. [main.py:33](<C:/Users/Uriel Rojo/Documents/ia-api/app/main.py:33>). Alternativa: un único ejecutor, admisión de lote solo sin trabajo interactivo pendiente, generaciones cortas y espera máxima documentada. Acepto `503 + Retry-After`, con backoff, jitter y caducidad en Laravel. Hay que comprobar que cancelar HTTP realmente detiene Ollama antes de liberar capacidad.

3. **BLOQUEANTE — El esquema deja abierta la alucinación.** Acepto hechos literales por ID sobre prosa libre “validada”. Pero `puente_personal` puede afirmar “su visión ha empeorado” sin usar ningún ID. Todos los campos deben restringirse a variantes aprobadas o contenido verificable. Validar elegibilidad de cada ID, duplicados y **mensaje ensamblado**, incluido costo. Las listas de palabras prohibidas no prueban fidelidad. Permitir cero hechos evita rellenar mensajes.

4. **BLOQUEANTE — Reglas clínicas insuficientes.** ADD permite describir apoyo cercano; no demuestra envejecimiento ni presbicia. [SALIDA_DUAL.md:87](<C:/Users/Uriel Rojo/Documents/ia-api/SALIDA_DUAL.md:87>). Una diferencia de equivalente esférico no demuestra progresión y omite cambios de cilindro/eje. Exigir recetas comparables, procedencia y cronología documentadas; expresar únicamente cambios registrados. No convertir “última receta” o cantidad de recetas en evaluación o visitas confirmadas.

5. **IMPORTANTE — Lote frente a generación al pulsar.** Prefiero preparación anticipada en una ventana donde la PC esté disponible, no necesariamente nocturna. Al pulsar: mostrar inmediatamente borrador vigente o plantilla segura; generación opcional asíncrona. No bloquear la apertura por GPU apagada. Antes de generalizar el lote, medir demanda real: cinco recetas semanales no indican cuántos seguimientos habrá.

6. **BLOQUEANTE — Persistencia y aislamiento.** En consola puede desaparecer el filtro automático de tenant. [BelongsToTenant.php:24](<C:/Users/Uriel Rojo/Documents/opt/app/Models/Concerns/BelongsToTenant.php:24>). Cada job necesita tenant explícito, consultas acotadas y unicidad por paciente/ciclo/base. Revalidar cita, pausa, consentimiento, costo y base al terminar y abrir. Una respuesta antigua no debe sobrescribir una edición humana. Separar apertura de WhatsApp de envío confirmado manualmente.

7. **BLOQUEANTE — Minimización y privacidad.** **Sí enviaría:** estado relativo, política de costo, destinatario verificado y hechos elegibles derivados determinísticamente; pantallas solo si están registradas. **No enviaría por defecto:** dos Rx completas, ocupación libre, visitas, motivo, notas, patologías, identificadores ni fechas exactas. Formalizar el nuevo contrato en el diccionario; el actual contiene una sola Rx. [IaApiService.php:446](<C:/Users/Uriel Rojo/Documents/opt/app/Services/IaApiService.php:446>).

   Seudonimización no equivale a disociación. Una bandera no acredita consentimiento: documentar finalidad, evidencia, revocación y base jurídica; no presumir excepción asistencial para reactivación comercial. También definir responsables/encargados, retención y recorrido VPS–Cloudflare–PC–WhatsApp. Sin autorización aplicable, el genérico tampoco queda automáticamente permitido. [LFPDPPP vigente, arts. 2, 7–15 y 18](https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPDPPP.pdf). Verificar tutor y teléfono autorizado; hoy el modelo no documenta esa relación.

8. **IMPORTANTE — Candidatas y patologías.** `resumen_evolucion` no es de riesgo bajo por ser interno: puede alterar decisiones clínicas. Haría cálculos y cronología deterministas. `mensaje_entrega` requiere instrucciones realmente registradas. **Rechazo Fase 2 de patologías en campañas persuasivas**; una comunicación asistencial sería otro flujo, dirigido por el profesional.

**3. Qué falta para considerarla sólida**

Pruebas de aislamiento entre tenants, carreras e invalidación; regresión HTTP completa; presupuestos coordinados de timeout/reintentos; worker `ia` y `retry_after`; versiones de modelo/prompt/catálogo; regeneración que gestione caché explícitamente; telemetría sin contenido clínico —hoy puede registrarse el payload— [IaApiService.php:113](<C:/Users/Uriel Rojo/Documents/opt/app/Services/IaApiService.php:113>). Medir latencia real, revisión humana y bajas/quejas. Comparar conversión con asignación aleatoria; abrir WhatsApp no demuestra exposición.

**4. Dictamen por sección**

| Sección | Dictamen |
|---|---|
| B.2 | **ACEPTO con cambios:** retirar garantías de espera y latencias supuestas. |
| B.3 | **ACEPTO con cambios:** simplificar, tipar y asegurar ejecución única. |
| B.4 | **ACEPTO con cambios:** retirar “certificado” y reclasificar riesgos. |
| C.2 | **ACEPTO con cambios:** cerrar prosa, minimizar datos y resolver concurrencia. |
| C.3 | **ACEPTO con cambios:** consentimiento demostrable; **RECHAZO** patologías persuasivas. |
| C.4 | **RECHAZO:** no imponer refactor y planificador antes de validar contrato, respaldo y utilidad del piloto. |