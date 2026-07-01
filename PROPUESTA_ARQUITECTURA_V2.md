# Propuesta de arquitectura v2 para la API de inferencia clínica optométrica

## Contexto

Este documento resume un análisis crítico del proyecto actual de API para inferencia clínica optométrica usando Qwen 3.5 9B sobre hardware NVIDIA RTX 3070 Ti. El objetivo no es solo valorar si el sistema responde bien, sino evaluar si la arquitectura actual es la más adecuada para un caso de uso clínico y qué diseño sería superior.

La conclusión corta es la siguiente:

- La arquitectura actual es funcional y útil como prototipo.
- No es la mejor arquitectura para un sistema clínico serio, auditable y mantenible.
- La propuesta más sólida es una arquitectura determinista-first, con el modelo de IA actuando como capa de redacción o estilización limitada y no como fuente principal de decisión clínica.

---

## 1. Resumen ejecutivo

El sistema actual recibe un payload clínico estructurado, aplica correlaciones clínicas mediante reglas deterministas, construye un prompt largo y delega la generación del informe final a un modelo de lenguaje. Esto genera resultados que pueden verse fluidos y útiles, pero presenta problemas estructurales importantes:

1. La lógica clínica está demasiado dispersa entre reglas, prompt y modelo.
2. El modelo es utilizado como autor principal del informe, cuando debería ser un componente secundario.
3. La salida no está restringida a un esquema formal ni verificable.
4. La arquitectura mezcla demasiadas responsabilidades en un solo flujo.
5. La seguridad clínica, trazabilidad y audibilidad no son lo suficientemente sólidas para un uso médico serio.

Por ello, la arquitectura actual puede servir como MVP, pero no como arquitectura final para una solución clínica robusta.

---

## 2. Qué hace hoy el sistema

El flujo actual se puede resumir así:

1. Se recibe un payload estructurado con datos de refracción, AKR, hallazgos clínicos y contexto del paciente.
2. Se valida el input con Pydantic.
3. Se ejecutan correlaciones clínicas deterministas.
4. Se construye un prompt largo con ese contexto.
5. Se envía el prompt a un modelo local o remoto.
6. Se postprocesa el resultado para limpiar formato y eliminar artefactos del modelo.
7. Se devuelve un párrafo final como respuesta HTTP.

Esto es una arquitectura válida para una prueba de concepto, pero no es la arquitectura más adecuada para un sistema que debe ser consistente, auditable y clínicamente responsable.

---

## 3. Crítica profunda de la arquitectura actual

### 3.1 Demasiado prompt-driven y poco sistema de decisión

La lógica clínica actual está repartida entre:

- reglas en el módulo de correlaciones,
- instrucciones en el prompt del sistema,
- lógica de postprocesamiento,
- y la propia inferencia del modelo.

Esto implica que la “decisión clínica” no está formalizada en una capa de negocio clara. En lugar de eso, depende de la capacidad del modelo para interpretar un prompt complejo.

Problema central:
- El sistema no posee una capa formal de hechos clínicos estructurados.
- La decisión clínica está implícita en texto libre y en comportamiento generativo.

Esto es una debilidad seria para cualquier sistema que tenga impacto clínico.

### 3.2 El modelo está siendo usado como autor principal

El sistema genera un párrafo libre, no un informe estructurado. Eso significa que el modelo debe decidir:

- qué incluir,
- qué priorizar,
- qué reformular,
- y qué omitir.

Eso es demasiado para una pieza de software que debería estar gobernada por reglas claras, trazabilidad y control de calidad.

En una solución clínica, el modelo debería actuar como componente de redacción o estilización, no como fuente principal de contenido.

### 3.3 Mezcla excesiva de responsabilidades

La arquitectura actual reúne varias responsabilidades en un mismo flujo:

- validación HTTP,
- concurrencia y cola,
- cache,
- selección de proveedor,
- prompt engineering,
- lógica clínica,
- postprocesamiento del texto,
- y publicación del resultado.

Eso genera acoplamiento excesivo. Un cambio pequeño en una de estas capas puede alterar la calidad general del output.

### 3.4 El fallback entre proveedores introduce inconsistencia

El sistema puede usar Ollama o NVIDIA según configuración. Eso tiene sentido como estrategia de resiliencia, pero no es una arquitectura ideal para consistencia clínica.

Problemas concretos:

- el mismo payload puede terminar en un modelo distinto,
- la redacción puede variar,
- el tono y la estructura del informe pueden cambiar,
- y el cache no garantiza un comportamiento uniforme si la estrategia de inferencia cambia.

Para un sistema que debe producir inferencias consistentes, esta heterogeneidad introduce ruido.

### 3.5 Falta de salida estructurada y validable

Aunque el input es bien tipado, la salida no está restringida por un esquema formal. Se devuelve un texto libre, no un documento clínico estructurado.

Eso significa que no existe:

- un esquema obligatorio de salida,
- secciones normalizadas,
- campos verificables,
- ni una forma robusta de validar si el informe cubre los hallazgos clave.

Esto es una deficiencia importante si se busca una arquitectura seria y auditable.

### 3.6 La lógica clínica está mal ubicada

Las correlaciones están bien intencionadas, pero se implementan como texto libre y reglas heurísticas. Eso es insuficiente para un sistema médico robusto.

La arquitectura debería distinguir claramente entre:

- hechos observados,
- interpretaciones clínicas,
- recomendaciones,
- y redacción final.

Hoy esas capas se mezclan.

### 3.7 Falta de seguridad clínica real

No hay una estrategia formal de:

- guardrails clínicos,
- abstención cuando la información es insuficiente,
- priorización segura de hallazgos urgentes,
- revisión humana para hallazgos críticos,
- ni control de sobreinterpretación del modelo.

Esto no es un detalle menor. En un contexto médico, la seguridad no puede depender solo de la fluidez del texto generado.

---

## 4. ¿Es la arquitectura actual la mejor para este propósito?

No.

La arquitectura actual es una buena solución de prototipo, pero no la mejor para una API clínica optométrica seria.

### Lo que sí hace bien

- Es rápida de implementar.
- Permite probar el concepto.
- Integra reglas deterministas y generación con LLM.
- Es suficientemente flexible para iterar.

### Lo que falla

- No separa bien la lógica clínica del lenguaje.
- No ofrece salida estructurada y validable.
- No es suficientemente auditable.
- No está diseñada para seguridad clínica.
- No es escalable desde el punto de vista de calidad y gobernanza.

---

## 5. Propuesta de nueva arquitectura

### 5.1 Arquitectura recomendada: determinista primero, LLM como capa de estilización limitada

La propuesta más adecuada para este tipo de API es la siguiente:

#### Capa 1: Ingesta y normalización

- Recibe el payload.
- Normaliza campos.
- Valida el esquema de entrada.
- Detecta si el payload está incompleto o ambiguo.

#### Capa 2: Motor de hechos clínicos estructurados

En vez de pasar directamente a texto libre, el sistema extrae hechos estructurados como:

- hallazgo clínico,
- localización,
- severidad,
- categoría,
- evidencia,
- y confianza.

Esto convierte el problema en una representación formal, no en un prompt gigante.

#### Capa 3: Motor de reglas clínicas

Esta capa evalúa reglas explícitas para:

- detectar hallazgos urgentes,
- priorizar observaciones,
- inferir recomendaciones de seguimiento,
- y marcar riesgos clínicos.

Aquí se resuelve la lógica clínica de forma determinista.

#### Capa 4: Renderizador determinista del informe

El informe se arma a partir de plantillas y estructuras de datos.

Ejemplo conceptual:

- sección de motivo de consulta,
- sección de refracción,
- sección de hallazgos clínicos,
- sección de observaciones relevantes,
- sección de recomendaciones,
- sección de alertas urgentes.

Esto evita que el modelo tenga que inventar la estructura completa del informe.

#### Capa 5: Capa de redacción con LLM (opcional y limitada)

El modelo solo se usa para:

- mejorar el estilo del texto,
- transformar datos estructurados en lenguaje natural,
- o generar una versión final más legible.

Pero no decide los hechos clínicos.

#### Capa 6: Validación y guardrails

Antes de devolver el resultado, el sistema debe verificar que:

- la salida cumple el esquema,
- no contiene afirmaciones no soportadas,
- no trivializa hallazgos urgentes,
- y no omite información crítica.

#### Capa 7: Auditoría y trazabilidad

Cada respuesta debería almacenar:

- hash del input,
- versión de reglas clínicas,
- versión del renderer,
- versión del modelo,
- y output final.

Esto permite auditar y revisar el comportamiento del sistema con mucha más facilidad.

---

## 6. Por qué esta arquitectura es mejor

### 6.1 Mejor para seguridad clínica

Porque separa claramente:

- lo que se observa,
- lo que se interpreta,
- y lo que se redacta.

### 6.2 Mejor para trazabilidad

Porque se puede justificar por qué se emitió una observación concreta.

### 6.3 Mejor para consistencia

Porque el informe ya no depende tanto del comportamiento probabilístico del modelo.

### 6.4 Mejor para mantenimiento

Porque la lógica clínica no está escondida dentro de prompts largos.

### 6.5 Mejor para escalabilidad

Porque se puede cambiar el modelo, los templates o las reglas sin reescribir toda la arquitectura.

---

## 7. Propuesta concreta de refactorización

### Fase 1: introducir una capa de hechos clínicos

Crear un modelo intermedio que represente el caso clínico como estructura formal:

- hallazgos detectados,
- severidad,
- categoría,
- prioridad,
- y evidencia.

### Fase 2: separar reglas clínicas del prompt

Mover la lógica de decisión fuera del prompt y convertirla en un motor independiente.

### Fase 3: reemplazar el párrafo libre por un informe estructurado

En lugar de devolver solo un párrafo, devolver algo como:

- resumen clínico,
- hallazgos principales,
- alertas urgentes,
- recomendaciones,
- y observaciones complementarias.

### Fase 4: limitar el uso del LLM

Usar el LLM solo para redacción final o para convertir la salida estructurada a lenguaje natural.

### Fase 5: agregar validación clínica y auditoría

Añadir reglas de validación que impidan:

- afirmar más de lo que el caso soporta,
- omitir alertas críticas,
- o generar lenguaje excesivamente interpretativo.

---

## 8. Conclusión final

La arquitectura actual es suficientemente válida como prototipo, pero no es la mejor arquitectura para una API clínica optométrica seria.

La propuesta más adecuada es una arquitectura modular en la que:

- la lógica clínica sea determinista y explícita,
- el modelo de IA sea un componente de redacción y estilo,
- la salida sea estructurada y validable,
- y la trazabilidad sea central.

En resumen:

- hoy la arquitectura está diseñada como un wrapper de prompt,
- lo ideal es diseñarla como un motor clínico controlado, auditable y estructurado.

---

## 9. Recomendación para versionado

Este análisis debería servir como base para una nueva versión del producto, por ejemplo:

- v2.0: arquitectura orientada a hechos clínicos estructurados.
- v2.1: separación de motor de reglas y renderer.
- v2.2: salida estructurada con validación clínica.
- v2.3: integración de revisión humana o banderas de riesgo.

La dirección correcta no es “hacer que el modelo responda mejor”, sino “diseñar un sistema que no dependa excesivamente del modelo para tomar decisiones clínicas”.
