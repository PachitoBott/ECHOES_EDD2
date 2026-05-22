# Plan: Sincronización de Transiciones de Cuarto

## Objetivo
Cuando CUALQUIER jugador active una puerta/transición, AMBOS jugadores deben pasar al siguiente cuarto simultáneamente, sin importar quién activó la puerta.

**Referencia:** The Binding of Isaac - si un jugador entra a una puerta, el otro es teletransportado automáticamente.

---

## Situación Actual (Problema)
- El servidor (VICTIMA) ejecuta `_handle_room_transition()` y se mueve cuando toca una puerta
- El cliente (ALIADO) TAMBIÉN ejecuta `_handle_room_transition()` pero se mueve SOLO localmente
- El resultado: Los dos jugadores en salas diferentes

**Logs esperados que demostren el problema:**
```
Terminal 1 (Servidor): "Room transition detected: moving to (5,4)"
Terminal 2 (Cliente): "Room transition detected: moving to (5,4)" pero servidor sigue en (0,0)
```

---

## Arquitectura Propuesta

### Enfoque: Servidor como Autoridad

El servidor (VICTIMA) es la autoridad. Solo el servidor procesa transiciones y teletransporta a ambos.

**Flujo:**
```
┌─────────────────────────────────────────────────────┐
│ CLIENTE (ALIADO) toca una puerta                    │
├─────────────────────────────────────────────────────┤
│ 1. Detecta check_exit() en local (antes de moverse) │
│ 2. Envía msg_accion("transicion", dir="N") al server│
│ 3. ESPERA respuesta (no se mueve aún)               │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ SERVIDOR (VICTIMA) toca una puerta                  │
├─────────────────────────────────────────────────────┤
│ 1. Detecta check_exit() en local                    │
│ 2. Procesa transición: dungeon.move(dir)            │
│ 3. Posiciona VICTIMA en entry point                 │
│ 4. TAMBIÉN teletransporta ALIADO (si está en sesión)│
│ 5. Envía msg_evento("transicion_completada", ...)  │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ CLIENTE (ALIADO) recibe evento                      │
├─────────────────────────────────────────────────────┤
│ 1. Desaparece la puerta (transición animada)        │
│ 2. Carga nueva sala                                 │
│ 3. ALIADO teletransportado al entry point           │
│ 4. Enemigos cargados                                │
└─────────────────────────────────────────────────────┘
```

---

## Cambios Necesarios

### 1. Protocol.py - Mensajes de Red

**Ya existe:**
```python
msg_accion(tipo_accion="transicion", direccion="N"|"S"|"E"|"W")
```

**Agregar:**
```python
def msg_transicion_completada(
    sala_nueva: tuple[int, int],
    pos_victima: tuple[float, float],
    pos_aliado: tuple[float, float],
) -> Mensaje:
    """Notifica que la transición se completó en el servidor."""
    return Mensaje(
        TipoMensaje.EVENTO,
        {
            "evento": "transicion_completada",
            "sala_nueva": list(sala_nueva),
            "pos_victima": list(pos_victima),
            "pos_aliado": list(pos_aliado),
        },
        origen=Rol.SERVIDOR,
    )
```

### 2. Game.py - Cliente: No procesar transiciones localmente

**Cambio en _handle_room_transition():**

```python
def _handle_room_transition(self, room) -> None:
    if not hasattr(room, "check_exit"):
        return
    if getattr(room, "locked", False):
        return
    if self.door_cooldown > 0.0:
        return

    direction = room.check_exit(self.player)
    if not direction or not self.dungeon.can_move(direction):
        return

    # EN MODO CLIENTE: Notificar al servidor, NO procesar localmente
    if self.net and not self.net.es_servidor:
        log_game.info(f"[TRANSICION] Cliente detectó puerta en dirección {direction}")
        # Enviar acción al servidor
        from network.protocol import msg_accion
        msg = msg_accion("transicion", direccion=direction)
        self.net.enviar(msg)
        self.door_cooldown = 0.25  # Cooldown para evitar spam
        return

    # EN MODO SERVIDOR O OFFLINE: Procesar transición
    self._procesar_transicion(direction, room)

def _procesar_transicion(self, direction: str, room) -> None:
    """Procesa la transición y teletransporta a ambos jugadores."""
    if hasattr(self.dungeon, "move_and_enter"):
        moved = self.dungeon.move_and_enter(
            direction, self.player, self.cfg, ShopkeeperCls=Shopkeeper
        )
    else:
        self.dungeon.move(direction)
        moved = True
    
    if not moved:
        return

    # Posicionar al SERVIDOR
    victima_pos = self.dungeon.entry_position(
        direction, self.player.w, self.player.h
    )
    self.player.x, self.player.y = victima_pos

    # Teletransportar al CLIENTE (si está conectado)
    if self.net and self.net.es_servidor and self.remote_players:
        # Calcular posición de entrada para el cliente
        # (probablemente la misma, pero podría ser diferente)
        aliado_pos = victima_pos  # Mismo punto de entrada

        # Notificar al cliente
        from network.protocol import msg_evento
        msg = msg_evento(
            "transicion_completada",
            sala_nueva=list((self.dungeon.i, self.dungeon.j)),
            pos_victima=list(victima_pos),
            pos_aliado=list(aliado_pos),
        )
        self.net.enviar(msg)

    # Limpiar y actualizar
    self.dungeon.explored.add((self.dungeon.i, self.dungeon.j))
    self.door_cooldown = 0.25
    self.projectiles.clear()
    self.enemy_projectiles.clear()

    new_room = self.dungeon.current_room
    depth = self.dungeon.depth_map.get((self.dungeon.i, self.dungeon.j), -1)
    log_room.room_enter((self.dungeon.i, self.dungeon.j), depth)
    self._spawn_room_enemies(new_room)
    self._update_room_lock(new_room)
```

### 3. Game.py - Servidor: Procesar acción de transición

**En _procesar_evento_red():**

```python
elif ev.tipo == "accion":
    self._procesar_accion(ev)

def _procesar_accion(self, ev: EventoRed) -> None:
    """Procesa acciones enviadas por el cliente."""
    accion = ev.datos.get("accion")
    origen = ev.origen

    if accion == "transicion":
        # Cliente solicita transición en dirección
        direccion = ev.datos.get("direccion")
        if direccion:
            log_game.info(f"[TRANSICION] Servidor procesando transición de {origen} en dirección {direccion}")
            room = self.dungeon.current_room
            if not getattr(room, "locked", False):
                self._procesar_transicion(direccion, room)

    # ... otras acciones ...
```

### 4. Game.py - Cliente: Recibir evento de transición completada

**En _procesar_evento_red():**

```python
elif ev.tipo == "transicion_completada":
    self._handle_transicion_completada(ev)

def _handle_transicion_completada(self, ev: EventoRed) -> None:
    """Recibe notificación de transición desde el servidor."""
    sala_nueva = tuple(ev.datos.get("sala_nueva", [0, 0]))
    pos_aliado = tuple(ev.datos.get("pos_aliado", [0, 0]))

    log_game.info(f"[TRANSICION] Cliente recibió transición completada a sala {sala_nueva}, pos={pos_aliado}")

    # Mover a la nueva sala
    self.dungeon.i, self.dungeon.j = sala_nueva
    
    # Posicionar al jugador (ALIADO)
    self.player.x, self.player.y = pos_aliado

    # Limpiar y actualizar
    self.projectiles.clear()
    self.enemy_projectiles.clear()
    self.door_cooldown = 0.25

    room = self.dungeon.current_room
    depth = self.dungeon.depth_map.get((self.dungeon.i, self.dungeon.j), -1)
    log_room.room_enter((self.dungeon.i, self.dungeon.j), depth)
    self._spawn_room_enemies(room)
    self._update_room_lock(room)
```

---

## Testing

### Test 1: Servidor activa puerta
1. PC1 (Servidor) toca una puerta → PC1 y PC2 ambos transicionan
2. Logs esperados:
   ```
   Terminal 1: "[TRANSICION] Servidor procesando transición... dirección N"
   Terminal 1: "Room enter: (0,1) at depth..."
   Terminal 2: "[TRANSICION] Cliente recibió transición completada a sala (0, 1)"
   ```

### Test 2: Cliente activa puerta  
1. PC2 (Cliente) toca una puerta → PC2 espera, PC1 procesa, ambos transicionan
2. Logs esperados:
   ```
   Terminal 2: "[TRANSICION] Cliente detectó puerta en dirección N"
   Terminal 1: "[TRANSICION] Servidor procesando transición de aliado en dirección N"
   Terminal 2: "[TRANSICION] Cliente recibió transición completada a sala (0, 1)"
   ```

### Test 3: Ambos tocan al mismo tiempo
1. PC1 y PC2 tocan diferentes puertas simultáneamente → El servidor procesa la suya y teletransporta al cliente
2. Debería haber solo UNA transición (la del servidor)

---

## Orden de Implementación

1. ✅ Agregar `msg_evento("transicion_completada", ...)` en protocol.py
2. Modificar `_handle_room_transition()` en Game.py
3. Crear `_procesar_transicion()` en Game.py
4. Crear `_procesar_accion()` en Game.py
5. Crear `_handle_transicion_completada()` en Game.py
6. Agregar manejo de "accion" en `_procesar_evento_red()` en Game.py
7. Testing y debugging

---

## Consideraciones Especiales

### Cooldown de Puertas
- Mantener `self.door_cooldown` de 0.25s para evitar spam
- Es importante para ambos (servidor y cliente)

### Salas Bloqueadas
- Si la sala está bloqueada (tiene enemigos), la transición no se procesa
- Verificar en el servidor: `if getattr(room, "locked", False)`

### Proyectiles y Pickups
- Limpiar `self.projectiles` y `self.enemy_projectiles` en ambos
- Los pickups se sincronizan vía red, así que se limpiarán automáticamente

### Cinemáticas
- Si la nueva sala dispara una cinemática, asegurarse que ambos jugadores la vean
- Probablemente requiera un mensaje de red adicional

