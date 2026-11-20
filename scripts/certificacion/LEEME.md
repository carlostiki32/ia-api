# Guía para el Dueño: Certificación en GPU de ia-api

Este kit mide y certifica en la PC con GPU las funciones de IA de la clínica:
1. Impresión clínica optométrica.
2. Explicación educativa para el paciente (receta dual).
3. Mensajes de seguimiento por WhatsApp.

---

## 1. Antes de empezar (preparación)

1. **Detener la ia-api de producción**:
   Si la API está corriendo como servicio o en otra terminal, deténgala antes de certificar para que no compita por la tarjeta de video (GPU).
   - En Linux: `sudo systemctl stop ia-api` (o detenga el proceso `uvicorn` activo).
   - En Windows: cierre la ventana de consola donde corre ia-api.
2. **Verificar que Ollama esté en ejecución**:
   Asegúrese de que Ollama esté iniciado con el modelo `qwen3.5:9b` instalado.
3. **No ejecutar programas pesados en la GPU**:
   Cierre juegos, navegadores con aceleración pesada u otras aplicaciones que consuman más del 10 % de la GPU.

---

## 2. Comando exacto para la certificación

Abra una terminal en la carpeta del proyecto `ia-api`, active el entorno virtual y ejecute el kit indicando una carpeta de salida **fuera del repositorio** que esté vacía:

### En Linux:
```bash
source .venv/bin/activate
python scripts/certificar_gpu.py --salida ~/certificacion-gpu-2026
```

### En Windows:
```powershell
.venv\Scripts\Activate.ps1
python scripts/certificar_gpu.py --salida C:\certificacion-gpu-2026
```

### ¿Cuánto tarda aproximadamente?
- Calcule entre **1½ y 2½ horas**, según la velocidad de la GPU. Cada receta completa (clínico + explicación + verificación) tarda del orden de 30 a 60 s en la RTX 3070 Ti.
- Incluye 100 recetas completas, 50 mensajes de WhatsApp, pruebas de caché, de concurrencia, de cancelación y de los interruptores. La estabilidad sostenida se mide sobre toda la corrida, que debe durar al menos 30 minutos.
- No use la PC para otra cosa mientras corre: el kit exige la GPU en reposo (< 10 %) antes de cada fase.
- Si la corrida se interrumpe, se repite completa en una carpeta vacía nueva.
- Durante la ejecución, el kit muestra el avance fase por fase en la pantalla.

---

## 3. Salidas generadas

Al finalizar la corrida, encontrará cuatro archivos en la carpeta de salida:
- `informe.json` e `informe.md`: mediciones técnicas automatizadas de cada criterio.
- `revision_paciente.csv`: 100 recetas generadas para revisión de calidad de redacción.
- `revision_whatsapp.csv`: 50 mensajes de WhatsApp para revisión de tono y pertinencia.

---

## 4. Cómo marcar las hojas de revisión (CSV)

Abra los archivos CSV en Microsoft Excel o LibreOffice Calc. Los archivos tienen codificación UTF-8 con BOM para que las tildes y caracteres en español se abran correctamente.

> [!IMPORTANT]
> - Escriba únicamente **sí** o **no** (o **si** / **no**).
> - **No deje casillas vacías**. Una sola casilla sin marcar impide que el sistema emita un veredicto APTO global.
> - Al guardar en Excel elija **«CSV UTF-8 (delimitado por comas)»** y no lo convierta a XLSX. Si por error lo guarda como «CSV (delimitado por comas)» o con punto y coma, `--cerrar` también lo lee.
- Marque las hojas **antes** de abrir `informe.md`, para que el resultado automático no influya en su revisión.
- La columna `observaciones` es libre y opcional.

### En `revision_paciente.csv` (100 filas):
- **`valida`**: ¿La explicación al paciente es clara, educativamente fiel a su graduación y comprensible? (Marque `sí` o `no`).
- **`critico_clinico`**: ¿Observa un error crítico, peligroso o contradictorio en la impresión clínica? (`no` si está bien, `sí` si hay error crítico).
- **`critico_explicacion`**: ¿Observa algún error crítico en la explicación al paciente (afirma un diagnóstico médico no respaldado, datos falsos, tuteo o agresividad)? (`no` si está bien, `sí` si hay error).
- **`critico_acciones`**: ¿Hay errores críticos en las acciones sugeridas? (`no` si está bien, `sí` si hay error).
- **`critico_plantilla`**: ¿Hay errores críticos en la plantilla educativa de respaldo? (`no` si está bien, `sí` si hay error).

### En `revision_whatsapp.csv` (50 filas):
- **`aceptable`**: ¿El mensaje es adecuado y respetuoso para enviarse a un paciente real por WhatsApp? (`sí` o `no`).
- **`critico`**: ¿El mensaje contiene afirmaciones médicas indebidas, cifras falsas, tuteo o nombres/teléfonos reales expuestos? (`no` si está bien, `sí` si hay error crítico).

---

## 5. Cómo cerrar la certificación

Una vez marcadas y guardadas ambas hojas CSV, ejecute el comando con `--cerrar`:

```bash
python scripts/certificar_gpu.py --cerrar C:\certificacion-gpu-2026
```

El kit leerá las hojas marcadas, calculará las tasas de aprobación y completará los criterios R6, R7 y W3.

---

## 6. Cómo leer el veredicto por perfil

El comando imprimirá en pantalla y actualizará en `informe.md` el veredicto final para los 4 perfiles de operación:

| Perfil | Descripción | Cuándo usarlo |
|---|---|---|
| **A** | Todo activo con IA (clínico, explicación paciente y WhatsApp). | Si todos los criterios pasan y la calidad del modelo es óptima. |
| **B** | Explicación al paciente desactivada (`PACIENTE_LLM_HABILITADO=false`). | Si el modelo en GPU redacta bien WhatsApp pero la explicación al paciente requiere ajustes editoriales. Usa plantilla CPU. |
| **C** | WhatsApp desactivado (`SEGUIMIENTO_LLM_HABILITADO=false`). | Si la receta dual opera perfectamente pero los mensajes de WhatsApp prefieren mantenerse 100 % en catálogo estático. |
| **D** | Solo clínico con IA (`PACIENTE_LLM_HABILITADO=false` y `SEGUIMIENTO_LLM_HABILITADO=false`). | Si solo se desea certificar la impresión clínica médica con IA, dejando explicaciones y WhatsApp en respaldo CPU. |

- Si un perfil dice **APTO**, esa configuración está **certificada para desplegarse en producción**. Para usar B, C o D, ponga las variables indicadas en el `.env` de ia-api y reiníciela; no hace falta desplegar código.
- Prefiera el perfil APTO con más funciones activas: A, luego B o C, y al final D.
- Si un perfil dice **NO APTO**, no debe desplegarse bajo esa modalidad.
- Si fallan los criterios base (P1–P3, R1–R3, X1, X2 o S1), **ningún perfil es APTO**.

---

## 7. Comprobación final en producción

Una vez concluida la certificación:
1. Vuelva a iniciar la `ia-api` de producción.
2. Ejecute la comprobación final de enrutado contra la URL pública configurada:
   ```bash
   python scripts/probar_enrutado.py --modo real --url URL_PUBLICA --api-key-env VARIABLE_CON_LA_CLAVE
   ```
   Debe concluir exitosamente sin fallos.
