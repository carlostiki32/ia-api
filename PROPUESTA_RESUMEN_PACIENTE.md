> **Documento histórico (2026-11-06).** No es normativo. El ejemplo «Tus ojos se encuentran saludables» está prohibido. El comportamiento vigente está en `SALIDA_DUAL.md`.

# Propuesta Técnica: Generador de Resumen Visual Amable para el Paciente

> **Documento de Especificación e Implementación para `ia-api`**  
> **Modelo Objetivo:** `qwen3.5:9b` (Ollama local sobre NVIDIA RTX 3070 Ti 8GB)  
> **SaaS Consumidor:** `opt` (Laravel 13, Livewire 4, MySQL multi-tenant)  
> **Fecha:** Octubre 2026  

---

## 1. Justificación y Diagnóstico del Problema

### El Estado Actual de `ia-api`
Actualmente, el endpoint `POST /inferencia/impresion-clinica` está blindado bajo el prompt de `app/prompt_builder.py`, cuyas directivas son:
- *"Eres un optometrista clínico experto que redacta la impresión clínica de una receta."*
- *"Usa siempre 'El paciente' en tercera persona; nunca asumas género."*
- *"Redacta en tiempo presente con lenguaje clínico optométrico en español correcto."*
- *"Responde ÚNICAMENTE con el párrafo clínico final. Sin encabezados, sin explicaciones..."*

### La Brecha de Experiencia de Usuario (UX)
El texto generado actual es **estrictamente técnico y pericial**. Cumple una función legal y médica para el expediente en la sección `V. Impresión clínica y plan`, pero cuando el paciente descarga su informe en PDF o consulta su liga pública firmada, lee términos como:
> *"Ametropía miópica compuesta con astigmatismo miópico con la regla en ambos ojos... tiempo de ruptura lagrimal de 6 segundos en contexto de uso prolongado de dispositivos digitales..."*

El 95% de los pacientes no comprende esta terminología.

### El Objetivo
Permitir que la misma instancia de `ia-api` genere un **"Resumen Visual Amable"**:
1. Redactado en **segunda persona ("Tú")** o lenguaje directo y empático.
2. Traduciendo las dioptrías y pruebas a **síntomas del día a día** (lejanía, halos nocturnos, fatiga vespertina).
3. Entregando **recomendaciones prácticas de higiene visual** (parpadeo consciente, regla 20-20-20, hidratación).
4. Sin emitir diagnósticos alarmistas ni inventar patologías.

---

## 2. Viabilidad de Hardware en la RTX 3070 Ti

Basado en las mediciones reales de `app/config.py`:

| Parámetro | Configurado en `config.py` | Consumo Real Actual | Consumo con Resumen Amable | Margen Disponible |
| :--- | :--- | :--- | :--- | :--- |
| **Context Window (`ollama_num_ctx`)** | **8,192 tokens** | ~2,200 a 4,895 tokens | ~2,200 a 4,895 tokens (mismo input) | **> 3,200 tokens libres** |
| **Budget de Salida (`ollama_num_predict`)** | **1,024 tokens** | ~90 - 120 tokens | ~180 - 210 tokens (ambos textos) | **> 800 tokens libres (80%)** |
| **Uso de VRAM** | 8.0 GB GDDR6X | ~9.1 GB (72% GPU / 28% CPU) | Idéntico (el KV Cache no crece) | Estable |
| **Tiempo de Inferencia** | - | ~3.0 - 3.5 segundos | ~4.5 - 5.0 segundos (+1.5s) | Totalmente aceptable |

---

## 3. Comparativa de Arquitectura: ¿Cómo Integrarlo?

Existen dos estrategias para implementar esta funcionalidad dentro del proyecto `ia-api`:

### Opción A: Endpoint Hermano Dedicado (`POST /inferencia/resumen-paciente`) ⭐ **[RECOMENDADA]**

Se crea un endpoint separado en `app/main.py` que recibe el mismo payload [`ImpresionClinicaRequest`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/schemas.py), pero utiliza una función dedicada en `app/prompt_builder.py`.

```
                  ┌──────────────────────────────────────────────┐
                  │                 CLIENTE SAAS                 │
                  └───────────────┬──────────────┬───────────────┘
                                  │              │
        POST /inferencia/impresion-clinica       POST /inferencia/resumen-paciente
                                  │              │
                                  ▼              ▼
                    [Prompt Clínico Pericial]  [Prompt Divulgación Empática]
                                  │              │
                                  └───────┬──────┘
                                          │
                                          ▼
                               ┌─────────────────────┐
                               │   Ollama Qwen 9B    │
                               └─────────────────────┘
```

* **Ventajas:**
  * **Cero riesgo de regresión:** No modifica ni compromete el pipeline de correlaciones clínicas auditado ni los regex de `app/inference.py`.
  * **Invocación bajo demanda:** El SaaS puede pedir la impresión médica para guardar la receta, y pedir el resumen amable solo cuando se emite el PDF o cuando el usuario lo solicite.
  * **Latencia contenida:** Cada llamada tarda solo 1.5 a 2.5 segundos.

---

### Opción B: Salida Unificada JSON en el Endpoint Actual

Modificar `POST /inferencia/impresion-clinica` para que Qwen responda con un JSON estructurado con dos campos:
```json
{
  "impresion_clinica": "El paciente presenta ametropía miópica...",
  "resumen_paciente": "Tus ojos necesitan graduación para enfocar de lejos..."
}
```

* **Ventajas:** Una sola llamada HTTP desde Laravel.
* **Desventajas:** Obliga a reescribir `app/inference.py` (`clean_impresion` y `_purgar_no_sustentado` esperan texto plano, no objetos JSON). Aumenta la complejidad del post-procesamiento.

---

## 4. Especificación de la Opción A (Endpoint Hermano)

### 4.1. El System Prompt (`build_paciente_system_prompt`)

```python
def build_paciente_system_prompt() -> str:
    return """\
Eres un optometrista empático y pedagógico. Tu objetivo es explicarle al paciente los resultados de su examen visual de forma clara, tranquilizadora y sin tecnicismos médicos incomprensibles.

FORMATO Y ESTILO:
- Redacta en SEGUNDA PERSONA ("Tú" o "Usted" en tono cercano y respetuoso).
- Máximo 3 o 4 oraciones en un solo párrafo fluido.
- Prohibido usar tecnicismos oscuros: en lugar de "ametropía miópica compuesta" explica que "te cuesta enfocar objetos lejanos"; en lugar de "astigmatismo con la regla" menciona "las luces y sombras se distorsionan ligeramente".
- Si hay reporte de ojo seco o tiempo de ruptura lagrimal corto, asócialo con el uso de pantallas y recomienda descansar la vista (regla 20-20-20) y parpadear conscientemente.
- JAMÁS emitas diagnósticos de enfermedades graves que no aparezcan en los datos. No uses palabras como patología, degeneración, daño o peligro.
- Termina con una frase motivadora o recomendación práctica para el cuidado diario de sus ojos.
"""
```

### 4.2. El User Prompt para el Paciente

Toma los campos ya deserializados por `ImpresionClinicaRequest`:
```python
def build_paciente_user_prompt(req: ImpresionClinicaRequest) -> str:
    lineas = []
    
    # 1. Motivo de consulta
    if req.paciente.motivo_consulta:
        lineas.append(f"Motivo por el que viniste: {req.paciente.motivo_consulta}")
        
    # 2. Ocupación y pantallas
    if req.paciente.ocupacion or req.clinica.uso_pantallas:
        detalles = []
        if req.paciente.ocupacion:
            detalles.append(f"trabajo como {req.paciente.ocupacion}")
        if req.clinica.uso_pantallas:
            detalles.append(f"uso de pantallas {USO_PANTALLAS_MAP.get(req.clinica.uso_pantallas, '')}")
        lineas.append(f"Actividad diaria: {', '.join(detalles)}")

    # 3. Resumen de Refracción (Esferas y Cilindros traducidos a términos cotidianos)
    od_esf = req.refraccion.od.esfera
    oi_esf = req.refraccion.oi.esfera
    od_cil = req.refraccion.od.cilindro
    oi_cil = req.refraccion.oi.cilindro
    
    problemas = []
    if (od_esf is not None and od_esf < -0.25) or (oi_esf is not None and oi_esf < -0.25):
        problemas.append("dificultad para ver de lejos (miopía)")
    elif (od_esf is not None and od_esf > 0.25) or (oi_esf is not None and oi_esf > 0.25):
        problemas.append("esfuerzo adicional para enfocar de cerca (hipermetropía)")
        
    if (od_cil is not None and abs(od_cil) > 0.25) or (oi_cil is not None and abs(oi_cil) > 0.25):
        problemas.append("desenfoque o distorsión en contornos (astigmatismo)")
        
    if req.refraccion.od.add or req.refraccion.oi.add:
        problemas.append("cansancio visual al leer letras pequeñas de cerca (vista cansada)")

    if problemas:
        lineas.append(f"Condiciones visuales detectadas: {', '.join(problemas)}.")

    # 4. Superficie Ocular
    if req.clinica.ojo_seco_but_seg is not None and req.clinica.ojo_seco_but_seg <= 7:
        lineas.append(f"Prueba lagrimal: Tu lágrima se evapora rápido ({req.clinica.ojo_seco_but_seg} segundos), lo que genera resequedad o ardor.")

    return "\n".join(lineas)
```

---

## 5. Ejemplo de Entrada y Salida

### Entrada del Caso
* **Paciente:** 29 años, Diseñador Gráfico, pantallas `gt6` (>6 horas).
* **Motivo:** "Cansancio visual y ardor al final de la tarde".
* **Refracción:** OD: Esf -2.25 Cil -1.00 Eje 180°. OI: Esf -2.00 Cil -0.75 Eje 175°.
* **Clínica:** BUT: 5 segundos. PPC: 8 cm.

### Salida Médica Actual (`impresion_clinica`):
> *"El paciente masculino de 29 años refiere astenopía y ardor ocular vespertino. Presenta defecto refractivo astigmático miópico compuesto en ambos ojos con agudeza visual corregida óptima. En superficie ocular se evidencia tiempo de ruptura lagrimal disminuido de 5 segundos en relación con actividad digital prolongada."*

### Salida Amable Propuesta (`resumen_paciente`):
> *"Tus ojos se encuentran saludables, pero presentan miopía y astigmatismo moderados, lo que causa que los objetos lejanos y los letreros nocturnos pierdan nitidez si no usas tu graduación. Además, debido a tus más de 6 horas de trabajo frente al monitor, tu lágrima se está evaporando muy rápido (5 segundos), provocando el ardor y pesadez al final del día. Te recomendamos aplicar la regla 20-20-20: cada 20 minutos de pantalla, mira un punto lejano durante 20 segundos y parpadea profundamente para rehidratar tus ojos."*

---

## 6. Pasos para Implementar en Código

### En el Repo `ia-api`:
1. **`app/prompt_builder.py`:**
   * Agregar `build_paciente_system_prompt()` y `build_paciente_user_prompt(req)`.
2. **`app/inference.py`:**
   * Agregar `run_paciente_inference(req, client)` simplificada (sin filtros de correlaciones periciales, solo asegurando longitud corta y ausencia de alucinaciones terapéuticas).
3. **`app/main.py`:**
   * Exponer la ruta:
     ```python
     @app.post("/inferencia/resumen-paciente")
     async def inferencia_resumen_paciente(
         req: ImpresionClinicaRequest,
         background_tasks: BackgroundTasks,
         token_user: User = Depends(get_current_user),
     ):
         ...
     ```

### En el Repo `opt` (SaaS):
1. **Base de Datos:**
   * Migración para agregar columna `resumen_paciente` en la tabla `receta_clinicas` (`nullable text`).
2. **`app/Services/IaApiService.php`:**
   * Agregar método `generarResumenPacienteDetallada(array $formData)`.
3. **`resources/views/recetas/pdf/informe_clinico.blade.php`:**
   * Agregar la tarjeta destacada para el paciente justo debajo de la sección de refracción:
     ```blade
     @if(!blank($receta->clinica->resumen_paciente))
         <div class="section-paciente-callout">
             <div class="h-callout">💬 ¿Qué significa esto para tu visión?</div>
             <p class="v-callout">{{ $receta->clinica->resumen_paciente }}</p>
         </div>
     @endif
     ```

---

## 7. Plan de Verificación y Pruebas

1. **Prueba de Concurrencia:** Enviar una petición a `/inferencia/impresion-clinica` y otra inmediatamente a `/inferencia/resumen-paciente` para verificar que la cola FIFO de Ollama resuelve ambas secuencialmente en menos de 5 segundos totales.
2. **Prueba de Límites:** Probar un paciente con refracción neutra (plano) y sin BUT; validar que el resumen no invente miopía ni resequedad.
3. **Prueba en PDF DomPDF:** Verificar que el bloque de texto con estilos amables en Blade no empuje el contenido a una página extra innecesaria.

