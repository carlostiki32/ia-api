"""Punto de control, caché independiente y adaptador del proveedor del paciente."""
from dataclasses import dataclass, replace
import hashlib

from app.config import settings
from app.dual_contract import DualInferenceResult
from app.paciente import acciones, contexto, ensamblado, prompts, servicio, validador
from app.dual_contract import PATIENT_PROFILE_VERSION
from app.providers import ollama
from app.tareas.nucleo import CacheTareas
from app.correlaciones.registry import evaluar_correlaciones_con_nombres

paciente_cache = CacheTareas()


def plazos():
    return servicio.Plazos(
        redaccion=settings.paciente_timeout_redaccion_s,
        verificacion=settings.paciente_timeout_verificacion_s,
        paciente=settings.paciente_timeout_redaccion_s + settings.paciente_timeout_verificacion_s,
        global_peticion=settings.plazo_global_receta_s,
        minimo_redaccion=settings.paciente_minimo_redaccion_s,
        minimo_verificacion=settings.paciente_minimo_verificacion_s,
        ceder_interactiva=settings.paciente_omitir_si_espera)


def clave_paciente(caso):
    datos = dict(clinico=caso.contenido("clinico"), contexto=caso.como_dict(),
        perfil=PATIENT_PROFILE_VERSION, modelo=settings.ollama_model,
        opciones=[{**ollama.build_options(), **prompts.opciones(e)} for e in ("redaccion", "verificacion")],
        versiones=[servicio.VERSION, contexto.VERSION, prompts.PROMPT_VERSION,
            prompts.ESQUEMA_VERSION, prompts.GLOSARIO_VERSION, validador.VERSION,
            prompts.VERIFICADOR_VERSION, acciones.VERSION, ensamblado.VERSION])
    return hashlib.sha256(contexto.json_canonico(datos).encode("utf-8")).hexdigest()


@dataclass
class PuntoControlPaciente:
    clinico: str | None = None
    contexto: object = None
    publicar_clinico: object = None
    cache_clinico: bool = False
    cache_paciente: bool = False
    respaldo_base: object = None

    def publicar(self, req, texto):
        # Publicar el clínico antes de construir contexto o respaldo (CPU).
        self.clinico = texto
        if self.publicar_clinico and not self.cache_clinico:
            self.publicar_clinico(texto)
        pares = evaluar_correlaciones_con_nombres(req)
        self.contexto = contexto.contexto_desde_receta(req, texto,
            [dict(nombre=n, texto=t) for n, t in pares])
        self.respaldo_base = servicio.construir_respaldo(self.contexto)

    def resultado(self, paciente):
        return DualInferenceResult(impresion_clinica=self.clinico,
            explicacion_paciente=paciente.texto, explicacion_paciente_estado=paciente.estado,
            origen_explicacion=paciente.origen or "ninguno", paciente_version=servicio.VERSION,
            motivo_explicacion=paciente.motivo, acciones_sin_mapear=paciente.acciones_sin_mapear)

    def respaldo(self, motivo):
        base = self.respaldo_base or servicio.construir_respaldo(self.contexto, motivo)
        return self.resultado(replace(base, motivo="error" if base.motivo == "error" else motivo))

    def recuperado(self):
        if self.contexto is None or not settings.paciente_llm_habilitado:
            return None
        valor = paciente_cache.get(clave_paciente(self.contexto))
        self.cache_paciente = valor is not None
        return self.resultado(valor) if valor is not None else None


async def completar(punto, client, *, llegada, hay_interactiva_esperando=lambda: False):
    recuperado = punto.recuperado()
    if recuperado is not None:
        return recuperado
    if not settings.paciente_llm_habilitado:
        return punto.respaldo(None)
    async def llamar(l):
        import httpx
        try:
            return await ollama.call(l.system, l.user, client, options=l.opciones,
                format=l.formato, max_retries=l.max_retries, tarea=l.tarea, etapa=l.etapa,
                politica=l.politica, max_tokens_entrada=l.max_tokens_entrada)
        except httpx.TimeoutException as exc:
            raise TimeoutError from exc
    paciente = await servicio.generar(punto.contexto, llamar, llegada=llegada,
        plazos=plazos(), hay_interactiva_esperando=hay_interactiva_esperando)
    if paciente.estado == "generada":
        paciente_cache.put(clave_paciente(punto.contexto), paciente)
    return punto.resultado(paciente)
