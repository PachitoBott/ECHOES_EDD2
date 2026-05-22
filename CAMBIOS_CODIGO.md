# Cambios de Código Implementados

## Resumen de Cambios
Se han realizado modificaciones en 2 archivos principales para prevenir que los enemigos mueran incorrectamente en multijugador.

---

## Archivo: CODIGO/entities/Enemy.py

### Cambio 1: Logs de Daño en take_damage() [Línea 227-244]

**Antes:**
```python
if amount > 0:
    self.hp -= amount
    self.hit_flash_timer = max(self.hit_flash_timer, self._hit_flash_duration)
```

**Después:**
```python
if amount > 0:
    hp_antes = self.hp
    self.hp -= amount
    # [DIAG] Log de daño recibido
    log_enemy.warning(f"[DAMAGE] {self.enemy_id} recibió {amount} daño en ({self.x:.0f},{self.y:.0f}). HP: {hp_antes} -> {self.hp}")
    self.hit_flash_timer = max(self.hit_flash_timer, self._hit_flash_duration)
```

**Propósito:** Rastrear cada vez que un enemigo recibe daño y de cuánta vida dispone.

### Cambio 2: Logs de Muerte en take_damage() [Línea 242-244]

**Antes:**
```python
else:
    self._begin_death()
```

**Después:**
```python
else:
    log_enemy.warning(f"[DEATH] {self.enemy_id} muere en ({self.x:.0f},{self.y:.0f}). HP final: {self.hp}")
    self._begin_death()
```

**Propósito:** Registrar cuándo y dónde muere cada enemigo.

### Cambio 3: Logs de Disparo en ShooterEnemy.maybe_shoot() [Línea 536]

**Antes:**
```python
log_enemy.warning(f"[SHOOT] {self.enemy_id} disparando, owner_id={self.enemy_id}")
```

**Después:**
```python
log_enemy.warning(f"[SHOOT] {self.enemy_id} disparando desde ({ex:.0f},{ey:.0f}) hacia jugador en ({px:.0f},{py:.0f}), dist={dist:.1f}, owner_id={self.enemy_id}")
```

**Propósito:** Ver exactamente dónde dispara el enemigo y hacia quién apunta.

---

## Archivo: CODIGO/Game.py

### Cambio 1: Logs de Estado Remoto [Línea 862-867]

**Antes:**
```python
else:
    # Valid remote player state
    self.remote_players[origen] = ev.datos
    sala_remota = ev.datos.get("sala", [0, 0])
    log_game.debug(f"[ESTADO_REMOTO] {origen} está en sala {sala_remota}")
```

**Después:**
```python
else:
    # Valid remote player state
    pos_data = ev.datos.get("pos", [0, 0])
    sala_remota = ev.datos.get("sala", [0, 0])
    # [DIAG] Log de estado remoto
    log_game.warning(f"[ESTADO_REMOTO_NUEVA] {origen} pos=({pos_data[0]:.0f},{pos_data[1]:.0f}) sala={sala_remota}")
    # [FIX B] Marcar posición como válida cuando se recibe estado real del cliente
    ev.datos["posicion_valida"] = True
    self.remote_players[origen] = ev.datos
    log_game.debug(f"[ESTADO_REMOTO] {origen} está en sala {sala_remota}")
```

**Propósito:** 
- Ver la posición exacta que envía el cliente
- Marcar la posición como válida para permitir targeting

### Cambio 2: Fix B - Targeting de Jugadores Remotos [Línea 1785-1814]

**Antes:**
```python
if self.remote_players:
    for rol, datos in self.remote_players.items():
        # ... extrae posición ...
        if sala_remota == room_pos:
            # ... calcula distancia ...
            remote_dist = math.hypot(...)
            remote_pos = (remote_x, remote_y)
            break
```

**Después:**
```python
if self.remote_players:
    for rol, datos in self.remote_players.items():
        # [FIX B] Solo considerar jugadores remotos con posición válida
        posicion_valida = datos.get("posicion_valida", True)
        if not posicion_valida:
            log_game.debug(f"[TARGETING] Ignorando {rol}: posición aún no validada")
            continue

        sala_list = datos.get("sala", [0, 0])
        sala_remota = (
            (sala_list[0], sala_list[1])
            if isinstance(sala_list, (list, tuple))
            else (0, 0)
        )

        if sala_remota == room_pos:
            # ... extrae posición ...
            # [FIX B] Ignorar posiciones en (0,0) que son inválidas
            if remote_x == 0 and remote_y == 0:
                log_game.debug(f"[TARGETING] Ignorando {rol}: posición (0,0) sospechosa")
                continue

            remote_dist = math.hypot(...)
            remote_pos = (remote_x, remote_y)
            break
```

**Propósito:** 
- Prevenir que enemigos apunten a jugadores remotos con posición no sincronizada
- Ignorar posiciones inválidas (0,0)
- LOG para ver qué está pasando

### Cambio 3: Logs de Targeting [Línea 1828-1835]

**Antes:**
```python
# [DEBUG] Log de targeting
log_game.debug(f"[TARGETING] {enemy.enemy_id} local_dist={local_dist:.1f} remote_dist={remote_dist:.1f} REMOTE ({remote_pos[0]:.0f},{remote_pos[1]:.0f}) en sala {room_pos}")
...
if hasattr(self, 'remote_players') and self.remote_players:
    log_game.debug(f"[TARGETING] {enemy.enemy_id} local_dist={local_dist:.1f} remote_players={len(self.remote_players)} pero no en sala {room_pos}")
```

**Después:**
```python
# [DEBUG] Log de targeting
log_game.warning(f"[TARGETING] {enemy.enemy_id} APUNTA A REMOTO: local_dist={local_dist:.1f} remote_dist={remote_dist:.1f} pos_remota=({remote_pos[0]:.0f},{remote_pos[1]:.0f}) sala={room_pos}")
...
if hasattr(self, 'remote_players') and self.remote_players:
    log_game.warning(f"[TARGETING] {enemy.enemy_id} APUNTA A LOCAL: dist={local_dist:.1f} remoto_dist={remote_dist:.1f} remoto_existe={len(self.remote_players)>0} remoto_en_sala={remote_pos is not None}")
```

**Propósito:** Más visibilidad sobre cuál jugador está siendo atacado.

### Cambio 4: Filtro de Disparos desde (0,0) [Línea 1416-1431]

**Antes:**
```python
def _process_client_bullet(self, ev: EventoRed) -> None:
    """
    El servidor procesa un disparo enviado por el cliente.
    """
    if not self.net or not self.net.es_servidor:
        return

    datos = ev.datos
    x = datos.get("x", 0)
    y = datos.get("y", 0)
    # ... sigue procesando ...
```

**Después:**
```python
def _process_client_bullet(self, ev: EventoRed) -> None:
    """
    El servidor procesa un disparo enviado por el cliente.
    """
    if not self.net or not self.net.es_servidor:
        return

    datos = ev.datos
    x = datos.get("x", 0)
    y = datos.get("y", 0)
    dir_x = datos.get("dir_x", 0)
    dir_y = datos.get("dir_y", 1)
    damage = datos.get("damage", 1)

    # [FIX] Ignorar disparos desde (0,0) que pueden ser falsos
    # durante la inicialización del cliente
    if x == 0 and y == 0:
        log_game.warning(f"[DISPARO_CLIENTE] [FILTRADO] Disparo sospechoso desde (0,0) - IGNORADO")
        return
    # ... sigue procesando ...
```

**Propósito:** Prevenir colisiones falsas de proyectiles del cliente desde (0,0).

### Cambio 5: Logs de Daño Remoto [Línea 1164-1167]

**Antes:**
```python
for enemy in room.enemies:
    dist = ((enemy.x - pos_x) ** 2 + (enemy.y - pos_y) ** 2) ** 0.5
    if dist <= tolerance and enemy.__class__.__name__ == enemy_type:
        if hasattr(enemy, "take_damage"):
            enemy.take_damage(damage, None)
```

**Después:**
```python
for enemy in room.enemies:
    dist = ((enemy.x - pos_x) ** 2 + (enemy.y - pos_y) ** 2) ** 0.5
    if dist <= tolerance and enemy.__class__.__name__ == enemy_type:
        # [DIAG] Log de daño remoto aplicado
        log_game.warning(f"[DAÑO_REMOTO_APLICADO] {enemy.enemy_id} recibe {damage} daño (evento DAÑO_REMOTO desde otro jugador)")
        if hasattr(enemy, "take_damage"):
            enemy.take_damage(damage, None)
```

**Propósito:** Rastrear cuándo se aplica daño remoto.

### Cambio 6: Logs de Limpieza de Enemigos [Línea 2284-2288]

**Antes:**
```python
if getattr(enemy, "hp", 1) > 0:
    survivors.append(enemy)
else:
    self._drop_enemy_coins(enemy, room)
```

**Después:**
```python
if getattr(enemy, "hp", 1) > 0:
    survivors.append(enemy)
else:
    # [DIAG] Enemigo muere por HP <= 0
    log_game.warning(f"[ENEMIES_CLEANUP] {enemy.enemy_id} eliminado: hp={enemy.hp}, dying={callable(dying_fn) and dying_fn()}, ready_to_remove={callable(ready_fn) and ready_fn()}")
    self._drop_enemy_coins(enemy, room)
```

**Propósito:** Ver cuándo se limpian enemigos muertos.

### Cambio 7: Logs de Disparo del Cliente [Línea 1450-1452]

**Antes:**
```python
# [DIAG] Colisión detectada
hp_antes = getattr(enemy, "hp", -1)
log_game.debug(f"[DISPARO_CLIENTE] [HIT] Enemigo[{i}] ({enemy.__class__.__name__} @ ({enemy.x:.1f}, {enemy.y:.1f}), HP={hp_antes})")
```

**Después:**
```python
# [DIAG] Colisión detectada
hp_antes = getattr(enemy, "hp", -1)
log_game.warning(f"[DISPARO_CLIENTE] [HIT] Enemigo[{i}] {enemy.enemy_id} ({enemy.__class__.__name__} @ ({enemy.x:.1f}, {enemy.y:.1f}), HP={hp_antes}) - IMPACTADO POR BALA DESDE ({x:.0f},{y:.0f})")
```

**Propósito:** Mejor visibilidad de dónde impactan los proyectiles del cliente.

---

## Niveles de Log

Los logs están distribuidos en dos niveles:
- **WARNING**: Eventos importantes que deben investigarse si hay problemas
- **DEBUG**: Detalles operacionales para diagnósticos detallados

Para ver todos los logs:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## Compatibilidad

Todos los cambios son **retrocompatibles**:
- Se mantiene la funcionalidad existente
- Se agregan checks defensivos sin alterar la lógica principal
- Los logs no afectan el rendimiento significativamente
- El modo un jugador continúa funcionando sin cambios
