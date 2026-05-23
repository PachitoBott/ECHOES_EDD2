# Flujo Sincronizado de Inicio del Juego (Servidor-Cliente)

## Problema Original

Cuando el servidor presionaba "JUGAR" en el lobby, el cliente podría:
- Recibir el mensaje con delay
- No estar listo cuando el servidor transiciona
- Estar en estados diferentes del menú

## Solución: Sistema ACK (Acknowledgement)

Implementar un protocolo de confirmación bidireccional que asegura que AMBOS inicien el juego **exactamente al mismo tiempo**.

## Flujo de Sincronización

```
┌─────────────────────────────────────────────────────────────┐
│                      SERVIDOR                  CLIENTE      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Usuario presiona "JUGAR"                               │
│     └─ setea lobby.resultado = "jugar"                     │
│                                                             │
│  2. Servidor calcula seed y prepara                        │
│     └─ enviar_inicio_juego(seed)                           │
│                                                             │
│  3. ENVÍA: {"type": "START_GAME", "seed": 12345}          │
│                                    ──────────────→         │
│                                                             │
│  4. ESPERA confirmación (timeout 5s)                       │
│     └─ cliente_confirmó_inicio = False                    │
│        [mientras espera]                                    │
│                                                             │
│                              ↓ CLIENTE RECIBE START_GAME    │
│                              │                              │
│                              ├─ iniciar_juego = True        │
│                              ├─ seed_juego = 12345          │
│                              │                              │
│                              └─ ENVÍA ACK:                  │
│                    ←──────── {"type": "ACK_START_GAME"}    │
│                                                             │
│  5. RECIBE ACK                                             │
│     └─ cliente_confirmó_inicio = True                     │
│        ✓ CONFIRM RECIBIDO                                  │
│                                                             │
│  6. Setea:                                                  │
│     ├─ _start_requested = True                            │
│     └─ running = False (sale del menú)                    │
│                                                             │
│  7. StartMenu.run() retorna con start_game=True           │
│                                                             │
│  8. Game.start_new_run() inicia                           │
│     └─ Genera dungeon                                     │
│     └─ Inicia cinemáticas                                 │
│     └─ Entra al juego                                    │
│                                                             │
│                              ↓ CLIENTE DETECTA iniciar_juego│
│                              │                              │
│                              ├─ _start_requested = True     │
│                              ├─ running = False             │
│                              │                              │
│                              └─ Game.start_new_run()       │
│                                 (igual que servidor)       │
│                                                             │
│  ✓ AMBOS EN EL JUEGO SINCRONIZADOS                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Componentes Clave

### 1. ServidorMenu (network/servidor_menu.py)

**Nuevos atributos**:
```python
self.cliente_confirmó_inicio = False      # Flag de confirmación
self.seed_juego_pendiente = None          # Seed en espera
```

**Nuevo mensaje soportado**:
```python
elif tipo == "ACK_START_GAME":
    self.cliente_confirmó_inicio = True   # Cliente confirmó
```

**Método mejorado**:
```python
def enviar_inicio_juego(self, seed: int, timeout: float = 5.0) -> bool:
    """Envía START_GAME y ESPERA confirmación del cliente."""
    # Enviar mensaje
    self.enviar({"type": "START_GAME", "seed": seed})
    
    # Esperar ACK (máximo timeout segundos)
    # Retorna True si confirmó, False si timeout
```

### 2. ClienteMenu (network/cliente_menu.py)

**Cambio en START_GAME**:
```python
elif tipo == "START_GAME":
    # 1. Setear flags
    self.iniciar_juego = True
    self.seed_juego = msg.get("seed", 0)
    
    # 2. Enviar ACK inmediatamente
    self.enviar({"type": "ACK_START_GAME", "seed": seed})
```

### 3. StartMenu (ui/StartMenu.py)

**En servidor**:
```python
cliente_listo = self.servidor_menu.enviar_inicio_juego(seed, timeout=5.0)

if cliente_listo:
    print("✓ Cliente confirmó, iniciando juego...")
    self._start_requested = True
else:
    print("⚠ Timeout, continuando sin confirmación...")
    # Esperar 1s de todas formas
    time.sleep(1.0)
    self._start_requested = True
```

**En cliente**:
```python
# El cliente solo recibe START_GAME y automáticamente
# setea iniciar_juego = True, lo cual dispara la transición
if debe_iniciar:
    self.modo_coop_solicitado = True
    self._start_requested = True
    running = False
```

**Bloqueo de input del cliente**:
```python
# Cliente NO puede presionar botones del lobby
if self.cliente_menu and self.cliente_menu.conectado:
    # Solo permitir ESC
    if event.key == pygame.K_ESCAPE:
        self._start_requested = False
        running = False
    # Ignorar otros eventos
else:
    # Servidor SÍ puede presionar botones normalmente
    self.lobby.handle_event(event)
```

## Garantías de Sincronización

✅ **Timing**: Servidor espera confirmación antes de salir del menú
✅ **Orden**: Cliente SIEMPRE recibe START_GAME antes de que servidor transicione  
✅ **Fallback**: Si timeout (5s), servidor continúa de todas formas
✅ **Thread-safe**: Acceso a flags con locks
✅ **Bloqueo de UI**: Cliente no puede presionar botones en lobby

## Casos Especiales

### Caso 1: Cliente se desconecta antes de ACK

**Timeout**: Servidor espera 5 segundos, luego continúa solo
```python
if cliente_listo:
    # Cliente confirmó
    pass
else:
    # Timeout: cliente desconectado o lento
    time.sleep(1.0)  # Esperar un poco más
    self._start_requested = True
```

### Caso 2: Red lenta

**Timeout de 5 segundos**: Suficiente para redes lentes, pero no espera infinito
- Si ACK llega antes de 5s → sincronización perfecta
- Si ACK no llega → fallback a 1s de delay

### Caso 3: Sin cliente conectado

**Servidor solo**: `enviar_inicio_juego()` retorna True inmediatamente (sin esperar)
```python
if self.servidor_menu.cliente_conectado:
    # Esperar cliente
    cliente_listo = self.servidor_menu.enviar_inicio_juego(seed)
else:
    # Sin cliente, iniciar solo
    self._start_requested = True
```

## Logs de Debug

Para verificar el flujo, busca estos logs:

**Servidor**:
- `[SERVIDOR] Enviando START_GAME con seed X...`
- `[SERVIDOR] ✓ Cliente confirmó, iniciando juego...`
- `[SERVIDOR] ⚠ Timeout esperando confirmación...`

**Cliente**:
- `[CLIENTE] Recibido START_GAME: seed=X`
- `[CLIENTE] ACK_START_GAME enviado al servidor`
- `[CLIENTE MENU] ACK_START_GAME enviado`

**ServidorMenu**:
- `[SERVIDOR MENU] Cliente confirmó inicio del juego`

## Mejoras Futuras

1. **Retry automático**: Si primer ACK falla, reintentar 1-2 veces
2. **Progress bar**: Mostrar "Sincronizando..." mientras espera confirmación
3. **Timeout adaptativo**: Medir latencia y ajustar timeout automáticamente
4. **Heartbeat**: Enviar pings periódicos para detectar desconexiones rápidamente

## Testing

Para verificar que funciona:

### Test 1: Servidor presiona JUGAR
```bash
# Terminal 1 (Servidor)
python Main.py --server --port 5555

# Terminal 2 (Cliente)  
python Main.py --client --host 127.0.0.1 --port 5555 --role victim

# Servidor: navega a lobby y presiona JUGAR
# ✓ Cliente debería recibir START_GAME y entrar al juego al mismo tiempo
```

### Test 2: Red lenta (simular delay)
- Agregar `time.sleep(2.0)` en ClienteMenu._recibir_mensajes()
- Servidor debería esperar, cliente eventualmente confirmará
- Ambos deberían sincronizarse

### Test 3: Cliente desconectado
- Cerrar cliente DESPUÉS de que llega START_GAME pero ANTES de que envíe ACK
- Servidor debería hacer timeout y continuar solo (con 1s de delay)
