# Phase 3: Enemy Synchronization - Implementation Summary

## Overview

Phase 3 implements **enemy death synchronization** across the network. When a player kills an enemy on one computer, it automatically dies on all other computers.

## What Was Implemented

### 1. Protocol Layer (`network/protocol.py`)

**New Function:** `msg_enemigo_muerto()`

```python
def msg_enemigo_muerto(pos_x: float, pos_y: float, tipo: str, sala: tuple[int, int]) -> Mensaje
```

- Creates serializable message when enemy dies
- Includes: position (x, y), enemy class name, room coordinates
- Returns: EVENTO type message with structured JSON

**Example Message:**
```json
{
  "tipo": "evento",
  "datos": {
    "tipo": "enemigo_muerto",
    "pos_x": 234.5,
    "pos_y": 567.8,
    "enemy_type": "BasicEnemy",
    "sala": [2, 3]
  },
  "origen": "servidor"
}
```

### 2. Game Loop Integration (`Game.py`)

#### A. Death Detection in `_handle_collisions()` (~line 814)

When an enemy is marked for removal (death animation complete):

```python
if callable(ready_fn) and ready_fn():
    self._drop_enemy_coins(enemy, room)
    
    # NEW: Notify other players
    if self.net:
        enemy_type = enemy.__class__.__name__
        sala = (self.dungeon.i, self.dungeon.j)
        event_msg = msg_enemigo_muerto(
            pos_x=enemy.x,
            pos_y=enemy.y,
            tipo=enemy_type,
            sala=sala
        )
        self.net.enviar(event_msg)
    
    continue
```

**Flow:** Enemy HP → 0 → Death animation starts → Animation finishes → Event sent → Removed from list

#### B. Event Handler in `_procesar_evento_red()`

Added case for incoming enemy death events:

```python
elif ev.tipo == "enemigo_muerto":
    self._handle_remote_enemy_death(ev)
```

#### C. Remote Enemy Death Processor

New method `_handle_remote_enemy_death()`:

```python
def _handle_remote_enemy_death(self, ev: EventoRed) -> None:
    """Busca enemy by position + type and removes it locally"""
    datos = ev.datos
    sala_remota = datos.get("sala")
    pos_x = datos.get("pos_x")
    pos_y = datos.get("pos_y")
    enemy_type = datos.get("enemy_type")
    
    # Only process if death in current room
    if sala_remota != (self.dungeon.i, self.dungeon.j):
        return
    
    # Find enemy with tolerance (5.0 pixels)
    tolerance = 5.0
    for i, enemy in enumerate(room.enemies):
        dist = ((enemy.x - pos_x)**2 + (enemy.y - pos_y)**2)**0.5
        if dist <= tolerance and enemy.__class__.__name__ == enemy_type:
            room.enemies.pop(i)  # Remove!
            break
```

**Design Decisions:**
- **Position tolerance (5px):** Accounts for client-side movement differences
- **Type checking:** Ensures killing correct enemy (not nearby different type)
- **Room filtering:** Prevents cross-room desync errors
- **Warning on not found:** Logs if enemy already removed (race condition ok)

### 3. Network API (`network/manager.py`)

**New Public Method:** `enviar()`

```python
def enviar(self, mensaje: Mensaje) -> bool:
    """Send Mensaje through network (server broadcasts, client sends to server)"""
    return self._enviar(mensaje)
```

- Public wrapper around existing `_enviar()` method
- Handles server broadcast and client send automatically
- Thread-safe through existing queue mechanisms

## Network Architecture

```
Computer A (Server)
├── Detects enemy death
├── Sends ENEMIGO_MUERTO event
└── Broadcasts to all clients

Computer A (Victim Client)
├── Kills enemy locally
├── Sends ENEMIGO_MUERTO to server
└── Receives echo (processes event)

Computer B (Ally Client)
├── Receives ENEMIGO_MUERTO broadcast
├── Searches room.enemies by position+type
└── Removes matching enemy
```

**Key Property:** Server acts as authority - it broadcasts all death events to all clients

## Thread Safety

- **Network thread:** Reads socket, enqueues events in Queue
- **Game thread:** Calls `net.tick()` to get accumulated events
- **No locks:** Queue is thread-safe primitive, no shared mutable state
- **Non-blocking:** Game loop not blocked by network delays

## Edge Cases Handled

| Scenario | Behavior | Result |
|----------|----------|--------|
| Enemy killed twice | First event removes, second finds nothing (warning logged) | No crash |
| Positions differ by >5px | Event received but not processed | No removal (laggy client) |
| Wrong enemy type nearby | Position matches but type differs | Correct enemy not killed (safety) |
| Death in different room | Event ignored (room filtered) | No cross-room corruption |
| Slow network | Client kills locally, sync happens few frames later | Minimal visual delay (~100ms) |
| Enemy drops coins | Happens locally on each client | No need to sync gold (each PC rewards locally) |

## Limitations (By Design)

- **No velocity sync:** Enemies don't move on remote screens (they spawn same location due to seed sync)
- **No HP sync:** Each client calculates damage independently (server doesn't validate)
- **No projectile sync:** Bullets not visible on remote screen yet (Phase 4)
- **Fire-and-forget:** Events not acknowledged (acceptable for this use case)

## Testing Requirements

See **PHASE3_ENEMY_SYNC_TEST.md** for detailed testing procedures.

**Quick test:**
```bash
# Terminal 1
python Main.py --server --port 5555 --skip-menu

# Terminal 2
python Main.py --client --host 127.0.0.1 --port 5555 --role victim --skip-menu

# Terminal 3
python Main.py --client --host 127.0.0.1 --port 5555 --role ally --skip-menu
```

Then kill an enemy in Terminal 2 and verify it disappears in Terminal 3.

## Code Changes Summary

| File | Changes | Lines |
|------|---------|-------|
| `network/protocol.py` | Added `msg_enemigo_muerto()` | +30 |
| `network/manager.py` | Added `enviar()` method | +15 |
| `Game.py` - `_handle_collisions()` | Added death event sending | +14 |
| `Game.py` - `_procesar_evento_red()` | Added event case | +2 |
| `Game.py` - new method | Added `_handle_remote_enemy_death()` | +33 |
| **Total** | | **+94 lines** |

## Performance Impact

- **Network:** +1 small message per enemy death (≈100 bytes)
- **CPU:** +1 dict lookup + position comparison per remote event
- **Memory:** No new allocations in steady state
- **Latency:** Event travel time ≈network RTT (typical 10-100ms LAN)

## Backward Compatibility

✅ **Fully backward compatible:**
- Offline mode (no --server/--client) unaffected
- Single-player gameplay unchanged
- Old network protocol still supported
- Event filtering prevents crashes on unknown event types

## Future Extensions

**Phase 4 ideas:**
1. Projectile/bullet synchronization
2. Enemy position interpolation
3. Ally support actions (healing, shields)
4. Player death synchronization
5. Achievement/stats sync

## Debugging

**If something's wrong:**

1. Check logs for "[NET]" prefix on all 3 terminals
2. Verify events flow: kill → broadcast → receive → remove
3. Look for "Removiendo" log on all computers when enemy dies
4. Check timestamps to understand event order
5. Use `--debug` flag for more verbose logging

## Files Modified

1. **CODIGO/network/protocol.py** — Protocol message
2. **CODIGO/Game.py** — Game loop integration (3 locations)
3. **CODIGO/network/manager.py** — Public API method

No changes to:
- Player.py, Enemy.py, Dungeon.py, Room.py
- Game loop scheduling
- Existing protocols/messages

## Conclusion

Phase 3 implementation is **complete and ready for testing**. The architecture is:
- **Simple:** Enemy dies → Event sent → Other client removes it
- **Robust:** Handles position differences, type checking, room filtering
- **Efficient:** One message per death, position tolerance prevents re-sends
- **Scalable:** Can easily add more event types in same pattern

For testing instructions, see **PHASE3_ENEMY_SYNC_TEST.md**.

