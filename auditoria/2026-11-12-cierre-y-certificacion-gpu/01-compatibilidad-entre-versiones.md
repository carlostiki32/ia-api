# Compatibilidad entre versiones durante el despliegue (2026-11-12)

Ejecutó Antigravity (tarea COMPAT) y auditó Claude. Las versiones viejas son el `HEAD` de cada repo: ia-api `1c996b0` y optica `16f7192`, lo que hoy corre en producción. Las nuevas son el árbol de trabajo sin commit. Las ia-api corrieron contra el Ollama simulado con el tokenizador oficial y los servicios de Laravel (`IaApiService` y la personalización de WhatsApp) se llamaron con el código real de cada versión.

| Escenario | Caso | Resultado |
|---|---|---|
| S1: ia-api nueva con Laravel viejo | receta en modo `ok` | 200, `success`, `generada/llm`, clínico presente |
| S1 | tuteo | 200, `plantilla` con `motivo_explicacion=validacion`, clínico presente |
| S1 | verificación falsa | 200, `plantilla`, clínico presente |
| S1 | lento, con `IA_API_TIMEOUT=90` | 200 a los 15,2 s, `plantilla` con `motivo_explicacion=timeout`, clínico presente |
| S1 | lento, con el valor por omisión de Laravel viejo (15 s) | 504 en Laravel: el cliente corta antes que ia-api |
| S1 | urgencia | 200, `generada`, derivación urgente en el clínico |
| S2: Laravel nuevo con ia-api vieja | receta en modo `ok` | 200, `plantilla/plantilla` aceptada |
| S2 | WhatsApp (la ia-api vieja no tiene la ruta) | 404 → `motivo=ia_error`; el usuario ve el «Mensaje general» del catálogo, sin excepción ni 500 |
| S3: ambas nuevas | receta y WhatsApp | 200, `generada/llm` en ambas |

## Auditoría de Claude
- `CHECKSUM TABLE` de `laravel` (32 tablas) y `laravel_testing` (33): idénticos antes y después.
- Antigravity dejó dos archivos `.tar` en la raíz de los repos, pese a la prohibición. Claude los sacó y `optica` volvió exactamente al árbol de la foto previa. También se retiró el junction temporal a `vendor` sin tocar el original. Se usó la base exclusiva `optica_compat_20261112`, que es descartable.
- El 504 de S1 no es una regresión. El valor por omisión de Laravel viejo es de 15 s (`config/services.php`), pero ninguna receta real con GPU cabe en 15 s, así que producción debe tener `IA_API_TIMEOUT` definido; la guía de despliegue vieja indicaba 300. **Hay que confirmar en el `.env` del VPS que `IA_API_TIMEOUT` sea ≥ 90 antes de cambiar la ia-api.**

## Orden de despliegue recomendado
Los dos órdenes son seguros si se cumple lo anterior. Se recomienda **primero ia-api**, porque el kit de certificación tiene que correr en la PC con GPU antes de abrir la nueva ia-api al tráfico, y Laravel viejo funciona con ella (S1). Después va Laravel, con `IA_API_TIMEOUT=90`. Si se despliega primero Laravel, mientras dure la ventana WhatsApp muestra el mensaje general y la explicación sale con la plantilla (S2).
