Revisión de ambos repositorios, sin modificar archivos. Reproduje la matriz: **144 perfiles, 143 plantillas válidas, 62–85 palabras**.

| Decisión | Voto |
|---|---|
| A — C1–C6 | **BLOQUEO:** C1 confunde esfera cero con ausencia de corrección. Redacción aceptable: «ESF 0.00 indica ausencia del componente esférico. Solo ESF y CIL explícitamente iguales a 0.00 permiten explicar que esa receta no lleva corrección de lejos; ADD se describe aparte». Aplicar también a C4. Certificar exige C1–C6, no solo C1–C5. |
| D-1 | **ACEPTO con ajuste menor:** conservar explícitamente el contrato del endpoint anterior durante la extracción del texto educativo. |
| D-2 | **ACEPTO con ajuste menor:** readmitir por prioridad cada llamada, incluidos verificación y reintentos; no reservar el turno para toda la cadena. La cota debe incluir prefill, carga y generación. |
| D-3 | **ACEPTO con ajuste menor:** retirar también los logs DEBUG actuales que contienen el prompt clínico. |
| D-4 | **ACEPTO con ajuste menor:** el LLM es opcional para textos deterministas; los meses también los calcula e inserta código. |
| D-5 | **ACEPTO con ajuste menor:** documentar `timeout HTTP < timeout del job < retry_after`, con margen operativo. |
| D-6 | **ACEPTO**. |
| D-7 | **ACEPTO**. |
| D-8 | **ACEPTO con ajuste menor:** revalidar también antes de abrir WhatsApp; incluir versiones y cambios relevantes del expediente en la invalidación. |
| D-9 | **ACEPTO con ajuste menor:** registrar aprobación humana, actor y versión exacta del texto aprobado; editarlo invalida esa aprobación. |
| D-10 | **ACEPTO con ajuste menor:** aclarar si viajan ESF/CIL/ADD o categorías derivadas. El perfil actual recibe una request clínica; necesita adaptación para el contrato mínimo. Edad desconocida excluye personalización. |
| D-11 | **ACEPTO**. |
| D-12 | **ACEPTO**. |
| D-13 | **BLOQUEO:** un substring literal puede quedar negado o descontextualizado. Redacción aceptable: «Qwen propone saludo, invitación e ids elegibles. El servidor inserta las frases clínicas como oraciones independientes en posiciones fijas. La prosa libre no puede modificar ni interpretar esas frases. Ningún mensaje personalizado habilita WhatsApp sin aprobación humana explícita del texto completo». |
| D-14 | **ACEPTO con ajuste menor:** comprobar correspondencia bidireccional entre ids y frases; rechazar hechos adicionales, repeticiones y alteraciones. La lista de palabras prohibidas es una defensa adicional, sin garantía semántica. |
| D-15 | **ACEPTO con ajuste menor:** timeout, JSON inválido o respuesta indeterminada también producen respaldo; esta pasada vuelve a solicitar turno. |
| D-16 | **ACEPTO**. |
| D-17 | **ACEPTO con ajuste menor:** conservar evidencia del consentimiento expreso por escrito y su autenticación, además de fecha/medio/versión, salvo excepción legal documentada. Véase [LFPDPPP, artículo 8](https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPDPPP.pdf). |
| D-18 | **ACEPTO con ajuste menor:** el genérico sigue sujeto a D-17 y a verificar el destinatario autorizado. |
| D-19 | **ACEPTO**. |
| D-20 | **ACEPTO**. |
| F0 | **ACEPTO con ajuste menor:** incorporar la corrección de A y cerrar las seis condiciones. |
| F1 | **ACEPTO**. |
| F2 | **ACEPTO con ajuste menor:** añadir pruebas adversariales de negación/contexto y de prioridad entre llamadas consecutivas. |
| F3 | **ACEPTO con ajuste menor:** probar aprobación, edición posterior y bloqueo de apertura sin aprobación vigente. |
| F4 | **ACEPTO con ajuste menor:** fijar umbrales de latencia, espera y rechazo antes del piloto. |
| F5 | **ACEPTO**. |

**Errores de hecho o incompatibilidades restantes:**

- **C1:** ESF 0.00 con CIL −1.00 sí contiene corrección refractiva. Está contemplado en [tests/test_patient_profile.py:23](</C:/Users/Uriel Rojo/Documents/ia-api/tests/test_patient_profile.py:23>) y en la clasificación de [app/patient_profile.py:63](</C:/Users/Uriel Rojo/Documents/ia-api/app/patient_profile.py:63>).
- **D-10:** `build_patient_profile` actualmente exige `ImpresionClinicaRequest` y consulta ESF/CIL de ambos ojos; no consume directamente categorías mínimas: [app/patient_profile.py:55](</C:/Users/Uriel Rojo/Documents/ia-api/app/patient_profile.py:55>).
- La restricción futura de logs requiere cambios reales: hoy se registra el prompt completo en DEBUG: [app/inference.py:836](</C:/Users/Uriel Rojo/Documents/ia-api/app/inference.py:836>).

CONSENSO: NO (2 bloqueos)