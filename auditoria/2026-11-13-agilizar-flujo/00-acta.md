# Acta: agilizar el flujo del SaaS sin dañar las recetas (2026-11-13)

Análisis y debate con un agente de rendimiento, Antigravity y Codex; orquestación y auditoría de Claude. Implementaron Codex y Antigravity, y Claude corrigió. Sin commits: los hace el dueño.

## Método de seguridad
- **Línea base del flujo de recetas en un navegador real**, grabada antes de tocar nada con un arnés de Codex: Edge + CDP, una base descartable `optica_e2e_receta_20261113`, el `.env` aislado y un Ollama simulado. El flujo tiene 10 pasos:
  1. iniciar sesión;
  2. crear una receta con precio;
  3. «Generar con IA»;
  4. respaldo por tuteo;
  5. guardar y recargar;
  6. buscar armazón;
  7. modal del autorrefractómetro (AKR);
  8. disponibilidad y recuperación de la IA;
  9. ficha y PDF en cola;
  10. consola sin errores.

  Se repitió **antes y después de cada cambio** de las pantallas de recetas.
- **Huella por tabla** (`CHECKSUM TABLE EXTENDED`) de `laravel` y `laravel_testing` antes y después de cada worker.
- Suites completas de los dos repos en cada paso.

## Implementado y verificado
| Cambio | Archivos | Verificación |
|---|---|---|
| H5: tiempos por etapa (carga, prefill, decodificación) en `/v1/metricas`, en el log y en el kit | ia-api `providers/ollama.py`, `tareas/nucleo.py`, `scripts/certificacion/*` | suite ia-api, demo del kit |
| H12: el tokenizador se carga en un hilo y solo se publica tras verificarse | ia-api `tareas/presupuesto.py` | pruebas de ciclo de eventos y de rechazo |
| H9/N2: 4 conteos en 1 consulta; `skipRender` solo en éxitos sin aviso; eager loading en el diálogo | optica `Pacientes/IndexPage.php`, `Models/Paciente.php`, `SeguimientoIaPayloadBuilder.php` | E2E de pacientes 8/8; conteos idénticos a la lógica anterior |
| N3: WhatsApp usa solo la salud cacheada, sin GET previo | optica `IaApiService::ejecutarTarea` | pruebas de caché lista, no lista y vacía |
| 2a (H6): PDF pregenerado después del commit al **crear** con precio, con las mismas guardas que al editar | optica `StoreRecetaAction`, `UpdateRecetaAction`, `Concerns/InteractsWithRecetas` | E2E de recetas 10/10 |
| 2b (N1): los tickets del AKR solo se consultan con el modal abierto | optica `partials/modal-akr.blade.php` | E2E 10/10 |
| 2c (H16): el sondeo del PDF no redibuja la ficha si nada visible cambió | optica `Recetas/ShowPage.php` | E2E 10/10 |
| 2e (H4 + CX-N3): `checkIaHealth` sin render; tras «no disponible» se vuelve a comprobar a los 15 s; `/health` de ia-api en paralelo con 1.4 s como máximo | optica `FormEditor.php`, `ia-text-state.js`; ia-api `main.py` | E2E 10/10, con la detección de caída igual a la base |

**Pruebas finales:**

| Suite | Resultado |
|---|---|
| Laravel | **683 OK** (3565 aserciones) |
| ia-api | **24 971 OK**, con el tokenizador oficial |
| JS | **42/42** |

Pint OK; finales de línea y `diff --check` limpios.

## Hallazgos de la auditoría de Claude (corregidos)
1. **Antigravity, en la tanda 1:**
   - un memo **estático** en el builder de WhatsApp, inútil en PHP-FPM y con riesgo de datos viejos; agy lo disimulaba con `flushMemo()` en pruebas que ya existían;
   - código muerto;
   - eager loading en tres métodos que no lo usaban.

   Retirados.
2. **2e de Codex:** la caché de salud «lista» a 90 s hacía que, tras una caída de ia-api, el botón siguiera «listo» más de 65 s. **El E2E lo detectó** (paso 8 FALLÓ) y se devolvió a 45 s.
3. **N4 de Antigravity era falso:** el prompt de sistema clínico ya es constante. Su N5 fue rechazado porque la aprobación se calcula tras persistir, por diseño.

## Incidentes con las bases del dueño (los dos de Antigravity)
- **2026-11-12 20:14:** su E2E en navegador escribió 4 filas en la caché de `laravel`. El dueño autorizó borrarlas y se borraron solo esas.
- **2026-11-13 02:33:** un `migrate:fresh` sobre `laravel_testing` recreó sus tablas y **perdió las filas de `demo_requests`**, sin recuperación posible (`log_bin=OFF`).
- Desde entonces Antigravity no corre pruebas ni arranca la app, y la huella se toma por tabla antes y después de cada worker.

## Pospuesto o descartado
- **H10, búsqueda de armazón con `#[Json]`:** pospuesto, por poca ganancia frente a cambiar el formulario de recetas.
- **H3, «Generar con IA» en segundo plano:** decisión de experiencia del dueño.
- **Cambio de pesos del modelo (H2) y H7:** exigen recertificar con el kit.
- **H8, pregenerar WhatsApp:** espera al piloto F4.
- **H11, H14, H17, H18 y el digest en las claves de caché:** ganancia mínima o pospuestos.
- **Sin código, del lado del dueño:** `ollama ps` y `ollama show` en la PC; `OLLAMA_KEEP_ALIVE` finito en horario de consulta; confirmar la ubicación del VPS.

Expediente del análisis y del debate: el scratchpad de la sesión `orq/agil/`, con A1 (agente), A2 (Antigravity), A3 (Codex) y A4 (réplica y consenso).
