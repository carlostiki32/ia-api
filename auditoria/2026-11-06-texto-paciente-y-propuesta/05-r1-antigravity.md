===== antigravity (ok, 260.3s) =====
# Crítica Técnica y Clínica: Propuesta ia-api Multitarea y WhatsApp

---

## 1. Errores de hecho frente al código

1. **Destinatario "Tutor si es menor" inexistente:**
   - *Borrador C.2 y C.3:* Afirma *"destinatario (paciente o tutor si es menor)"* y *"el mensaje se dirige al tutor"*.
   - *Código real:* En [`Paciente.php`](file:///C:/Users/Uriel%20Rojo/Documents/opt/app/Models/Paciente.php#L23-L37) y sus migraciones, **no existen** columnas (`tutor_nombre`, `tutor_telefono`, `parentesco`) ni relaciones a tutores en el modelo. El mensaje solo tiene como destinatario a `$paciente->nombre` y `$paciente->telefono`.
2. **Inexistencia de bandera de consentimiento en `Paciente`:**
   - *Borrador C.2:* *"selecciona pacientes del tenant en `vencido` o `proximo`... con consentimiento"*.
   - *Código real:* En [`Paciente.php`](file:///C:/Users/Uriel%20Rojo/Documents/opt/app/Models/Paciente.php#L23-L37), no existe ningún campo `consentimiento` ni `opt_in_whatsapp`. El comando programado propuesto fallaría o seleccionaría 0 registros.
3. **Supervisor en VPS sin worker para la cola `ia`:**
   - *Borrador C.2:* *"Encola un job por paciente en la cola `ia` (un solo proceso...)"*.
   - *Código real:* En [`deploy-vps-ubuntu.md:924-1014`](file:///C:/Users/Uriel%20Rojo/Documents/opt/docs/deploy-vps-ubuntu.md#L924-L1014), Supervisor solo atiende colas `pdf` y `default`. Un job encolado en `ia` se quedará huérfano en Redis indefinidamente.
4. **Estados del semáforo incompletos:**
   - *Borrador C.1:* Omite el estado **`SinSeguimiento`** (`'sin_seguimiento'`, etiqueta *"Sin programar"*), definido explícitamente en [`PacienteSeguimientoEstado.php:22`](file:///C:/Users/Uriel%20Rojo/Documents/opt/app/Enums/PacienteSeguimientoEstado.php#L22). Además, confunde el nombre del case `Descartado` con su etiqueta de UI *"Seguimiento pausado"*.
5. **Formato de variables incompatible con Laravel:**
   - *Borrador C.2 y C.3:* Especifica placeholders `{paciente}` y `{clinica}` (sintaxis Python).
   - *Código real:* [`whatsapp.php:10-11`](file:///C:/Users/Uriel%20Rojo/Documents/opt/lang/es/whatsapp.php#L10-L11) y [`SeguimientoWhatsappMessageBuilder.php:9-12`](file:///C:/Users/Uriel%20Rojo/Documents/opt/app/Support/WhatsApp/SeguimientoWhatsappMessageBuilder.php#L9-L12) utilizan la convención nativa de Laravel `:paciente` y `:clinica`.
6. **Contrato de configuración acoplado a URL completa:**
   - *Borrador B.3:* Asume que Laravel puede invocar `/v1/tareas/{tipo}` dinámicamente.
   - *Código real:* [`services.php:35-36`](file:///C:/Users/Uriel%20Rojo/Documents/opt/config/services.php#L35-L36) y [`IaApiService.php:39`](file:///C:/Users/Uriel%20Rojo/Documents/opt/app/Services/IaApiService.php#L39) esperan `IA_API_IMPRESION_CLINICA_ENDPOINT` y `IA_API_HEALTH_ENDPOINT` como URLs completas individuales, sin un `base_url` para enrutamiento polimórfico.

---

## 2. Desacuerdos técnicos y clínicos

### 1. [BLOQUEANTE] Lote nocturno masivo contra PC local apagable
- **Problema:** La RTX 3070 Ti está en una máquina física conectada por Cloudflare Tunnel (no en un datacenter con SLA). De noche, la máquina se apaga, suspende o reinicia por actualizaciones de Windows. Correr un cron nocturno saturará la cola de Redis de reintentos fallidos y generará decenas de borradores que quedarán desfasados si el estado del paciente cambia antes de que la óptica abra.
- **Alternativa:** **Generación bajo demanda (Lazy On-Demand) con caché en BD.** Al dar clic en "WhatsApp" en el listado, se abre un modal de vista previa: si existe borrador válido para ese `base_hash`, lo muestra (0 ms GPU); si no, solicita la inferencia con timeout de 4–5 s. Si la PC está apagada o la GPU ocupada, cae inmediatamente a la plantilla pre-redactada de [`whatsapp.php`](file:///C:/Users/Uriel%20Rojo/Documents/opt/lang/es/whatsapp.php#L10-L11).

### 2. [BLOQUEANTE] Suposición ficticia de "Tutor" y brecha de consentimiento LFPDPPP
- **Problema:** En México (LFPDPPP), la salud visual y antecedentes refractivos son datos personales sensibles. Intentar deducir un "tutor" sin campos de base de datos provocará que el LLM salude a un menor en un teléfono ajeno o alucine parentescos.
- **Alternativa:** El mensaje debe dirigirse con respeto neutro al nombre registrado en el expediente (`:paciente`), sin intentar inferir relaciones familiares. El contenido no debe contener diagnósticos clínicos ni cifras médicas, limitándose a recordatorios de confort visual y periodicidad de control.

### 3. [IMPORTANTE] Sobreingeniería de router dinámico (`/v1/tareas/{tipo}`)
- **Problema:** Crear un registry dinámico en FastAPI rompe la generación de esquemas OpenAPI, destruye la validación automática de Pydantic a nivel de ruta y obliga a parsear `dict` crudo en un despachador manual. Para un sistema con 2 tareas reales, esto es sobreingeniería innecesaria.
- **Alternativa:** **Endpoints dedicados y fuertemente tipados:** `POST /v1/inferencia/receta-clinica` y `POST /v1/inferencia/seguimiento-whatsapp`, inyectando el planificador de GPU compartido con `Depends(get_gpu_slot)`.

### 4. [IMPORTANTE] Esquema de salida "Frankenstein" (`hechos: [ids]`)
- **Problema:** Que el LLM seleccione IDs de hechos para luego concatenarlos literalmente crea un mensaje fragmentado (saludo blando + bloque rígido prefabricado + cierre) y desperdicia 9B de parámetros en una tarea que un `if/else` en Python resuelve en microsegundos. Además, el límite estricto de 50–110 palabras causará frecuentes rechazos de validación por desajuste métrico entre partes.
- **Alternativa:** El backend en Python/Laravel selecciona deterministamente los hechos aplicables (meses transcurridos, lente actual, uso de pantallas), los envía como premisas fijas en el prompt, y el LLM redacta el mensaje cohesivo completo bajo JSON Schema `{ "mensaje": "..." }`.

### 5. [MENOR] 503 + Retry-After innecesario en colas de Laravel
- **Problema:** Lanzar 503 con `Retry-After` para tareas de fondo complica la gestión en Laravel Worker sin necesidad si se adopta el modelo interactivo bajo demanda.
- **Alternativa:** Prioridad en memoria dentro de FastAPI (`asyncio.PriorityQueue`): las peticiones de receta clínica siempre desalojan de la cola de espera a cualquier tarea de seguimiento.

---

## 3. Dictamen sobre los 6 puntos clave

- **(a) Enrutamiento:** **Endpoints separados.** Mantiene contratos Pydantic limpios, documentación Swagger automática y observabilidad directa sin metaprogramación.
- **(b) Planificador con prioridad:** **Prioridad interna en memoria SÍ; 503 para lote NO.** La prioridad interactiva debe vivir en `app/gpu_scheduler.py` dando paso inmediato a recetas clínicas sobre cualquier petición de fondo.
- **(c) Formato de salida:** **Prosa fluida guiada por hechos deterministas.** El backend inyecta los hechos como restricciones en el prompt y el LLM redacta un texto fluido y natural, validado con lista negra léxica (sin patologías, sin miedo, sin promesas).
- **(d) Generación nocturna vs al vuelo:** **Al vuelo (on-demand) en vista previa.** Es la única arquitectura resiliente ante la desconexión física de la PC del optometrista.
- **(e) Datos y privacidad (LFPDPPP):** SÍ enviar: tiempo desde última revisión, tipo de lente general, si incluye costo, uso de pantallas. **NUNCA enviar:** agudezas visuales con dioptrías exactas, keratometría ni diagnósticos. WhatsApp se visualiza en pantallas de bloqueo y teléfonos compartidos.
- **(f) Fase 2 (patologías en WhatsApp):** **RECHAZAR TERMINANTEMENTE.** Comunicar patologías (cataratas, glaucoma, retinopatía) por WhatsApp vulnera el secreto médico y genera alarma innecesaria. Esas condiciones solo deben informarse presencialmente o mediante el informe clínico PDF firmado.

---

## 4. Vacíos no contemplados en la propuesta

1. **Circuit Breaker en Laravel:** Si la PC con la GPU está apagada, un timeout de Guzzle de 15 s congelará la interfaz Livewire. Se requiere un health-check en Redis (TTL 30 s) para desactivar la llamada a la IA de inmediato si el túnel está caído.
2. **Desacoplamiento entre "generar" y "notificar":** Hoy, [`IndexPage.php:90`](file:///C:/Users/Uriel%20Rojo/Documents/opt/app/Livewire/Pacientes/IndexPage.php#L90) marca `seguimiento_notificado_at = now()` al abrir el enlace `wa.me`, sin verificar si el mensaje realmente se envió.
3. **Filtro anti-alucinaciones comerciales:** Validación estricta en FastAPI contra menciones de precios, descuentos o promesas curativas.

---

## 5. Veredicto final por sección

- **B.2 (Viabilidad N tareas en una GPU):** **ACEPTO con cambios:** Viable solo si se descarta el lote nocturno pesado y se acepta la penalización de prefill (~1–2 s) al alternar prompts.
- **B.3 (Diseño registro + enrutador + planificador):** **ACEPTO con cambios:** Reemplazar el registry dinámico y `POST /v1/tareas/{tipo}` por **endpoints dedicados tipados**. Planificador en memoria con prioridad para recetas.
- **B.4 (Tareas candidatas):** **ACEPTO tal cual:** El orden propuesto (Receta $\rightarrow$ WhatsApp $\rightarrow$ Evolución $\rightarrow$ Entrega) es certero.
- **C.2 (Flujo propuesto):** **RECHAZO:** Eliminar el cron nocturno y la cola `ia`. Implementar **generación lazy on-demand** al pulsar el botón de WhatsApp con modal de edición y fallback instantáneo a plantilla.
- **C.3 (Límites éticos y legales):** **ACEPTO con cambios:** Eliminar la figura inexistente de "tutor". **Cancelar definitivamente la Fase 2 de patologías**.
- **C.4 (Fases):** **ACEPTO con cambios:** F1 debe enfocarse en el scheduler de prioridades y el endpoint de WhatsApp; F3 debe centrarse en el modal Livewire bajo demanda en lugar de workers de fondo.

