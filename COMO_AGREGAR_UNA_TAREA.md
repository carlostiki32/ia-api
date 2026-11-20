# Cómo agregar una tarea

Copiar `app/tareas/definiciones/_plantilla.py`. Registrar el módulo y su instancia
`tarea` en `app/tareas/registro.py`, función `cargar_definiciones` (importación y
lista de módulos). No es necesario modificar `main.py`.

## Ejemplo completo

Esta tarea resume texto administrativo; el validador comprueba longitud y contenido.
Para datos clínicos, usar exclusivamente `DICCIONARIO_DATOS_RECETA.md`: no inventar
hallazgos, cronología ni diagnósticos. Un validador de forma no valida hechos clínicos.

```python
from pydantic import BaseModel, Field
from app.providers.ollama import build_options
from app.tareas.nucleo import FichaTarea, LlamadaLLM

SYSTEM = "Resume el texto recibido en una frase breve en español."
PROMPT_VERSION = "resumen-v1"

class Entrada(BaseModel):
    texto: str = Field(min_length=1, max_length=400)

class Salida(BaseModel):
    estado: str
    texto: str
    motivo: str | None = None

def validar(texto):
    texto = texto.strip()
    if not texto or len(texto) > 300:
        raise ValueError("Respuesta inválida")
    return texto

class Resumen:
    ficha = FichaTarea(
        nombre="resumen", version="1", descripcion="Resumen administrativo",
        rutas=("/v1/inferencia/resumen",), prioridad="fondo",
        modelo_request=Entrada, modelo_respuesta=Salida,
        timeout_s=30, modo_fallo="respaldo",
        respaldo="Texto administrativo fijo ante fallos",
        llamadas=(LlamadaLLM(
            "generar", PROMPT_VERSION, "texto",
            lambda req: {**build_options(), "num_predict":128},
            lambda:128, 2000),))

    async def ejecutar(self, req, ctx):
        from app.tareas.presupuesto import PresupuestoExcedido
        from app.gpu_scheduler import GPUOcupada
        try:
            texto, _ = await ctx.llamar("generar", SYSTEM, req.texto)
            return Salida(estado="generada", texto=validar(texto))
        except (PresupuestoExcedido, GPUOcupada, TimeoutError):
            raise  # El montaje asigna el motivo y llama al respaldo.
        except Exception:
            return self.respaldo(req, "respuesta_invalida")

    def respaldo(self, req, motivo):
        return Salida(estado="plantilla", texto="Consulte el texto original.", motivo=motivo)

tarea = Resumen()
```

Mantener SYSTEM estable; versionar cambios de prompts. Cada etapa declara sus
opciones reales; `opciones(None)` debe funcionar para el descubrimiento. CPU no
puede declarar llamadas. Usar `ctx.llamar` para presupuesto, prioridad y métricas.
La caché opcional usa tarea, versión, modelo, opciones y request como clave;
solo guarda resultados generados. Las métricas no almacenan contenido.

## Presupuesto y medición del peor caso

El límite efectivo es `int(0.95 * min(OLLAMA_NUM_CTX,
LIMITE_CONTEXTO_TOKENS, 8192))`: con 8192 son **7782 tokens**.
Cada etapa debe satisfacer `max_tokens_entrada + num_predict <= 7782`.
Reservar salida suficiente para la respuesta más larga válida y medir la entrada
completa con `app.tareas.presupuesto.contar(system, user, "estricto")`.
Incluye roles, separadores y prefijo assistant con thinking desactivado.

Generar requests con máximos de longitud, Unicode, cifras y todas las combinaciones
que cambien prompts; medir cada etapa, incluidas verificaciones y reintentos.
Ejecutar también con el tokenizador exacto verificado y contrastar
`prompt_eval_count` en un entorno Ollama. No medir solo el user prompt.
En el ejemplo, 400 caracteres Unicode ocupan como máximo 1600 bytes, más el
system y la envoltura; el techo de entrada 2000 deja margen y 128 de salida.
Si no cabe, reducir campos admitidos o dividir etapas con contrato explícito;
no recortar datos clínicos silenciosamente. Probar rechazo antes de enviar al proveedor.

Los modos son:
- **Exacto**: BPE reconstruido y seis sondas concordantes con Ollama.
- **Estricto**: bytes UTF-8 del prompt completo, respaldo de toda tarea nueva.
- **Conservador**: heurística exclusiva de receta, con warning; no garantiza cota BPE.

## Pruebas y despliegue

Probar esquemas, validador, respaldo, máximos, presupuesto, opciones fusionadas,
prioridad, métricas y rutas autenticadas. Consultar `/v1/tareas` y `/health` para
modo de conteo, pre-tokenizador detectado y tareas degradadas.

Desplegar Laravel aceptando y mostrando el motivo `presupuesto` **antes o junto**
con ia-api; versiones anteriores pueden sustituirlo por `respuesta_invalida`.
Consumir mediante `ejecutarTarea(nombre, payload, timeout)`. Validar compatibilidad
y tiempos de espera antes de habilitar la nueva tarea en producción.

## Tareas hijas y montaje manual

Una etapa opcional dentro de un flujo existente declara `padre="receta-clinica"`
y `montaje="manual"`. Ejemplo: `app/tareas/definiciones/explicacion_paciente.py`.
Comparte rutas descriptivas y prioridad interactiva con el padre; el registro
no monta otro endpoint. La integración invoca el servicio dentro del turno ya
adquirido: no volver a pedir turno dentro de la cadena. Si solo queda pendiente
la hija por un acierto parcial de caché, el handler pide un turno para ella.

Declarar cada `LlamadaLLM`, sus opciones efectivas, versión y techo de entrada.
`/v1/tareas` publica `padre`. Pasar `tarea`, `etapa`, `politica` y
`max_tokens_entrada` a `ollama.call`; el proveedor registra los intentos físicos.
No volver a sumar esas llamadas desde el servicio. Toda hija nueva usa política
estricta sin contador exacto. Publicar un punto de control antes de la hija y
recuperarlo ante errores o timeout exterior cuando el contrato exija conservar
la salida del padre. Versionar e independizar cachés y no guardar respaldos
transitorios. Probar cola, cancelación, aciertos parciales y errores por HTTP.

En la hija existente, `PACIENTE_LLM_HABILITADO=false` omite sus dos llamadas y
la recuperación de prosa paciente cacheada; devuelve respaldo CPU. No elimina
las llamadas declaradas en `/v1/tareas`: el descubrimiento conserva la ficha.
El motivo es nulo salvo fallo de ensamblado (`rechazada`/`error`).
