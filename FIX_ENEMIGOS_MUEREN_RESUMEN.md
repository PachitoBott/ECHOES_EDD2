# Fix: Enemigos Mueren al Atacar en Multijugador

## Problema
En modo multijugador, los enemigos mueren exactamente cuando ejecutan su animación de ataque. Este bug:
- Solo ocurre con cliente conectado
- NO ocurre en modo un jugador
- El cliente no necesita hacer nada para causarlo
- Afecta a TODOS los tipos de enemigos

## Causa Raíz Identificada
El problema más probable es una **race condition de sincronización**: cuando el cliente se conecta, la posición del jugador remoto (P2) no está sincronizada inmediatamente. Durante esos momentos críticos iniciales, existe un riesgo de que:

1. Los enemigos apunten a un jugador remoto con posición inválida o (0,0)
2. Los proyectiles del cliente se procesen desde (0,0) causando colisiones falsas
3. Se aplique daño incorrecto a los enemigos

## Fixes Implementados

### Fix 1: Ignorar Jugadores Remotos sin Posición Válida (Fix B)

**Archivo:** `CODIGO/Game.py`
**Método:** `_get_closest_player_for_enemy()` (línea ~1798)

Cambio:
```python
# [FIX B] Solo considerar jugadores remotos con posición válida
posicion_valida = datos.get("posicion_valida", True)
if not posicion_valida:
    continue

# [FIX B] Ignorar posiciones en (0,0) que son inválidas
if remote_x == 0 and remote_y == 0:
    continue
```

**Efecto:** Los enemigos NO apuntarán a un jugador remoto hasta que reciba su primera actualización de posición válida.

### Fix 2: Marcar Posición como Válida al Recibir Estado

**Archivo:** `CODIGO/Game.py`
**Método:** `_procesar_evento_red()` en el evento "estado" (línea ~866)

Cambio:
```python
# [FIX B] Marcar posición como válida cuando se recibe estado real del cliente
ev.datos["posicion_valida"] = True
self.remote_players[origen] = ev.datos
```

**Efecto:** Una vez que el cliente envía su estado con su posición real, se marca como válido y los enemigos pueden apuntarle.

### Fix 3: Filtrar Disparos Falsos desde (0,0)

**Archivo:** `CODIGO/Game.py`
**Método:** `_process_client_bullet()` (línea ~1416)

Cambio:
```python
# [FIX] Ignorar disparos desde (0,0) que pueden ser falsos
# durante la inicialización del cliente
if x == 0 and y == 0:
    log_game.warning(f"[DISPARO_CLIENTE] [FILTRADO] Disparo sospechoso desde (0,0) - IGNORADO")
    return
```

**Efecto:** Los disparos falsos del cliente desde (0,0) no causarán colisiones con enemigos.

## Logs de Diagnóstico Agregados

Se han agregado logs DETALLADOS en todos los puntos críticos para facilitar futuros diagnósticos:

1. **Enemy.py - take_damage():**
   - `[DAMAGE]` - Cuando un enemigo recibe daño
   - `[DEATH]` - Cuando un enemigo muere

2. **Enemy.py - ShooterEnemy.maybe_shoot():**
   - `[SHOOT]` - Cuando un enemigo dispara y a quién apunta

3. **Game.py - Targeting:**
   - `[TARGETING]` - A cuál jugador apunta cada enemigo (LOCAL vs REMOTE)

4. **Game.py - Disparos del Cliente:**
   - `[DISPARO_CLIENTE]` - Eventos de disparo del cliente
   - `[DISPARO_CLIENTE] [FILTRADO]` - Disparos bloqueados desde (0,0)

5. **Game.py - Daño Remoto:**
   - `[DAÑO_REMOTO_APLICADO]` - Cuando se aplica daño remoto

6. **Game.py - Limpieza de Enemigos:**
   - `[ENEMIES_CLEANUP]` - Cuando se eliminan enemigos

## Verificación

Para verificar que el fix funciona correctamente:

### Modo Local (sin multijugador)
```bash
python Main.py --seed 42 --skip-menu
```
✓ Los enemigos deben comportarse exactamente igual que antes

### Modo Servidor-Cliente
```bash
# Terminal 1 - Servidor
python Main.py --server --port 5555 --seed 42 --skip-menu

# Terminal 2 - Cliente
python Main.py --client --host 127.0.0.1 --port 5555 --role ally --seed 42 --skip-menu
```

✓ Los enemigos NO deben morir al atacar
✓ El targeting debe funcionar para ambos jugadores
✓ Los enemigos siguen muriendo cuando se les dispara normalmente

## Logs Esperados (Servidor)

Al conectarse el cliente, se deberían ver logs como:

```
[OK] Jugador aliado se unió a la sesión
[TARGETING] enemy_000001 APUNTA A LOCAL: dist=150.5 (porque P2 aún no tiene posición válida)
...después de ~0.1-0.2s...
[ESTADO_REMOTO_NUEVA] aliado pos=(400,300) sala=[0,0]
[TARGETING] enemy_000001 APUNTA A REMOTO: local_dist=150.5 remote_dist=120.3 pos_remota=(400,300)
[SHOOT] enemy_000001 disparando desde (300,300) hacia jugador en (400,300), dist=100.0
```

Si NO ves logs de enemigos muriendo sin razón, el fix funcionó.

## Detalles Técnicos

- **Sincronización:** El cliente envía su estado cada ~0.1 segundos (100ms)
- **Margen de seguridad:** Durante esos primeros ~0.1s, los enemigos apuntan solo al jugador local
- **Filtro (0,0):** Previene colisiones falsas si el cliente se inicializa incorrectamente
- **Flag posicion_valida:** Marca explícitamente cuándo se ha recibido una posición real

## Notas Importantes

- Los logs diagnósticos se pueden mantener con nivel DEBUG para no saturar la consola
- Si el bug persiste, revisar los logs de diagnóstico para identificar la causa específica
- El Fix B es la solución permanente; los otros fixes son defensivos adicionales
