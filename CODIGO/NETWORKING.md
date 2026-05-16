# Sistema Multijugador LAN — Echoes

## Visión General

Echoes implementa un **sistema cliente-servidor asimétrico** para multijugador local (LAN). 

- **VICTIMA** → Controla al personaje principal (movimiento, ataques, transiciones)
- **ALIADO** → Rol de soporte remoto (envía recursos, curación, mejoras)

El servidor hospeda la sesión y sincroniza el estado del juego entre clientes.

---

## Arquitectura

```
┌─────────────────────────────────────────────┐
│         ServidorEchoes (port 5555)          │
│  (hospeda sesión, valida acciones, syncro)  │
└────────┬──────────────────────┬─────────────┘
         │                      │
    Cliente VICTIMA        Cliente ALIADO
   (controla juego)      (envía apoyo)
```

### Componentes

| Archivo | Descripción |
|---------|-------------|
| `network/protocol.py` | Protocolo JSON (Mensaje, TipoMensaje, Rol) |
| `network/server.py` | ServidorEchoes (TCP, multi-cliente, threading) |
| `network/client.py` | ClienteEchoes (TCP, recepción daemon) |
| `network/manager.py` | NetworkManager (API unificada para Game.py) |
| `Main.py` | Punto de entrada con flags --server/--client |
| `Game.py` | Integración de net.tick() en game loop |

---

## Modo de Uso

### 1️⃣ Servidor

Abre una terminal y ejecuta:

```bash
cd CODIGO
python Main.py --server --port 5555 --skip-menu
```

**Salida esperada:**
```
[2024-XX-XX] INFO: Servidor escuchando en 0.0.0.0:5555
Echoes arranca, espera clientes...
```

El servidor corre en la misma máquina que la VICTIMA.

### 2️⃣ Cliente VICTIMA

Abre otra terminal (misma máquina o red local):

```bash
python Main.py --client --host 127.0.0.1 --port 5555 --role victim --skip-menu
```

O si el servidor está en otra IP:
```bash
python Main.py --client --host 192.168.1.100 --port 5555 --role victim --skip-menu
```

**Salida esperada:**
```
[2024-XX-XX] INFO: Conectado al servidor como victim
Echoes arranca, conectado al servidor
```

### 3️⃣ Cliente ALIADO

Abre una tercera terminal:

```bash
python Main.py --client --host 127.0.0.1 --port 5555 --role ally --skip-menu
```

**Salida esperada:**
```
[2024-XX-XX] INFO: Conectado al servidor como ally
✅ Jugador ally se unió a la sesión
```

---

## Flags CLI

### Servidor

```bash
python Main.py --server [opciones]
```

| Flag | Default | Descripción |
|------|---------|-------------|
| `--port PORT` | 5555 | Puerto TCP en el que escuchar |
| `--skip-menu` | - | Salta menú y inicia directo |
| `--debug` | - | Habilita consola debug (F1) |

### Cliente

```bash
python Main.py --client [opciones]
```

| Flag | Default | Descripción |
|------|---------|-------------|
| `--host ADDR` | 127.0.0.1 | IP/hostname del servidor |
| `--port PORT` | 5555 | Puerto del servidor |
| `--role ROLE` | victim | `victim` o `ally` |
| `--skip-menu` | - | Salta menú |
| `--debug` | - | Habilita consola debug |

### Offline (Single-player)

```bash
python Main.py --skip-menu
# o sin flags
python Main.py
```

---

## Protocolo de Mensajes

Todos los mensajes son JSON terminados en newline (`\n`). Ejemplo:

```json
{"tipo": "conectar", "datos": {"rol": "victim", "version": "1.0"}, "origen": null, "ts": 1714000000.123}
{"tipo": "aceptado", "datos": {"rol": "victim", "seed": 12345}, "origen": "servidor", "ts": 1714000000.130}
{"tipo": "evento", "datos": {"evento": "jugador_unido", "rol": "ally", "conectados": ["victim", "ally"]}, "origen": "servidor", "ts": 1714000000.140}
```

### Tipos de Mensaje

| Tipo | Dirección | Descripción |
|------|-----------|-------------|
| `conectar` | cliente → servidor | Anunciar rol |
| `aceptado` | servidor → cliente | Confirmar conexión |
| `rechazado` | servidor → cliente | Rechazar conexión |
| `estado` | cliente → servidor | Posición, HP, sala |
| `accion` | cliente → servidor | Input del jugador |
| `apoyo` | cliente → servidor | Acción de soporte (ALIADO) |
| `evento` | servidor → clientes | Evento de juego |
| `ping`/`pong` | ambos | Keep-alive |
| `desconectar` | cliente → servidor | Cierre limpio |

---

## Integración con Game.py

### Inicializar NetworkManager

En `Game.__init__()`, el NetworkManager se crea automáticamente según el modo:

```python
# Servidor
self.net = NetworkManager.como_servidor(port=5555, seed=None)
self.net.iniciar()

# Cliente
self.net = NetworkManager.como_cliente(host="192.168.1.10", port=5555, rol="victim")
self.net.iniciar()
```

### Procesar eventos cada frame

En `Game._update()`, se llama a `net.tick()` para procesar mensajes:

```python
if self.net:
    net_eventos = self.net.tick()
    for ev in net_eventos:
        self._procesar_evento_red(ev)
```

### Tipos de EventoRed

```python
class EventoRed:
    tipo: str              # "jugador_unido", "estado", "error_red", ...
    datos: dict            # payload del evento
    origen: str | None     # "victima", "aliado", "servidor"
```

### Ejemplos de eventos

```python
# Jugador se unió
EventoRed(tipo="jugador_unido", 
          datos={"rol": "ally", "conectados": ["victim", "ally"]},
          origen="servidor")

# Estado del otro jugador
EventoRed(tipo="estado",
          datos={"pos": [100.5, 200.3], "sala": [5, 3], "hp": 8, "vidas": 10},
          origen="victima")

# Apoyo recibido (ALIADO → VICTIMA)
EventoRed(tipo="apoyo_recibido",
          datos={"apoyo": "curar", "valor": 2},
          origen="aliado")
```

---

## Logs de Red

Los eventos de red se registran en `dev/logger.py` bajo `log_net`.

Activa logs detallados (desde DebugConsole o aumentando nivel de logging):

```
[2024-XX-XX] INFO: [NET] Evento: jugador_unido desde servidor
[2024-XX-XX] INFO: ✅ Jugador ally se unió a la sesión
```

---

## Testing

### Test 1: Servidor solo

```bash
python Main.py --server --port 5555 --skip-menu
```

Espera logs: `Servidor escuchando en 0.0.0.0:5555`

### Test 2: Servidor + 1 cliente (VICTIMA)

**Terminal 1:**
```bash
python Main.py --server --port 5555 --skip-menu
```

**Terminal 2:**
```bash
python Main.py --client --host 127.0.0.1 --port 5555 --role victim --skip-menu
```

Espera logs: ambos arrancando sin crashes

### Test 3: Servidor + 2 clientes

**Terminal 1:**
```bash
python Main.py --server --port 5555 --skip-menu
```

**Terminal 2:**
```bash
python Main.py --client --host 127.0.0.1 --port 5555 --role victim --skip-menu
```

**Terminal 3:**
```bash
python Main.py --client --host 127.0.0.1 --port 5555 --role ally --skip-menu
```

Espera logs:
- `✅ Jugador victim se unió`
- `✅ Jugador ally se unió`

### Test 4: Offline (single-player)

```bash
python Main.py --skip-menu
```

Espera: juego funciona normalmente, sin networking

---

## Roadmap: Fases Futuras

### Phase 2 (Sincronización Básica) ⏳

- [ ] Enviar posición del jugador cada frame
- [ ] Renderizar otro jugador en pantalla
- [ ] Sincronizar sala actual
- [ ] Mostrar estado remoto (HP, vidas)

### Phase 3 (Interacción Multijugador) ⏳

- [ ] Sistema de apoyo (ALIADO cura a VICTIMA)
- [ ] Sincronizar enemigos
- [ ] Proyectiles compartidos
- [ ] Transiciones de sala conjuntas

### Phase 4 (Polish) ⏳

- [ ] Interpolación de movimiento
- [ ] Predicción de latencia
- [ ] UI multijugador
- [ ] Estadísticas compartidas

---

## Troubleshooting

### "Connection refused" al conectar cliente

- ❌ Servidor no está corriendo
- ❌ IP incorrecta (verifica `--host`)
- ❌ Puerto incorrecto (verifica `--port`)

**Solución:** Abre terminal 1, ejecuta servidor, verifica que loguea "Servidor escuchando"

### "Rol ya ocupado"

- El rol que intentas conectar ya está tomado

**Solución:** Usa `--role ally` o `--role victim` según disponibilidad

### Cliente se desconecta sin mensaje

- Servidor caído
- Timeout por inactividad (>15 segundos sin actividad)
- Problema de red LAN

**Solución:** Revisa logs del servidor, reinicia ambos

---

## Referencias

- [protocol.py](network/protocol.py) — Especificación del protocolo
- [manager.py](network/manager.py) — API del NetworkManager
- [test_network.py](network/test_network.py) — Suite de pruebas
