# Phase 3: Enemy Synchronization Testing Guide

## Changes Implemented

✅ **1. Protocol Message** (`CODIGO/network/protocol.py`)
   - Added `msg_enemigo_muerto()` function to create enemy death events
   - Includes: position (x, y), enemy type, and room location

✅ **2. Enemy Death Detection** (`CODIGO/Game.py` - `_handle_collisions()`)
   - When enemy is ready to be removed, sends `ENEMIGO_MUERTO` event
   - Event contains: position, type, and room info
   - Server broadcasts to all clients

✅ **3. Event Handling** (`CODIGO/Game.py`)
   - Added `_procesar_evento_red()` case for "enemigo_muerto"
   - Calls new `_handle_remote_enemy_death()` method
   - Searches for matching enemy by position + type
   - Removes enemy from room if found

✅ **4. Network Communication** (`CODIGO/network/manager.py`)
   - Added public `enviar()` method to NetworkManager
   - Wraps existing `_enviar()` for clean API
   - Handles server broadcast and client send

## Testing Procedure

### Setup Requirements

- Two computers on same network (or localhost for initial testing)
- Python environment with Pygame installed on both
- Same codebase on both machines

### Test 1: Basic 3-Terminal Test (Localhost)

**Purpose:** Verify enemy sync works on same machine

```bash
# Terminal 1 (Server)
cd CODIGO
python Main.py --server --port 5555 --skip-menu

# Terminal 2 (Client - Victim)
cd CODIGO
python Main.py --client --host 127.0.0.1 --port 5555 --role victim --skip-menu

# Terminal 3 (Client - Ally)
cd CODIGO
python Main.py --client --host 127.0.0.1 --port 5555 --role ally --skip-menu
```

**Expected Logs:**

Terminal 1 (Server):
```
[TIMESTAMP] INFO: Servidor escuchando en 0.0.0.0:5555
[TIMESTAMP] INFO: Nueva conexion desde ('127.0.0.1', XXXXX)
[TIMESTAMP] INFO: Jugador conectado: rol=victima
[TIMESTAMP] INFO: Nueva conexion desde ('127.0.0.1', XXXXX)
[TIMESTAMP] INFO: Jugador conectado: rol=aliado
```

Terminal 2 (Victim):
```
[TIMESTAMP] INFO: Conectado como victima | seed=XXXXX | servidor=127.0.0.1:5555
[TIMESTAMP] INFO: [NET] Evento: jugador_unido desde servidor
[TIMESTAMP] INFO: Jugador aliado se unió a la sesión
```

Terminal 3 (Ally):
```
[TIMESTAMP] INFO: Conectado como aliado | seed=XXXXX | servidor=127.0.0.1:5555
[TIMESTAMP] INFO: [NET] Evento: jugador_unido desde servidor
[TIMESTAMP] INFO: Jugador victima se unió a la sesión
```

### Test 2: Enemy Kill Synchronization

**Purpose:** Verify enemies die on all computers when killed

**Steps:**

1. Keep all 3 terminals running from Test 1
2. In Terminal 2 (Victim): Move player to find an enemy and kill it
3. Shoot/attack enemy until it dies

**Expected Logs:**

Terminal 2 (Victim) - Where kill happens:
```
[TIMESTAMP] INFO: Removiendo BasicEnemy en posición (234.5, 567.8)
[TIMESTAMP] INFO: [NET] Evento: enemigo_muerto desde servidor
```

Terminal 1 (Server) - Receives and broadcasts:
```
[TIMESTAMP] INFO: [NET] Evento: enemigo_muerto desde victima
```

Terminal 3 (Ally) - Receives removal:
```
[TIMESTAMP] INFO: [NET] Evento: enemigo_muerto desde servidor
[TIMESTAMP] INFO: Removiendo BasicEnemy en posición (234.5, 567.8)
```

**Visual Verification:**
- Enemy dies on Terminal 2 (your character kills it)
- Enemy disappears on Terminal 3 a moment later (synchronized)
- No crash or errors in any terminal

### Test 3: Multiple Simultaneous Kills

**Purpose:** Verify multiple kills from different players sync correctly

**Steps:**

1. Keep 3 terminals running
2. In Terminal 2: Kill one enemy
3. In Terminal 3: Try to move ally character and observe (visual sync test, kills not relevant for ally)
4. Back in Terminal 2: Kill another enemy

**Expected:**
- Each kill in Terminal 2 produces "enemigo_muerto" event
- Terminal 1 receives and broadcasts
- Terminal 3 sees enemies disappear in real-time
- No crashes, clean shutdown possible with ESC

### Test 4: Network Isolation Test

**Purpose:** Verify offline mode still works

```bash
cd CODIGO
python Main.py --skip-menu
```

**Expected:**
- Game starts normally
- No network logs appear
- Gameplay identical to before
- Enemies only disappear locally (no sync)

### Test 5: Cross-Network Test (Two PCs)

**Purpose:** Full integration test on actual network

**Computer 1 (Server):**
```bash
python Main.py --server --port 5555 --skip-menu
```

**Computer 2 (Client):**
```bash
python Main.py --client --host 192.168.X.X --port 5555 --role victim --skip-menu
```

Replace `192.168.X.X` with Computer 1's actual IP address.

**Expected:**
- Same logs as Test 1 but with real network IP
- Enemies kill-sync works across network
- ~100ms latency visible in state updates (normal)

## Success Checklist

- [ ] Test 1: Localhost 3-terminal test runs without crashes
- [ ] Test 1: Server receives "jugador_unido" events for both clients
- [ ] Test 2: Killing enemy in Terminal 2 produces "enemigo_muerto" log
- [ ] Test 2: Terminal 1 receives and broadcasts the event
- [ ] Test 2: Terminal 3 logs "Removiendo [EnemyType]"
- [ ] Test 2: Enemy visually disappears on all screens simultaneously
- [ ] Test 3: Multiple kills work without race conditions
- [ ] Test 4: Offline mode works (no network logs)
- [ ] Test 5: Cross-network test works with real IP addresses
- [ ] All tests: No Python exceptions or crashes

## Debugging Tips

### Problem: "Address already in use"

**Solution:** Port 5555 is occupied. Try different port:
```bash
python Main.py --server --port 5556 --skip-menu
```

### Problem: "Connection refused"

**Solution:** Server not running or wrong IP. Check:
1. Is Terminal 1 showing "Servidor escuchando"?
2. Is IP address correct in Terminal 2?

### Problem: Enemy doesn't disappear on all screens

**Check logs for:**
- Does Terminal 1 show the event received?
- Does Terminal 3 show "Removiendo"?
- If not, enemy death event not being sent or broadcast properly

### Problem: Logs not showing

**Increase verbosity:**
```bash
python Main.py --server --port 5555 --skip-menu --debug
```

### Problem: Game freezes during kill

**Likely causes:**
- Deadlock in network thread
- Exception in event handler not being caught
- Check Terminal 1 (server) for error messages

## Next Steps After Success

Once all tests pass:

1. **Projectile Sync** — Make bullets visible on remote player's screen
2. **Full Position Tracking** — Smooth interpolation of enemy positions
3. **Ally Support** — Implement healing/shield from ally client
4. **Visual Polish** — Player nametags, damage numbers, effects

## Code Locations

| Component | File | Lines |
|-----------|------|-------|
| Protocol message | `network/protocol.py` | +30 |
| Death detection | `Game.py:_handle_collisions()` | ~814-820 |
| Event handler | `Game.py:_procesar_evento_red()` | ~545-548 |
| Death processor | `Game.py:_handle_remote_enemy_death()` | +35 |
| Network send | `network/manager.py` | +15 |

