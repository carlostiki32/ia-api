import asyncio
import pytest

from app.config import settings
from app.gpu_scheduler import GPUScheduler, GPUOcupada


def test_prioridad_fifo_y_estadisticas():
    async def run():
        gpu = GPUScheduler()
        orden = []
        async def worker(prioridad, nombre):
            async with gpu.turno(prioridad):
                orden.append(nombre)
                await asyncio.sleep(0)
        async with gpu.turno("fondo"):
            assert gpu.estadisticas == dict(ocupada=True, ocupante="fondo", en_espera_interactiva=0, en_espera_fondo=0)
            tareas = []
            for p, n in [("fondo", "f1"), ("fondo", "f2"), ("interactiva", "i1"), ("interactiva", "i2")]:
                tareas.append(asyncio.create_task(worker(p, n)))
                await asyncio.sleep(0)
            assert gpu.en_cola == 4
            assert gpu.estadisticas["en_espera_interactiva"] == 2
            assert gpu.estadisticas["en_espera_fondo"] == 2
            with pytest.raises(GPUOcupada):
                async with gpu.turno("fondo"):
                    pytest.fail("Admitió fondo con interactiva esperando")
        await asyncio.gather(*tareas)
        assert orden == ["i1", "i2", "f1", "f2"]
        assert gpu.estadisticas == dict(ocupada=False, ocupante=None, en_espera_interactiva=0, en_espera_fondo=0)
    asyncio.run(run())


def test_ocupante_interactiva_rechaza_fondo():
    async def run():
        gpu = GPUScheduler()
        async with gpu.turno("interactiva"):
            with pytest.raises(GPUOcupada):
                async with gpu.turno("fondo"):
                    pytest.fail("Admisión incorrecta")
            assert gpu.en_cola == 0
    asyncio.run(run())


@pytest.mark.parametrize("prioridad", ["fondo", "interactiva"])
def test_espera_agotada(monkeypatch, prioridad):
    monkeypatch.setattr(settings, "fondo_queue_wait_timeout", .01)
    monkeypatch.setattr(settings, "queue_wait_timeout", .01)
    async def run():
        gpu = GPUScheduler()
        async with gpu.turno("fondo"):
            with pytest.raises(GPUOcupada):
                async with gpu.turno(prioridad):
                    pytest.fail("No agotó la espera")
            assert gpu.en_cola == 0
            assert gpu.estadisticas["ocupada"]
        assert not gpu.estadisticas["ocupada"]
    asyncio.run(run())


def test_limite_total_de_cola(monkeypatch):
    monkeypatch.setattr(settings, "max_queue_size", 2)
    async def run():
        gpu = GPUScheduler()
        async def worker(p):
            async with gpu.turno(p):
                pass
        async with gpu.turno("fondo"):
            tareas = [asyncio.create_task(worker("fondo"))]
            await asyncio.sleep(0)
            tareas.append(asyncio.create_task(worker("interactiva")))
            await asyncio.sleep(0)
            with pytest.raises(GPUOcupada):
                async with gpu.turno("interactiva"):
                    pytest.fail("Excedió el límite")
            assert gpu.en_cola == 2
        await asyncio.gather(*tareas)
    asyncio.run(run())


@pytest.mark.parametrize("prioridad", ["interactiva", "fondo"])
def test_cancelacion_de_espera_y_ocupante(prioridad):
    async def run():
        gpu = GPUScheduler()
        inicio = asyncio.Event()
        async def worker(p):
            async with gpu.turno(p):
                inicio.set()
                await asyncio.Event().wait()
        ocupante = asyncio.create_task(worker("fondo"))
        await inicio.wait()
        espera = asyncio.create_task(worker(prioridad))
        await asyncio.sleep(0)
        assert gpu.en_cola == 1
        espera.cancel()
        with pytest.raises(asyncio.CancelledError):
            await espera
        assert gpu.en_cola == 0
        ocupante.cancel()
        with pytest.raises(asyncio.CancelledError):
            await ocupante
        assert not gpu.estadisticas["ocupada"]
        async with gpu.turno("interactiva"):
            assert gpu.estadisticas["ocupante"] == "interactiva"
    asyncio.run(run())


def test_cancelacion_justo_despues_de_despacho():
    async def run():
        gpu = GPUScheduler()
        async def worker():
            async with gpu.turno("interactiva"):
                await asyncio.Event().wait()
        async with gpu.turno("fondo"):
            tarea = asyncio.create_task(worker())
            await asyncio.sleep(0)
        # El turno ya está asignado pero el waiter aún no ha continuado.
        tarea.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarea
        assert not gpu.estadisticas["ocupada"] and gpu.en_cola == 0
    asyncio.run(run())
