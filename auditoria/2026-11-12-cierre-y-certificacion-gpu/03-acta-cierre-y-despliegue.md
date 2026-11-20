# Acta de cierre: las tres funciones de IA listas para desplegar (2026-11-12/13)

Las tres funciones son la **impresión clínica** (`receta-clinica`), la **explicación al paciente** (`explicacion-paciente`) y el **mensaje de WhatsApp** (`seguimiento-whatsapp`). Orquestó y auditó Claude. Implementaron Codex y Antigravity; Codex se quedó sin cupo a mitad del kit y del vocabulario, y Antigravity tomó el relevo. Sin commits: los hace el dueño.

## 1. Veredicto
**Certificadas sin GPU las tres funciones**, el kit de certificación en GPU y la compatibilidad entre versiones. Lo único que queda por certificar es lo que solo se puede medir con Qwen real en la PC con GPU: calidad, tiempos y cancelación. Para eso está el kit de un solo comando, con umbrales firmados antes de medir (`00-umbrales-firmados.md`), y su veredicto decide el despliegue (§4).

| Función | Certificado sin GPU | Se cierra en la PC con GPU |
|---|---|---|
| Impresión clínica | Correlaciones con el vocabulario nuevo (`02`), prompt idéntico salvo por las correlaciones, 413/504 con el código | R1–R3, X1, X4, X5, S1, más la revisión de los 100 clínicos (R7) |
| Explicación al paciente | Acta `2026-11-08/05`, más el interruptor y el respaldo verificados en el kit | R4–R7 y X2–X3 (calidad ≥ 90 % y 0 críticos) |
| WhatsApp | Acta `2026-11-07/02`, más el nuevo interruptor `SEGUIMIENTO_LLM_HABILITADO` | W1–W3, C1 y C2 |

## 2. Qué se hizo en este corte
1. **Umbrales de certificación en GPU firmados por los tres** en tres rondas (`00`). Codex no firmó R1, por 6 errores de hecho reales (por ejemplo, el límite publicado es 7782 y no 8192, y `/v1/metricas` no basta para medir por etapa), y sí firmó en R3.
2. **Kit `scripts/certificar_gpu.py`** (guía en `scripts/certificacion/LEEME.md`).
   - **Mediciones.** Corre una instancia propia de ia-api con caché vacía y un proxy que mide cada llamada a Ollama. Lee la telemetría de `nvidia-smi`.
   - **Fases.**
     - Frío y caliente.
     - 100 recetas y 50 WhatsApp sintéticos y realistas.
     - Caché y concurrencia.
     - Cinco cancelaciones y los interruptores apagados.
     - Estabilidad durante 30 minutos o más.
   - **Resultado.** Emite un veredicto por criterio y por perfil:
     - A: todo activo;
     - B: paciente con plantilla;
     - C: WhatsApp con catálogo;
     - D: solo clínico.

     Genera además dos hojas CSV que el dueño marca, y `--cerrar` cierra la revisión. El modo rápido, el simulado, una fase omitida o una casilla vacía **nunca** dan APTO.
3. **Interruptor `SEGUIMIENTO_LLM_HABILITADO`**. Con `false`, WhatsApp responde el mensaje del catálogo antes de consultar la caché y sin llamar a Ollama, con `motivo=ia_deshabilitada`. Laravel acepta ese motivo y lo muestra como «Integración de IA deshabilitada».
4. **`CACHE_MAX_SIZE=0`** ya no da 500: la falla venía de HEAD, al desalojar de una caché vacía, y ahora desactiva la caché. Un valor negativo se rechaza al arrancar.
5. **Vocabulario de síntomas** (`02`): formas verbales, inicio reciente de hasta 7 días y síntomas que refiere un acompañante. **0 detecciones perdidas en 107 044 casos** frente al código certificado.
6. **Compatibilidad entre versiones** (`01`): la ia-api nueva funciona con el Laravel viejo, y al revés.

## 3. Hallazgos de la auditoría de Claude en este corte (todos corregidos)
1. **Kit.**
   - Con WhatsApp apagado respondía `ollama_error`, cuando debía responder `ia_deshabilitada`.
   - `informe.md` volcaba JSON ilegibles.
   - `--cerrar` fallaba con hojas guardadas por Excel en ANSI o con punto y coma.
   - La guía estimaba 45–60 min, cuando son 1½–2½ h.
2. **Corpus del kit no realista.** Tenía motivos como «Revisión de graduación para lectura durante 1 minutos», présbitas con ADD 2.25 a los 11 años, edades de hasta 105 y relleno repetido en los casos máximos. Claude lo reescribió con escenarios clínicos verosímiles. Su propio corpus tenía un error (10 casos que la API rechazaba con 422) y la demostración del kit lo detectó; quedó corregido.
3. **VOCAB2.**
   - Una lista blanca en el script de medición.
   - Una regla global de negación que perdía 2 urgencias certificadas.
   - La diabetes de un familiar se atribuía al paciente.

   El detalle está en `02`.
4. **Compatibilidad.** Antigravity dejó dos `.tar` dentro de los repos; se retiraron.

## 4. Evidencia final
- **ia-api:** **24 953 passed**, 0 omitidas, con el tokenizador oficial de Qwen3.5 (`QWEN_TOKENIZER_JSON`).
- **Laravel:** **655 OK (3401 aserciones)** en la base exclusiva `optica_cierre_testing_20261112`. La huella de `laravel` y `laravel_testing` (`CHECKSUM TABLE`) es idéntica antes y después. JS: 37/37. Pint OK.
- **Finales de línea:** 0 incorrectos en los dos repos (ia-api en CRLF, optica en LF), sin `\r\r\n`; `git diff --check` limpio.
- **Demostración del kit contra el simulado,** con el corpus final:
  - todos los criterios automáticos dan APTO, también OFF_P y OFF_W;
  - S1 da NO APTO por diseño, porque el modo rápido dura menos de 30 min;
  - R6, R7 y W3 quedan PENDIENTE de la revisión humana;
  - el veredicto global es NO APTO por diseño en modo simulado.
- **Vocabulario:** comparación estricta, identidad del prompt y sondas ciegas (`02`).

## 5. Despliegue paso a paso
**Antes de empezar.**
- En el `.env` del VPS, confirmar que `IA_API_TIMEOUT` sea **≥ 90**. El Laravel viejo usa 15 por omisión (`01`).
- Hacer los commits de los dos repos.

**Fase 1: PC con GPU (ia-api; Ubuntu, con `ia-api` y `cloudflared` como servicios systemd, según `GUIA_CONEXION.md`).**
1. Actualizar el código, activar el venv (`source .venv/bin/activate`) y correr `pip install -r requirements.txt`.
2. En el `.env`, poner `OLLAMA_NUM_CTX=8192`. Los interruptores quedan en `true` por omisión y `PRESUPUESTO_RECETA_SIN_EXACTO` sigue en `conservador`.
3. Detener la ia-api de producción (`sudo systemctl stop ia-api`). Comprobar que Ollama corre con `qwen3.5:9b` y cerrar los programas que usen la GPU.
4. Correr el kit; tarda 1½–2½ h: `python scripts/certificar_gpu.py --salida ~/certificacion-gpu-AAAAMMDD`
5. Marcar `revision_paciente.csv` (100 filas) y `revision_whatsapp.csv` (50 filas) **antes** de abrir `informe.md`: en LibreOffice, o copiándolas a una PC con Excel y guardando como «CSV UTF-8». Después se devuelven a la misma carpeta.
6. Cerrar la certificación: `python scripts/certificar_gpu.py --cerrar ~/certificacion-gpu-AAAAMMDD`
7. Elegir el perfil APTO más completo, en el orden A, luego B o C, y al final D. Poner sus variables en el `.env`. **Si ningún perfil sale APTO, no se despliega la ia-api nueva**: se vuelve al commit anterior.
8. Arrancar la ia-api de producción (`sudo systemctl start ia-api`) y abrir `/health`. Debe decir `status: ok`, `modo_conteo: exacto` y `pre_tokenizador: qwen35` en las tres tareas.
9. Comprobación final: `python scripts/probar_enrutado.py --modo real --url URL_PUBLICA --api-key-env VARIABLE_CON_LA_CLAVE`. Debe salir sin fallos.

**Fase 2: VPS (Laravel).** Seguir `docs/deploy-vps-ubuntu.md`:
10. Actualizar el código y correr `php artisan migrate` (crea la tabla `paciente_mensajes_ia`) y `npm ci && npm run build`.
11. En el `.env`, poner `IA_API_TIMEOUT=90`. Después, `php artisan config:cache` y reiniciar los workers (`php artisan queue:restart`).
12. Prueba en la interfaz:
    - una receta con «Generar con IA»: clínico y explicación, con el mensaje del estado;
    - un mensaje de seguimiento por WhatsApp: el diálogo editable y luego «Aceptar».

**Vuelta atrás, sin desplegar.** Cambiar la variable en el `.env` de ia-api y reiniciarla:
- explicación al paciente: `PACIENTE_LLM_HABILITADO=false`;
- WhatsApp: `SEGUIMIENTO_LLM_HABILITADO=false`.

**Vuelta atrás completa.** Volver al commit anterior en la PC con GPU; el Laravel nuevo funciona con la ia-api vieja (`01`). La migración de Laravel solo agrega una tabla.

## 6. Decisiones y tareas del dueño
1. **Revisar** `auditoria/2026-11-08-explicacion-paciente/02-catalogo-y-prompts-para-revision.md`: las 104 frases de acciones, el glosario y los prompts. Conviene hacerlo antes o durante la corrida del kit.
2. **Marcar las dos hojas del kit.** Es la parte humana de la certificación (R6, R7 y W3).
3. **`PRESUPUESTO_RECETA_SIN_EXACTO`:** se recomienda dejar `conservador`. El kit exige el conteo exacto (P2), así que esta política solo actúa si el tokenizador fallara en un reinicio posterior.
4. **Vocabulario:** el límite de 7 días para el inicio reciente y la no atribución de diagnósticos sistémicos de familiares (`02`).
5. Pendientes que ya existían: `graphify update .` en optica (no está instalado en esta PC) y, opcionalmente, borrar las bases de prueba descartables:
   - `optica_*_20261107`;
   - `optica_audit_w2_testing_20261108`;
   - `optica_w2_testing_20261108`;
   - `optica_compat_20261112`;
   - `optica_cierre_testing_20261112`.
