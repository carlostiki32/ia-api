# Re-certificación de C1–C6 (texto simple para el paciente) — 2026-11-07

Pendiente 2 de `RETOMAR_TRABAJO_2026-11-06.md`. Certificadores independientes y cruzados (cada uno revisó lo que **no** implementó en F0):
- **ia-api (C2–C6): Antigravity** (F0 de ia-api lo hizo Codex).
- **Laravel (C1, C2, C6): Codex** (F0 de Laravel lo hizo Antigravity).
- **Claude** re-ejecutó los scripts y la prueba temporal y revisó la evidencia.

## Veredicto
| Condición | Resultado | Evidencia |
|---|---|---|
| C1 bloque «Cómo leer su receta» | **CERTIFICADO tras F0-FIX** | Render Blade real de 7 casos (−1/−8, cilindro positivo, plano con ADD, miope/hipermétrope, −0.25/−12, ojo nulo, −1/−1); cada cifra del bloque coincide con su celda (signo y decimales). Primera pasada: NO CERTIFICADO por redacción → corrección F0-FIX (ver abajo). |
| C2 explicación 100 % CPU | CERTIFICADO | Prompt dual = prompt clínico (sin «PERFIL EDUCATIVO»); `explicacion_paciente` sale de `build_patient_template` aunque el modelo devuelva basura; HTTP 200 `plantilla`/`plantilla`; Laravel presenta `plantilla` como éxito sin «respaldo». |
| C3 trato de usted | CERTIFICADO | 208 perfiles (196 + 12 extremos): 0 tuteos; las coincidencias de grep son sustantivos («parte») o instrucciones internas al modelo. |
| C4 ojo plano | CERTIFICADO | Frase acordada en el 100 % de los planos; 0 «sano/normal/no necesita/no requiere/bien»; apertura sin repetir. |
| C5 `OLLAMA_NUM_CTX ≥ 8192` | CERTIFICADO EN CÓDIGO / NO VERIFICABLE AQUÍ | Valor por omisión y `.env.example` = 8192; golden Rx+AKR+clínica = 3566 tokens frente a 7782 (95 %). **Falta la evidencia del `.env` real de la PC con GPU.** |
| C6 título y documento histórico | CERTIFICADO | «Explicación para el paciente» en los 7 HTML; `PROPUESTA_RESUMEN_PACIENTE.md` marcado como histórico. |

## Corrección F0-FIX (Laravel, Codex, 2026-11-07)
Archivos: `lang/es/receta_lectura.php`, `app/Support/Recetas/LecturaRecetaPaciente.php`, `tests/Unit/Support/LecturaRecetaPacienteTest.php`, `tests/Feature/RecetaLecturaPdfTest.php`.
1. **Ojo plano con ADD** con la frase acordada (§3b de la certificación) y la cifra en el mismo formato que el resto del bloque: «Ojo izquierdo: su receta de lejos marca 0.00; ese lado solo lleva el apoyo para ver de cerca. Apoyo para cerca (ADD) +2.00 D.»
2. **Cilindro nulo ≠ cero** (defecto hallado por Claude): con esfera y CIL vacío la línea decía «sin cilindro»; ahora no menciona el cilindro. «sin cilindro» solo con CIL explícitamente 0.00.
3. **Leyendas:** ESF explica cada signo («−: lente que corrige la visión de lejos, como en la miopía; +: lente que ayuda a enfocar, como en la hipermetropía»); CIL ya no iguala «vacío» con 0.00.
4. Pruebas nuevas para los tres puntos; el tope de palabras de la leyenda pasó de 90 a 120 (lo exige la leyenda ESF más completa; el tope no venía del criterio de certificación).

Evidencia: prueba temporal de R2 sin modificar (SHA-256 `bd8e5505…3c11`) **3/3 OK** (82 aserciones), repetida por Claude; pruebas enfocadas 69 OK; suite completa de Laravel **588 OK** (antes 586).

## Limitaciones
- No se certifica la rasterización ni la paginación de DomPDF (se certificó el HTML que DomPDF recibe).
- La comparación entre ojos sigue siendo neutral («misma graduación» / «graduación distinta»); no dice cuál lleva más potencia, porque con signos o cilindros distintos esa comparación puede inducir a error. La propuesta (§A, C1) pide comparación neutral.
- C5 depende de la PC con GPU.
