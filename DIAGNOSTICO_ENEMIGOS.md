# Diagnóstico: Enemigos Ignoran al Cliente + Se Vuelven Invisibles

## Análisis de Arquitectura Actual

### P1: ¿Dónde se crean los enemigos?

**Respuesta:**
- Los enemigos se crean en `room.ensure_spawn()` (método del Dungeon/Room)
- Se llama desde `Game._spawn_room_enemies()` cuando se entra a una sala
- Los enemigos se crean EN AMBAS MÁQUINAS para la misma sala (con la misma seed)
- NO hay diferenciación entre enemigos "locales" y "remotos" en la creación

**Ubicación:**
- `Game._spawn_room_enemies()` línea 1237
- Llamada en `Game._update()` línea 1202

**Conclusión:** Los enemigos existen en ambas máquinas para la misma sala, pero...

---

### P2: ¿Cómo funciona el targeting de enemigos?

**Respuesta:**
```python
# Game._get_closest_player_for_enemy() línea 1261
```

El targeting funciona así:
1. **Calcula distancia al jugador local:** `local_dist = hypot(player.x - enemy.x, player.y - enemy.y)`
2. **Busca en `self.remote_players` (si existe)**
3. **Solo considera jugador remoto si está en la misma sala:**
   ```python
   if sala_remota == (self.dungeon.i, self.dungeon.j):
       remote_x = datos.get("pos_x", 0)
       remote_y = datos.get("pos_y", 0)
       remote_dist = hypot(...)
   ```
4. **Retorna el más cercano**

**PROBLEMA IDENTIFICADO:**
- Si `self.remote_players` está vacío → solo retorna `self.player` (jugador local)
- En un cliente que entra PRIMERO a una sala, `self.remote_players` probablemente está vacío
- Resultado: **Enemigos solo conocen al jugador local, ignoran al remoto**

**¿Cuándo se actualiza `self.remote_players`?**
- Línea 675: `self.remote_players[origen] = ev.datos` cuando llega evento "estado"
- Incluye: `pos_x`, `pos_y`, `sala`, `hp`, `vidas`, `apoyo`
- El servidor envía cada ~50ms (según protocolo)

**Conclusión:** El targeting SÍ intenta considerar jugadores remotos, PERO falsa cuando el remoto no ha enviado un update aún.

---

### P3: ¿Qué pasa cuando el cliente entra primero a una sala?

**Respuesta:**

1. **PC2 (cliente) entra a sala (4, 5)**
   - Se llama `_spawn_room_enemies()` 
   - Se crea una lista de enemigos en `room.enemies`
   - Los enemigos comienzan a actualizar

2. **En `Game._update_enemies()` (línea 1327)**:
   - Se itera `for enemy in room.enemies`
   - Se llama `enemy.update(dt, closest_player, room)`
   - `closest_player` viene de `_get_closest_player_for_enemy(enemy)`

3. **Problema:**
   - `self.remote_players` en PC2 está vacío (el servidor no ha enviado actualización aún)
   - `_get_closest_player_for_enemy()` retorna solo `self.player` (el cliente mismo)
   - **Los enemigos solo ven al cliente, no saben que un servidor existe**

4. **Cuando PC1 (servidor) entra a la misma sala:**
   - PC1 ACTUALIZA sus enemigos (los que ya creó)
   - PC1 comienza a sincronizar enemigos vía `_sync_enemies_to_client()` (línea 1452)
   - PC1 envía animator_state, facing_right, etc.
   - PC2 recibe y procesa en `_handle_enemies_state()` (línea 849)

**Conclusión:** Cuando PC2 entra primero, los enemigos no tienen un target válido durante segundos hasta que PC1 se conecte.

---

### P4: ¿Qué mensajes de red existen actualmente?

**Respuesta - Mensajes relacionados con enemigos:**

1. **`estado` (bidireccional)**
   - Cliente → Servidor: Posición del jugador local
   - Servidor → Cliente: Posición del jugador del servidor
   - Incluye: `pos_x`, `pos_y`, `sala`, `hp`, `vidas`, `apoyo`
   - Frecuencia: ~10 veces por segundo (línea 1147)
   - **Problema:** Incluye sala pero sin identificador de "qué jugador es este"

2. **`enemies_state` (Servidor → Cliente)**
   - Sincroniza estado de TODOS los enemigos de una sala
   - Incluye: `id`, `tipo`, `x`, `y`, `health`, `vivo`, `animator_state`, `facing_right`
   - Frecuencia: Cada 50ms (línea 1464)

3. **`enemy_projectiles_state` (Servidor → Cliente)**
   - Sincroniza proyectiles de enemigos
   - Incluye posición y dirección

4. **`enemigo_muerto` (Servidor → Cliente)**
   - Evento cuando un enemigo muere

5. **`proyectil_disparado` (Cliente → Servidor)**
   - Notifica cuando el cliente dispara

6. **`enemigo_danado` (Cliente → Servidor)**
   - Notifica daño hecho al enemigo

**Problema identificado:** 
- No hay mensaje `PLAYER_ENTERED_ROOM` o similar
- El servidor no sabe cuándo un cliente entra a una sala hasta que recibe un "estado"
- Los enemigos pueden estar esperando actualizaciones de jugador remoto sin saberlo

---

### P5: ¿Cómo se renderizan los enemigos en el cliente?

**Respuesta:**

En `Game._update_enemies()` para cliente (línea 1320):
```python
if self.net and not self.net.es_servidor:
    # Cliente: solo actualizar FSM y animaciones
    for enemy in room.enemies:
        # Actualizar timers y FSM state
        # Pero NO llamar enemy.update() (eso movería el enemigo)
    return  # ← NO actualizar posición en cliente
```

En `_handle_enemies_state()` (línea 849):
```python
# Cuando llega enemigos_state del servidor:
for i, enemy in enumerate(room.enemies):
    enemy_id = getattr(enemy, "enemy_id", None)
    if enemy_id and enemy_id in server_enemies_by_id:
        server_data = server_enemies_by_id[enemy_id]
        
        # Sincronizar posición
        enemy.x = server_data.get("x", enemy.x)
        enemy.y = server_data.get("y", enemy.y)
        enemy.hp = server_data.get("health", enemy.hp)
        
        # Sincronizar animator_state
        animator_state = server_data.get("animator_state", "idle")
        if hasattr(enemy, "animator"):
            if animator_state == "shoot":
                enemy.animator.trigger_shoot()
            elif animator_state == "attack":
                enemy.animator.trigger_attack()
            else:
                enemy.animator.set_base_state(animator_state)
```

**Conclusión:** El renderizado en cliente depende 100% de los datos que llegan del servidor. Si el servidor no actualiza enemigos en esa sala, el cliente solo ve enemigos estáticos.

---

### P6: ¿Existe condición que haga invisible el enemigo?

**Respuesta:**

NO encontré `set_alpha()`, `alpha`, `transparent` o `visible` en:
- Enemy.py draw() method (línea 272)
- RemoteEnemy class (línea 74)
- Ningún lugar donde se manipule la opacidad

**PERO:** Encontré que hay un sistema de animator con estados. Si el animator entra en un estado incorrecto y retorna un frame vacío/incorrecto, eso podría parecer invisibilidad.

Véase Enemy.py línea 272:
```python
def draw(self, surf: pygame.Surface) -> None:
    frame = self.animator.current_surface()
    if not self._facing_right:
        frame = pygame.transform.flip(frame, True, False)
    if self.hit_flash_timer > 0.0:
        frame = frame.copy()
        flash_overlay = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
        flash_overlay.fill((255, 255, 255, 220))
        frame.blit(flash_overlay, (0, 0), special_flags=pygame.BLEND_ADD)
    dest = frame.get_rect(center=self.rect().center)
    surf.blit(frame, dest)
```

**Posible causa de "invisibilidad":**
- Si `animator.current_surface()` retorna un surface vacío o transparente
- Si el animator está en un estado incorrecto y no tiene frames

---

## RESUMEN DE HALLAZGOS

### Síntoma 1: Enemigos ignoran al cliente
**Causa probable: CAUSA A (Targeting solo al jugador local)**

```
PC2 entra primero a sala:
├─ room.enemies se crea correctamente
├─ Enemigos buscan _get_closest_player_for_enemy()
├─ self.remote_players está VACÍO (no ha llegado update del servidor aún)
├─ _get_closest_player_for_enemy() retorna solo self.player (PC2)
└─ Enemigos SOLO ven al jugador local PC2, ignoran al servidor

Cuando PC1 entra:
├─ Enemigos en PC1 ahora tienen valid targets
├─ Comienzan a ataque y move toward PC1
├─ Sincronización del servidor comienza
└─ Enemigos en PC2 siguen estáticos porque NO se mueven (dependen de servidor)
```

**Lugar del bug:**
- `Game._get_closest_player_for_enemy()` línea 1261
- El problema es que solo busca en `self.remote_players` si está poblado
- Pero cuando PC2 entra primero, `remote_players` está vacío

---

### Síntoma 2: Enemigos se vuelven invisibles en PC2 cuando atacan al servidor
**Causa probable: CAUSA D (Sala no sincronizada al entrar el cliente primero)**

```
1. PC2 entra a sala (4,5)
   ├─ Crea enemigos locales
   └─ Enemigos esperan updates del servidor

2. PC1 NO está en misma sala
   ├─ _update_remote_player_rooms() intenta sincronizar
   ├─ Pero el problema es más sutil...

3. Cuando PC1 LUEGO entra:
   ├─ PC1 comienza a atacar a enemigos
   ├─ Los enemigos en PC1 entran en animación "attack"/"shoot"
   ├─ Envían animator_state="shoot" al cliente
   ├─ El cliente aplica trigger_shoot() que cambia animator.state
   ├─ El animator intenta renderizar frame de "shoot"
   └─ Si el frame está mal o incompleto → "invisibilidad"
```

**Posible subproblema:**
- El animator en el cliente no tiene los frames correctos para "shoot"
- O hay un conflict entre el FSM del cliente y el estado del animator

---

## HIPÓTESIS FINAL

**Combinación de Causa A + Causa D:**

1. **Causa A (Targeting):**
   - PC2 entra primero, `remote_players` vacío
   - Enemigos solo ven a PC2
   - Cuando PC1 entra, el sistema de targeting ahora FUNCIONA para PC1 en el servidor
   
2. **Causa D (Sincronización):**
   - PC1 (servidor) actualiza enemigos y los envía via `enemies_state`
   - PC2 recibe e intenta sincronizar posiciones y animator_state
   - Pero hay un timing problem o un problema en cómo se aplica animator_state
   - Resultado: "invisibilidad" cuando el enemigo está en estado "shoot"

---

## PRÓXIMOS PASOS: PASO 2 - Agregar Logs

Para confirmar esta hipótesis, necesito agregar logs en:

1. **En Game._get_closest_player_for_enemy()** - Ver qué jugador retorna
2. **En Game._update_enemies()** - Ver si se actualiza posición
3. **En Game._handle_enemies_state()** - Ver si animator_state llega correctamente
4. **En Enemy.draw()** - Ver si se está renderizando

¿Autorizas que agregue estos logs temporales?
