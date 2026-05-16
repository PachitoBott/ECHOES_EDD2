# Plan de Testing — Networking Multijugador

## ¿Cómo sé que funciona?

Busca estos **patrones en los logs** que confirman cada etapa.

---

## Test 1: Servidor solo (baseline)

### Ejecutar

```bash
cd CODIGO
python Main.py --server --port 5555 --skip-menu
```

### Qué esperar (en ~3-5 segundos)

**✅ ÉXITO si ves:**
```
[2024-XX-XX HH:MM:SS] INFO: Servidor escuchando en 0.0.0.0:5555
[2024-XX-XX HH:MM:SS] INFO: Modo debug activo — F1 abre la consola de debug
```

O sin debug:
```
[2024-XX-XX HH:MM:SS] INFO: Servidor escuchando en 0.0.0.0:5555
```

Luego el juego abre (pantalla negra con el dungeon cargándose).

**❌ FALLO si:**
- No aparece "Servidor escuchando"
- Error "Address already in use" → puerto ocupado (prueba `--port 5556`)
- Crash con excepción

### Qué está pasando

- ✅ CLI parser funciona
- ✅ Game.__init__() acepta flags
- ✅ NetworkManager se inicializa
- ✅ Servidor TCP escucha en puerto 5555

---

## Test 2: Cliente se conecta (handshake)

### Ejecutar en 2 terminales

**Terminal 1** (servidor, déjalo corriendo):
```bash
cd CODIGO
python Main.py --server --port 5555 --skip-menu
```

**Terminal 2** (cliente):
```bash
cd CODIGO
python Main.py --client --host 127.0.0.1 --port 5555 --role victim --skip-menu
```

### Qué esperar

**En Terminal 1 (servidor):**
```
[2024-XX-XX HH:MM:SS] INFO: Servidor escuchando en 0.0.0.0:5555
[2024-XX-XX HH:MM:SS] INFO: Nueva conexion desde ('127.0.0.1', XXXXX)
[2024-XX-XX HH:MM:SS] INFO: Jugador conectado: rol=victima addr=('127.0.0.1', XXXXX)
```

**En Terminal 2 (cliente):**
```
[2024-XX-XX HH:MM:SS] INFO: Conectado como victima | seed=XXXXX | servidor=127.0.0.1:5555
```

Ambas terminales abrirán el juego (ventana Pygame).

### Qué está pasando

- ✅ Cliente resuelve DNS (127.0.0.1)
- ✅ Socket TCP se conecta
- ✅ Handshake exitoso (cliente envía CONECTAR, servidor responde ACEPTADO)
- ✅ Ambos tienen la misma seed del dungeon

**Si falla:**
- "Connection refused" → servidor no corre en terminal 1
- "No such host" → `--host` es incorrecto
- "Timeout" → firewall bloqueando puerto 5555

---

## Test 3: Ambos clientes conectan (2 roles)

### Ejecutar en 3 terminales

**Terminal 1** (servidor):
```bash
cd CODIGO
python Main.py --server --port 5555 --skip-menu
```

**Terminal 2** (cliente VICTIMA):
```bash
cd CODIGO
python Main.py --client --host 127.0.0.1 --port 5555 --role victim --skip-menu
```

**Terminal 3** (cliente ALIADO):
```bash
cd CODIGO
python Main.py --client --host 127.0.0.1 --port 5555 --role ally --skip-menu
```

### Qué esperar

**En Terminal 1 (servidor):**
```
[2024-XX-XX HH:MM:SS] INFO: Servidor escuchando en 0.0.0.0:5555
[2024-XX-XX HH:MM:SS] INFO: Nueva conexion desde ('127.0.0.1', XXXXX)
[2024-XX-XX HH:MM:SS] INFO: Jugador conectado: rol=victima addr=('127.0.0.1', XXXXX)
[2024-XX-XX HH:MM:SS] INFO: Nueva conexion desde ('127.0.0.1', XXXXX)  ← 2º cliente
[2024-XX-XX HH:MM:SS] INFO: Jugador conectado: rol=aliado addr=('127.0.0.1', XXXXX)
```

**En Terminal 2 (VICTIMA):**
```
[2024-XX-XX HH:MM:SS] INFO: Conectado como victima | seed=XXXXX | servidor=127.0.0.1:5555
[2024-XX-XX HH:MM:SS] INFO: [NET] Evento: jugador_unido desde servidor
[2024-XX-XX HH:MM:SS] INFO: Jugador aliado se unió a la sesión
```

**En Terminal 3 (ALIADO):**
```
[2024-XX-XX HH:MM:SS] INFO: Conectado como aliado | seed=XXXXX | servidor=127.0.0.1:5555
[2024-XX-XX HH:MM:SS] INFO: [NET] Evento: jugador_unido desde servidor
[2024-XX-XX HH:MM:SS] INFO: Jugador victima se unió a la sesión
```

### Qué está pasando

- ✅ Servidor acepta múltiples conexiones (threading)
- ✅ Ambos clientes reciben el mismo seed
- ✅ Evento "jugador_unido" se propaga a clientes
- ✅ Cada cliente sabe quién se conectó

**Esto es lo MÁS IMPORTANTE:** Si ves "jugador_unido" en ambas terminales, **el networking FUNCIONA**.

---

## Test 4: Juega y cierra (graceful shutdown)

Con las 3 terminales corriendo:

1. En **Terminal 2**, presiona ESC → menú pausa
2. Haz clic en "Salir del juego"
3. O presiona Ctrl+C

### Qué esperar

**En Terminal 2:**
```
[2024-XX-XX HH:MM:SS] INFO: Cliente desconectado (shutdown)
```

**En Terminal 1 (servidor):**
```
[2024-XX-XX HH:MM:SS] INFO: Conexion cerrada: victima (...)
```

**Importante:** No debe haber crashes, solo cierre limpio.

### Qué está pasando

- ✅ Cliente envía DESCONECTAR
- ✅ Servidor registra desconexión
- ✅ Sin datos corruptos o connections colgadas

---

## Test 5: Rol ya ocupado (error handling)

**Terminal 1** (servidor):
```bash
python Main.py --server --port 5555 --skip-menu
```

**Terminal 2** (VICTIMA):
```bash
python Main.py --client --host 127.0.0.1 --port 5555 --role victim --skip-menu
```

**Terminal 3** (intentar VICTIMA de nuevo):
```bash
python Main.py --client --host 127.0.0.1 --port 5555 --role victim --skip-menu
```

### Qué esperar

**En Terminal 3:**
```
[2024-XX-XX HH:MM:SS] ERROR: Conexion rechazada: El rol 'victima' ya está ocupado
```

El juego NO abre, cierra limpiamente.

### Qué está pasando

- ✅ Validación de rol en servidor
- ✅ Respuesta RECHAZADO correcta
- ✅ Sin datos corruptos

---

## Test 6: Servidor caído (timeout)

**Terminal 1**: Abre servidor
```bash
python Main.py --server --port 5555 --skip-menu
```

**Terminal 2**: Cliente conecta
```bash
python Main.py --client --host 127.0.0.1 --port 5555 --role victim --skip-menu
```

**Espera a que aparezca "jugador_unido", luego:**

Mata Terminal 1 (Ctrl+C) para simular servidor caído.

### Qué esperar (en Terminal 2)

Después de ~15 segundos:
```
[2024-XX-XX HH:MM:SS] INFO: Servidor cerro la conexion
```

O después de timeout:
```
[2024-XX-XX HH:MM:SS] WARNING: Error en recv_loop del cliente: [Errno 104] Connection reset by peer
```

### Qué está pasando

- ✅ Detecta conexión perdida
- ✅ Keep-alive timeout funciona (15 segundos)
- ✅ Sin crash, solo log de error

---

## Test 7: Single-player sin networking (baseline)

```bash
python Main.py --skip-menu
```

Juega normalmente sin flags.

### Qué esperar

```
[2024-XX-XX HH:MM:SS] INFO: Inicio rápido — seed=None  sala=None  debug=False  modo=offline
```

**Sin logs de networking**, solo logs de gameplay normales.

### Qué está pasando

- ✅ Modo offline, no hay network
- ✅ Self.net = None
- ✅ Gameplay idéntico al antes

---

## Checklist de Validación

Marca cada test cuando pase:

```
□ Test 1: Servidor solo arranca sin errores
□ Test 2: Un cliente conecta y recibe handshake
□ Test 3: Dos clientes conectan y ven "jugador_unido"
□ Test 4: Cierre limpio sin crashes
□ Test 5: Validación de rol (rechaza duplicados)
□ Test 6: Timeout detection (servidor caído)
□ Test 7: Single-player funciona sin networking
```

Si todos pasan → **NETWORKING FUNCIONA** ✅

---

## Debugging: Qué hacer si falla

### Problema: "Address already in use"

```bash
# Puerto 5555 ya está ocupado
# Solución: usa otro puerto
python Main.py --server --port 5556 --skip-menu
```

### Problema: "Connection refused"

```bash
# Servidor no está corriendo
# Verificar: ¿ves "Servidor escuchando" en Terminal 1?
# Si no: revisa logs de Terminal 1 para ver qué error hay
```

### Problema: Cliente conecta pero no ve "jugador_unido"

```bash
# Posible problema: evento no se procesa
# Verificar logs: busca "[NET] Evento:"
# Si no aparece: el tick() de networking no se llama
# Solución: revisar que Game._update() tenga la llamada a net.tick()
```

### Problema: Juego se abre pero cuelga

```bash
# Posible deadlock en threading
# Revisar: ¿hay locks mal adquiridos?
# Verificar: revisar logs para ver dónde se detiene
# Solución: usar Ctrl+C y revisar traceback
```

### Problema: Logs no aparecen

```bash
# Posible: nivel de logging muy alto
# Solución: revisar dev/logger.py, `log_net` debería estar en INFO
# O: ejecutar con DEBUG
python Main.py --server --port 5555 --skip-menu --debug
```

---

## Logs importantes (busca estas palabras)

| Palabra | Significa |
|---------|-----------|
| "Servidor escuchando" | ✅ Servidor arrancó |
| "Conectado como" | ✅ Cliente se autenticó |
| "jugador_unido" | ✅ Evento propagado |
| "Conexion cerrada" | ✅ Desconexión limpia |
| "Connection refused" | ❌ Servidor no responde |
| "El rol ... ya está ocupado" | ✅ Validación correcta |
| "Timeout" | ⚠️ Conexión muy lenta |
| "ERROR" o "CRITICAL" | ❌ Problema serio |

---

## Conclusión

Si ves estos 3 logs en las 3 terminales:

```
Terminal 1: Servidor escuchando en 0.0.0.0:5555
Terminal 2: Conectado como victima
Terminal 3: Conectado como aliado
Ambas: jugador_unido
```

## ✅ EL NETWORKING FUNCIONA CORRECTAMENTE

No hay UI visual todavía (eso es Phase 2), pero la infraestructura está probada y funcionando.
