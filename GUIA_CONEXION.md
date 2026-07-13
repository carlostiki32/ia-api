# Guía de conexión total — SaaS (Hetzner) ⇄ ia-api local vía Cloudflare Tunnel

> Cómo conectar **todo** el sistema de punta a punta: el autorrefractómetro ya
> inserta datos en el SaaS (`www.redcoretech.xyz`, VPS Hetzner `157.180.39.184`),
> y esta guía conecta el botón **"Generar con IA"** del SaaS con la **ia-api que
> corre en tu PC gamer en casa**, sin abrir puertos en tu router, sin exponer tu
> IP doméstica y con el tráfico cifrado de extremo a extremo.
>
> **Actualizada: julio 2026**, con la UI vigente de Cloudflare (los túneles ahora
> se administran desde el dashboard principal, `Networking > Tunnels`, desde el
> cambio de febrero 2026) y con el **estado real de tu dominio verificado por
> DNS** (ver §1).

---

## 0. Mapa general (a dónde vamos a llegar)

```
Autorrefractómetro ──POST──► Cloudflare (proxy, YA ACTIVO) ──► Hetzner VPS 157.180.39.184
                                                                 SaaS Laravel (YA FUNCIONA ✔)
                                                                        │
                                              Botón "Generar con IA" (FormEditor)
                                                                        │
                                                                        ▼
                                    POST https://ia.redcoretech.xyz/inferencia/impresion-clinica
                                         Authorization: Bearer <IA_API_KEY>
                                                                        │
                                                               ┌────────▼─────────┐
                                                               │    CLOUDFLARE    │ ← WAF (solo deja
                                                               │   (edge, TLS)    │   pasar la IP del
                                                               └────────┬─────────┘   VPS) + Tunnel
                                                                        │ túnel saliente cifrado
                                                                        ▼ (sin puertos abiertos)
                                                     TU PC GAMER EN CASA (Ubuntu, RTX 3070 Ti)
                                                     cloudflared (systemd) ──► ia-api (127.0.0.1:8888)
                                                                                   │
                                                                                   ▼
                                                                        Ollama → qwen3.5:9b (local)
                                                                                   │
                                                                                   ▼
                                    { "impresion_clinica": "El paciente..." } ──► de regreso al SaaS
                                    → textarea "Impresión clínica" → BD → PDF
```

**Por qué Cloudflare Tunnel y no abrir un puerto:** `cloudflared` abre una
conexión **saliente** desde tu casa hacia Cloudflare. No hay port-forwarding, no
importa que tu IP de casa sea dinámica o estés detrás de CGNAT, tu IP doméstica
nunca se publica, y el certificado TLS lo pone Cloudflare automáticamente.

---

## 1. Estado actual — verificado hoy (julio 2026)

Esto NO es teoría: se verificó con `dig` contra el DNS público y con tu panel de
Namecheap. El proceso que iniciaste antes **sí quedó a medias, pero avanzado**:

| Pieza | Estado verificado | Evidencia |
|---|---|---|
| Namecheap → nameservers delegados a Cloudflare | ✅ **HECHO** | `dig NS redcoretech.xyz` → `hasslo.ns.cloudflare.com` y `karsyn.ns.cloudflare.com` (coincide con tu panel: NAMESERVERS = Custom DNS) |
| Zona `redcoretech.xyz` en tu cuenta Cloudflare | ✅ **ACTIVA** | El SOA lo responde `hasslo.ns.cloudflare.com` — si la zona no estuviera activa en tu cuenta, tu SaaS no resolvería |
| `@` y `www` **proxied (nube naranja)** | ✅ **HECHO** | `dig A redcoretech.xyz` → `104.21.49.195` / `172.67.166.149` — esas son IPs del **edge de Cloudflare**, no tu VPS. Todo tu tráfico web (incluido el autorrefractómetro) **ya pasa por Cloudflare** |
| Subdominio `ia.redcoretech.xyz` (túnel) | ❌ **NO EXISTE** | `dig A ia.redcoretech.xyz` → vacío. **Esto es lo que falta** |
| Regla WAF para proteger `ia.` | ❌ Falta | (depende del túnel) |
| `.env` del VPS apuntando a `ia.redcoretech.xyz` | ❌ Falta | |
| cloudflared + ia-api como servicios en tu PC | ❌ Falta | |

**Conclusión:** Namecheap está terminado (no toques nada ahí) y el onboarding de
Cloudflare también. Lo que falta es: **el túnel (§4), el blindaje (§5) y los
`.env` de ambos lados (§6–§7)**. Las secciones 2 y 3 son solo verificación.

---

## 2. Namecheap — NO hay nada que hacer (solo verificar que se quede así)

Tu captura del panel ya muestra la configuración correcta. Botón por botón, para
confirmar:

1. Entra a [namecheap.com](https://www.namecheap.com) → inicia sesión → menú
   izquierdo **Domain List** → fila `redcoretech.xyz` → botón **MANAGE**.
2. Pestaña **Domain** (la que se abre por defecto). Verifica:
   - **STATUS & VALIDITY**: `ACTIVE`, con vigencia (la tuya: Feb 13, 2026 – Feb 13,
     2028) y **AUTO-RENEW activado** (palanca verde) — así el dominio no se te
     vence por accidente. ✔ ya lo tienes así.
   - **NAMESERVERS**: dropdown en **Custom DNS** con exactamente estas dos líneas:
     ```
     hasslo.ns.cloudflare.com
     karsyn.ns.cloudflare.com
     ```
     ✔ ya lo tienes así. **No agregues un tercer nameserver** con "ADD
     NAMESERVER", **no** lo regreses a "Namecheap BasicDNS", y no uses "Redirect
     Domain" (esa función te pide volver a los NS de Namecheap y rompería todo).
3. La pestaña **Advanced DNS** de Namecheap está **inactiva** desde que delegaste
   a Cloudflare: cualquier registro que edites ahí **no tiene efecto**. Todos los
   registros DNS viven ahora en Cloudflare. Namecheap solo te sirve para renovar
   el dominio y el WithheldforPrivacy (privacidad WHOIS, también ✔ activada).

Eso es todo en Namecheap. **Cero cambios.**

---

## 3. Cloudflare — verificar la zona (botón por botón)

Antes de crear el túnel, confirma en 3 minutos que lo que detectó el `dig`
coincide con tu cuenta:

### 3.1 Zona activa

1. Entra a [dash.cloudflare.com](https://dash.cloudflare.com) e inicia sesión
   (con la cuenta donde hiciste el proceso anterior — si no recuerdas cuál,
   es la que puede ver `redcoretech.xyz` en el Home).
2. En el **Account Home** verás la tarjeta/fila del dominio **redcoretech.xyz**
   con estado **Active** (✔ verde). Haz clic en el dominio para entrar a la zona.
   - Si dijera "Pending Nameserver Update", espera unos minutos o usa el botón
     **Check nameservers now** — pero por lo verificado con `dig`, ya está Active.

### 3.2 Registros DNS

1. Menú izquierdo → **DNS** → **Records**.
2. Debes ver, como mínimo:
   - Tipo `A` — Name `redcoretech.xyz` (o `@`) — Content `157.180.39.184` —
     Proxy status **Proxied** (nube naranja 🟠).
   - `A` o `CNAME` — Name `www` — apuntando a `157.180.39.184` (o a
     `redcoretech.xyz`) — **Proxied** 🟠.
3. **No cambies el proxy de esos registros**: ya están en naranja y tu SaaS y el
   autorrefractómetro funcionan así (verificado: resuelven a IPs de Cloudflare).
4. **No crees tú el registro `ia`** — lo crea solo el túnel en §4 (si creas uno
   manual tipo A, chocará con el CNAME del túnel).

### 3.3 Modo SSL/TLS (importante porque ya estás proxied)

Como tu tráfico ya pasa por Cloudflare, hay dos tramos cifrados: navegador→
Cloudflare (certificado de Cloudflare, automático) y Cloudflare→tu VPS. El modo
controla el segundo tramo:

1. Menú izquierdo → **SSL/TLS** → **Overview**.
2. Mira el modo actual (botón **Configure** para cambiarlo):
   - Si dice **Full (strict)** ✅ perfecto, no toques nada.
   - Si dice **Full** ⚠️ aceptable; súbelo a **Full (strict)** si tu VPS tiene un
     certificado Let's Encrypt vigente para `redcoretech.xyz`/`www` (lo tiene,
     porque tu SSL funcionaba antes de Cloudflare).
   - Si dice **Flexible** 🔴 cámbialo: en Flexible el tramo Cloudflare→VPS viaja
     **sin cifrar** por internet. Selecciona **Full (strict)** → Save.
3. Prueba inmediatamente `https://www.redcoretech.xyz` en el navegador. Si tras
   subir a Full (strict) vieras **Error 526** (certificado de origen inválido),
   significa que el cert del VPS expiró: renuévalo (`certbot renew`) o baja
   temporalmente a **Full** mientras lo arreglas.

> Nota sobre el túnel: `ia.redcoretech.xyz` **no depende** de este modo — el
> tráfico del túnel viaja dentro del canal cifrado de cloudflared, no usa el
> certificado del VPS.

---

## 4. Cloudflare — crear el túnel (UI de 2026, botón por botón)

> **Dónde viven los túneles ahora:** desde febrero 2026 se administran en el
> **dashboard principal**: zona o cuenta → **Networking > Tunnels**. (La ruta
> vieja del dashboard Zero Trust sigue existiendo como
> `Cloudflare One → Networks → Connectors`, pero ya no la necesitas para esto.)

### 4.1 Instalar cloudflared en tu PC gamer

En la misma PC donde corren Ollama e ia-api:

```bash
# Repo oficial de Cloudflare para Ubuntu/Debian:
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install -y cloudflared
cloudflared --version   # confirma la instalación
```

(El panel del túnel te mostrará estos mismos comandos + el token; puedes copiar
directo de ahí si prefieres.)

### 4.2 Crear el túnel en el dashboard

1. [dash.cloudflare.com](https://dash.cloudflare.com) → entra a la zona
   **redcoretech.xyz** → menú izquierdo **Networking** → **Tunnels**.
2. Botón **Create a tunnel** (si te pregunta el tipo, elige **Cloudflared** —
   el conector oficial).
3. **Name your tunnel**: escribe `ia-api-casa` → **Save tunnel** / **Continue**.
4. Pantalla **Install and run a connector**:
   - **Choose your environment**: sistema operativo **Debian**, arquitectura
     **64-bit**.
   - Te muestra un bloque de comandos que termina en:
     ```bash
     sudo cloudflared service install <TOKEN-MUY-LARGO>
     ```
   - Cópialo con el botón de copiar y **ejecútalo en tu PC gamer**. Eso registra
     cloudflared como **servicio systemd** (arranca solo al encender la PC).
5. Abajo en la misma pantalla, en **Connectors**, en unos segundos debe aparecer
   tu conector con estado **Connected** ✅. Pulsa **Next** / **Continue**.

### 4.3 Publicar la ia-api (Published application)

1. Dentro del túnel `ia-api-casa`, ve a la pestaña **Routes** (o el paso
   "Route tunnel" del asistente).
2. Botón **Add route** → tipo **Published application** (así se llama ahora lo
   que antes era "Public hostname").
3. Llena los campos exactamente así:
   - **Subdomain:** `ia`
   - **Domain:** `redcoretech.xyz` (dropdown)
   - **Path:** (vacío)
   - **Service → Type:** `HTTP`
   - **Service → URL:** `localhost:8888`
4. **Save** / **Add route**.

Cloudflare crea automáticamente el registro DNS `ia` (CNAME →
`<uuid>.cfargotunnel.com`, proxied 🟠) — por eso no debías crearlo a mano en §3.2.

### 4.4 Verificar

```bash
# En tu PC:
systemctl status cloudflared          # → active (running)
journalctl -u cloudflared -e          # sin errores de conexión

# Desde cualquier lado (aún sin WAF, debe responder):
dig A ia.redcoretech.xyz +short       # → ahora sí devuelve IPs de Cloudflare
curl -s https://ia.redcoretech.xyz/health
```

En el dashboard, **Networking > Tunnels** debe mostrar `ia-api-casa` con estado
**Healthy**. (Nota: para que `/health` responda, ia-api debe estar corriendo —
§7.)

---

## 5. Blindaje (que solo TU VPS pueda usar la ia-api)

Tres capas, todas baratas:

### 5.1 Regla WAF: solo la IP del VPS (botón por botón)

1. Dashboard → zona **redcoretech.xyz** → menú izquierdo **Security**.
2. Según la versión del panel que te toque:
   - **Panel nuevo:** entra a **Security rules** → botón **Create rule** →
     **Custom rules**.
   - **Panel clásico:** **Security → WAF → Custom rules** → **Create rule**.
3. Llena la regla:
   - **Rule name:** `solo-vps-a-ia-api`
   - En **When incoming requests match…** pulsa **Edit expression** (editor de
     texto) y pega:
     ```
     (http.host eq "ia.redcoretech.xyz" and ip.src ne 157.180.39.184)
     ```
     (Equivalente con el builder visual: Field `Hostname` · Operator `equals` ·
     Value `ia.redcoretech.xyz`, **And**, Field `IP Source Address` · Operator
     `does not equal` · Value `157.180.39.184`.)
   - **Then take action… → Choose action:** `Block`.
4. Botón **Deploy** (no "Save as Draft").

Resultado: cualquier request a `ia.redcoretech.xyz` que **no** venga de tu VPS
recibe **403 de Cloudflare** y jamás llega a tu casa. El resto del dominio
(`www`, `@`) no se ve afectado porque la regla filtra por `http.host`. Si algún
día cambias de VPS, edita la IP aquí.

### 5.2 API key fuerte (ya integrada en ia-api)

Genera un token real y úsalo **idéntico en ambos lados**:

```bash
openssl rand -hex 32
# ejemplo: 7f3a9c...64 caracteres...
```

- En la PC de casa → `ia-api/.env` → `API_KEY=<ese token>`
- En el VPS → `.env` del SaaS → `IA_API_KEY=<el mismo token>`

### 5.3 ia-api solo en localhost

Como cloudflared corre en la **misma** PC, la API no necesita escuchar en la red:

```bash
# ia-api/.env
HOST=127.0.0.1
```

Así ni siquiera en tu LAN de casa queda expuesto el puerto 8888. (Si quieres
probar con Postman desde otra máquina de tu casa, hazlo vía
`https://ia.redcoretech.xyz` — recuerda que la regla WAF te bloqueará: pruébalo
desde el VPS con curl, o agrega temporalmente tu IP a la regla.)

### 5.4 El límite de 100 segundos de Cloudflare (importante)

Cloudflare corta cualquier request proxied que tarde **más de ~100 s** (error
**524**). Tu inferencia tarda ~5 s, pero si la GPU está ocupada un request puede
esperar en cola hasta `QUEUE_WAIT_TIMEOUT` (default 120 s) y moriría en 524 en
lugar de un 503 limpio. Ajusta en `ia-api/.env`:

```bash
QUEUE_WAIT_TIMEOUT=60
```

Así el peor caso (60 s de cola + ~10–30 s de inferencia) queda debajo de 100 s y
el SaaS siempre recibe un error explicable.

---

## 6. VPS Hetzner — configurar el SaaS

SSH al VPS y edita el `.env` del proyecto Laravel:

```bash
IA_API_IMPRESION_CLINICA_ENDPOINT=https://ia.redcoretech.xyz/inferencia/impresion-clinica
IA_API_KEY=<el mismo token de openssl rand>
IA_API_ENABLED=true
IA_API_TIMEOUT=120
IA_API_LOG_ENABLED=true     # déjalo en true mientras estabilizas; luego false si quieres
```

Aplica la config (Laravel cachea la configuración):

```bash
php artisan config:clear && php artisan config:cache
```

> `IA_API_LOG_ENABLED=true` hace que `IaApiService` escriba en
> `storage/logs/laravel.log` cada intento: endpoint, payload, status, duración y
> cuerpo de la respuesta. Es tu mejor amigo durante la puesta en marcha.

---

## 7. PC de casa — configurar y dejar corriendo ia-api

### 7.1 `.env` final recomendado

```bash
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_TIMEOUT=120.0
OLLAMA_TEMPERATURE=0.2
OLLAMA_NUM_PREDICT=1024
OLLAMA_NUM_CTX=8192
OLLAMA_REPEAT_PENALTY=1.0
OLLAMA_TOP_P=0.8
OLLAMA_TOP_K=20
OLLAMA_MIN_P=0.0
OLLAMA_SEED=42
OLLAMA_MAX_RETRIES=2
MAX_CONCURRENT=1
QUEUE_WAIT_TIMEOUT=60          # ver §5.4 (límite de 100s de Cloudflare)
MAX_QUEUE_SIZE=5
HOST=127.0.0.1                 # solo localhost; cloudflared vive en esta misma PC
PORT=8888
API_KEY=<token de openssl rand -hex 32>
MAX_SENTENCES=10
CACHE_TTL_SECONDS=86400
CACHE_MAX_SIZE=500
HEALTH_CHECK_TIMEOUT=5.0
LOG_LEVEL=INFO                 # DEBUG imprime además el prompt completo
```

### 7.2 Arranque manual (como hasta ahora)

```bash
cd ~/Documentos/ia-api && ./start_linux.sh
```

### 7.3 Arranque automático con systemd (recomendado para "producción casera")

```bash
sudo tee /etc/systemd/system/ia-api.service >/dev/null <<'EOF'
[Unit]
Description=ia-api - Inferencia Clinica Optometrica
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=home
WorkingDirectory=/home/home/Documentos/ia-api
ExecStart=/home/home/Documentos/ia-api/start_linux.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ia-api
systemctl status ia-api
```

Con esto, tras un corte de luz o reinicio la PC levanta sola: Ollama →
ia-api → cloudflared, y el SaaS recupera la IA sin tocar nada.

---

## 8. Alineación de datos SaaS ⇄ ia-api (verificada contra el código)

No hay nada que corregir — el circuito completo ya está alineado:

1. **Botón "Generar con IA"** ([observaciones.blade.php](../optica/resources/views/livewire/recetas/form/observaciones.blade.php))
   llama al método Livewire `generateImpresionClinica()`.
2. **`FormEditor::generateImpresionClinica`** arma `$this->form->toPayload(true)`
   (serializa también los campos derivados: reflejos, motilidad, cover test) y lo
   pasa a `IaApiService`.
3. **`IaApiService::buildPayload`** construye el JSON con los nombres exactos que
   espera el schema de ia-api (`paciente.edad` calculada con Carbon,
   `refraccion.od/oi.*`, `akr.*` con las 13 claves de queratometría,
   `clinica.*`, `tipo_lente`). Verificado campo por campo contra
   [app/schemas.py](app/schemas.py). El `akr.taken_at` que envía el SaaS no está
   modelado en la API y se ignora sin error (Pydantic descarta extras).
4. **`IaApiService`** hace `POST` con `Authorization: Bearer IA_API_KEY`,
   `Accept: application/json` y timeout `IA_API_TIMEOUT` — exactamente el
   contrato de `verify_api_key` en ia-api.
5. **ia-api responde** `{"status": "ok", "impresion_clinica": "...", "correlaciones_activadas": [...]}`.
   El SaaS lee `impresion_clinica` (y en errores lee `detail`, que es el formato
   de error de FastAPI ✓).
6. **El resultado se imprime donde debe:** `FormEditor` lo asigna a
   `form.clinica['impresion_clinica_plan']` → aparece al instante en el textarea
   **"Impresión clínica"** (editable antes de guardar) → al guardar la receta se
   persiste en `receta_clinicas.impresion_clinica_plan` → se muestra en la vista
   de la receta (`show-page`) y en el **PDF del informe clínico**.

Único matiz de contrato: ia-api solo responde `422` cuando el payload no trae
**ningún** dato clínico (el propio SaaS ya lo pre-valida con `hasAnyValue` y ni
siquiera llama a la API en ese caso). Valores fuera de catálogo no tumban el
request: se descartan/normalizan por coerción tolerante.

---

## 9. Verificación end-to-end (en orden)

### 9.1 En la PC de casa

```bash
# 1) ia-api viva en localhost:
curl -s http://127.0.0.1:8888/health | python3 -m json.tool
#    → "status": "ok", "model_loaded": true

# 2) inferencia local directa:
curl -s -X POST http://127.0.0.1:8888/inferencia/impresion-clinica \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"receta_id":"smoke-1","paciente":{"edad":30},"refraccion":{"od":{"esfera":-2.0,"av_cc":"20/20"}}}'
#    → 200 con "impresion_clinica"

# 3) túnel conectado:
systemctl status cloudflared
```

### 9.2 Desde el VPS (Hetzner)

```bash
# 4) a través de Cloudflare + túnel (la ruta real que usará el SaaS):
curl -s https://ia.redcoretech.xyz/health | python3 -m json.tool
curl -s -X POST https://ia.redcoretech.xyz/inferencia/impresion-clinica \
  -H "Authorization: Bearer <IA_API_KEY>" -H "Content-Type: application/json" \
  -d '{"receta_id":"smoke-vps","refraccion":{"od":{"esfera":-2.0}}}'
```

### 9.3 Desde cualquier otra red (tu celular con datos móviles)

```bash
curl -i https://ia.redcoretech.xyz/health
# → 403 de Cloudflare (la regla WAF del §5.1 funcionando) ✔
```

### 9.4 La prueba final

En el SaaS: abre una receta con extensión clínica → llena datos → **"Generar con
IA"** → en unos segundos el textarea "Impresión clínica" se llena con el párrafo
→ edítalo si quieres → guarda → verifica que aparece en la vista de la receta y
en el PDF.

---

## 10. Debugging — dónde mirar cuando algo falle

El request se puede seguir **por request-id**: ia-api devuelve el header
`X-Request-ID` y todas sus líneas de log llevan ese id entre corchetes:
`grep <rid> logs/inference.log`.

| Síntoma (lo que ve el SaaS) | Causa probable | Dónde mirar |
|---|---|---|
| `403` HTML de Cloudflare | La regla WAF bloqueó el origen (¿cambió la IP del VPS?) | Cloudflare → Security → Events |
| `530` / error 1033 | El túnel está caído (PC apagada, cloudflared muerto) | `systemctl status cloudflared` · `journalctl -u cloudflared -e` |
| `502` de Cloudflare | cloudflared vivo pero ia-api caída en el puerto 8888, **o la published application quedó con Service `HTTPS` en vez de `HTTP`** (cloudflared intenta TLS contra uvicorn y falla) | `systemctl status ia-api` · `journalctl -u cloudflared` (busca la línea `Updated to new configuration` y revisa que diga `http://localhost:8888`, no `https://`) |
| `Could not resolve host: ia.redcoretech.xyz` **solo en tu PC** (desde otras redes sí resuelve) | Caché DNS **negativo** local: preguntaste por el subdominio antes de crear la ruta y tu router/ISP cacheó el "no existe" (expira solo, máx. ~30 min) | Verifica contra el autoritativo: `dig A ia.redcoretech.xyz @hasslo.ns.cloudflare.com +short` — si ahí responde, solo espera; mientras, prueba con `curl --resolve ia.redcoretech.xyz:443:104.21.49.195 https://ia.redcoretech.xyz/health` |
| `524` de Cloudflare | El request tardó >100 s (cola + inferencia) | Baja `QUEUE_WAIT_TIMEOUT` (§5.4); revisa `en_cola` en `/health` |
| `401 Token invalido` | `IA_API_KEY` (VPS) ≠ `API_KEY` (casa) | `logs/inference.log` muestra "Auth rechazada" con la longitud recibida |
| `413` | Prompt excede `num_ctx` (texto libre larguísimo) | Warning "Prompt excede contexto" en `logs/inference.log` |
| `422` | Payload sin ningún dato clínico | Warning "Payload sin datos clinicos"; en el VPS revisa el `clinical_input_snapshot` en `laravel.log` |
| `503` | Cola llena (5 esperando) | Warning "Cola saturada"; `/health` → `concurrencia.en_cola` |
| `504` | Ollama no respondió en `OLLAMA_TIMEOUT` | Error "Timeout de inferencia"; `ollama ps`, `nvidia-smi` |
| Texto raro/incompleto | Guardarraíles descartaron oraciones | Líneas "Guardarrail: ..." en `logs/inference.log`; con `LOG_LEVEL=DEBUG` se loggea el prompt completo |
| El SaaS dice "integracion deshabilitada" | `IA_API_ENABLED` no es true o falta config cache | `php artisan config:clear && php artisan config:cache` |
| `526` en el SaaS (no en `ia.`) | Modo Full (strict) con cert de origen vencido en el VPS | `certbot renew` en el VPS, o baja a Full (§3.3) |

**Los cuatro logs del sistema:**

| Log | Máquina | Qué tiene |
|---|---|---|
| `storage/logs/laravel.log` | VPS | Cada llamada del SaaS a la ia-api: payload, status, duración, respuesta (con `IA_API_LOG_ENABLED=true`) |
| Cloudflare → Security → Events / Networking → Tunnels | nube | Bloqueos WAF y salud del túnel |
| `journalctl -u cloudflared` | PC casa | Conexión del túnel, errores de origen |
| `ia-api/logs/inference.log` + `logs/errors.log` | PC casa | Todo el pipeline con request-id: payload recibido, correlaciones, métricas de Ollama (tokens, tok/s), guardarraíles, y errores con traceback (errors.log = solo WARNING+, el primer archivo a revisar) |

---

## 11. Logging de ia-api (qué se registra ahora)

- **`logs/inference.log`** (rotatorio, 10 MB × 5): todo el flujo a nivel `INFO` —
  entrada/salida de cada request con IP de origen real (`CF-Connecting-IP`),
  resumen del payload (qué campos vienen, sin contenido clínico), correlaciones
  activadas, métricas de Ollama (tokens de entrada/salida, tok/s, duración,
  `done_reason`), acciones de los guardarraíles y duración total.
- **`logs/errors.log`** (rotatorio): solo `WARNING`+ con traceback completo. Si
  algo falló, **empieza aquí**.
- **Request-id:** cada request recibe un id corto (o propaga el header
  `X-Request-ID` si el cliente lo envía); todas sus líneas lo llevan y se
  devuelve en la respuesta. `grep a395f5b3 logs/inference.log` reconstruye el
  request completo.
- **`LOG_LEVEL=DEBUG`** agrega: el system/user prompt completos renderizados
  antes de cada inferencia y el margen de contexto real reportado por Ollama.
- El texto clínico libre **no** se loggea a nivel INFO (solo nombres de campos);
  el contenido aparece únicamente en DEBUG y en los fragmentos que los
  guardarraíles descartan (máx. 80 caracteres).

---

## Checklist final

- [x] Namecheap: nameservers = `hasslo`/`karsyn`.ns.cloudflare.com (**ya estaba hecho** — solo no tocarlo)
- [x] Cloudflare: zona `redcoretech.xyz` **Active**, `@`/`www` proxied 🟠 (**ya estaba hecho**)
- [ ] Cloudflare: SSL/TLS en **Full (strict)** (verificar, §3.3)
- [ ] PC casa: cloudflared instalado + túnel `ia-api-casa` **Connected/Healthy** (§4)
- [ ] Túnel: published application `ia.redcoretech.xyz → HTTP localhost:8888` (§4.3)
- [ ] Cloudflare WAF: regla `solo-vps-a-ia-api` **Deploy** (§5.1)
- [ ] Token de `openssl rand -hex 32` idéntico en `API_KEY` (casa) y `IA_API_KEY` (VPS)
- [ ] `ia-api/.env`: `HOST=127.0.0.1`, `QUEUE_WAIT_TIMEOUT=60`
- [ ] VPS: endpoint `https://ia.redcoretech.xyz/...`, `IA_API_ENABLED=true`, `config:cache`
- [ ] `systemctl enable --now ia-api` (y ollama corriendo)
- [ ] §9 completo: curl local ✔, curl desde VPS ✔, 403 desde otra red ✔, botón "Generar con IA" ✔

**Referencias oficiales (julio 2026):**
[Create a tunnel (dashboard)](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/) ·
[Tunnels en el dashboard principal (changelog feb 2026)](https://developers.cloudflare.com/changelog/post/2026-02-20-tunnel-core-dashboard/) ·
[Set up Cloudflare Tunnel](https://developers.cloudflare.com/tunnel/setup/) ·
[WAF custom rules](https://developers.cloudflare.com/waf/custom-rules/create-dashboard/)
