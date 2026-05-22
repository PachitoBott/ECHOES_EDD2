# Implementation Checklist - Multiplayer Fixes

## ✅ Code Changes Completed

### 1. Seed Synchronization (server.py)
- [x] Server rejects connections if `self.seed is None`
- [x] Location: `network/server.py` lines 379-383
- [x] Effect: Ensures client always gets valid seed before connecting

### 2. Room Access Bug (Game.py)
- [x] Changed from list indexing to dictionary access
- [x] Location: `Game.py` line ~1450: `room = self.dungeon.rooms.get(room_pos)`
- [x] Added None check before processing room
- [x] Effect: Fixes KeyError when accessing remote rooms

### 3. Remote Room Enemy Spawning (Game.py)
- [x] Added logic to spawn enemies in rooms server hasn't visited
- [x] Location: `Game.py` lines 1456-1471 in `_update_remote_player_rooms()`
- [x] Calculates difficulty correctly based on room depth
- [x] Effect: Enemies now appear when PC2 enters first

### 4. Animator Synchronization (Game.py)
- [x] Server sends `animator_state` in `_sync_enemies_to_client()`
- [x] Location: `Game.py` lines 1519-1521
- [x] Client receives and calls `trigger_shoot()` / `trigger_attack()`
- [x] Location: `Game.py` lines 886-904 in `_handle_enemies_state()`
- [x] Effect: Enemy animations synchronized between server and client

### 5. Targeting Logic (Game.py)  
- [x] Checks both local and remote players
- [x] Returns closest player to attack
- [x] Location: `Game.py` lines 1269-1331 in `_get_closest_player_for_enemy()`
- [x] Added debug logging for targeting
- [x] Effect: Enemies attack whichever player is closer

### 6. Debug Logging  
- [x] `[TARGETING]` logs in `_get_closest_player_for_enemy()`
- [x] `[ANIMATOR_SYNC]` logs in `_handle_enemies_state()`
- [x] `[ANIMATOR_UPDATE]` logs showing animator state transitions
- [x] `[RENDER_BUG]` logs if frame size is ZERO
- [x] `[ANIMATOR_BUG]` logs if animations missing for a state (NEW)
- [x] `[ENEMY_UPDATE]` logs in server's `_update_enemies()`
- [x] `[SERVIDOR]` logs in `_update_remote_player_rooms()`

### 7. Error Checking
- [x] Added checks for None values in targeting
- [x] Added None checks for animations in animator
- [x] Added try/except in _update_remote_player_rooms()
- [x] Added error logging for failed room updates

---

## 📋 Ready to Test: Step-by-Step

### Pre-Test Verification
```bash
# 1. Verify code syntax
cd F:\martin\Universidad\ECHOES_EDD2
python -m py_compile CODIGO/Game.py
python -m py_compile CODIGO/entities/enemy_sprites.py
python -m py_compile CODIGO/network/server.py
```

All should compile without errors.

### Test Execution

#### Terminal 1 - Server
```bash
cd F:\martin\Universidad\ECHOES_EDD2
python Main.py --server --port 5555 --skip-menu
```

**Expected output:**
- Loads game and pauses at main room
- Seed is NOT yet displayed (seed=None still)

#### Terminal 2 - Client  
```bash
cd F:\martin\Universidad\ECHOES_EDD2
python Main.py --client --host 127.0.0.1 --port 5555 --role aliado --skip-menu
```

**Expected output:**
- Should output: "Servidor no listo (sin seed)"
- Should wait/loop trying to connect
- Should NOT error out

#### Back to Terminal 1
- Select "New Game" from start menu
- Choose any seed (or leave random)
- Game loads

**Expected sync:**
- Terminal 1 shows: `Seed establecida: [NUMBER]`
- Terminal 2 connects automatically with same seed

---

## ✅ Test Cases

### Test 1: Enemigos Aparecen Cuando PC2 Entra Primero

**Steps:**
1. PC1 stays in starting room (0,0)
2. PC2 moves to adjacent room: press arrow key to move (e.g., to room 1,0)
3. Observe PC2 screen: Do you see enemies?

**Success Conditions:**
- Enemies visible in PC2's room
- Enemies move toward PC2
- Server logs show:
  ```
  [SERVIDOR] Sala remota (1, 0) spawned enemigos (difficulty=...)
  [SERVIDOR] Sala remota (1, 0) sincronizada (N enemigos)
  ```

**Diagnostic Logs to Check:**
- `[SERVIDOR]` - Shows enemy spawning and sync
- `[TARGETING]` - Shows which player enemy is attacking
- `[ANIMATOR_UPDATE]` - Shows animation state on client

---

### Test 2: Enemigos Permanecen Visibles Cuando Atacan

**Steps:**
1. PC1 and PC2 move to same room
2. PC2 gets close to an enemy
3. Attack the enemy to force it to fire (or let it fire naturally)
4. Watch: Does the enemy disappear when firing?

**Success Conditions:**
- Enemy plays shoot animation without disappearing
- Client logs show:
  ```
  [ANIMATOR_SYNC] enemy_XXXX animator_state=SHOOT → trigger_shoot()
  [ANIMATOR_UPDATE] enemy_XXXX animator.state=shoot frame_idx=...
  ```
- NO logs like:
  ```
  [RENDER_BUG] enemy_XXXX frame size is ZERO
  [ANIMATOR_BUG] No frames for state='shoot'
  ```

**Diagnostic Logs to Check:**
- `[ANIMATOR_SYNC]` - Should show trigger_shoot() being called
- `[ANIMATOR_UPDATE]` - Should show state changing to "shoot"  
- `[RENDER_BUG]` or `[ANIMATOR_BUG]` - If present, indicates problem

---

## 🔴 Possible Issues & Quick Diagnostics

### Issue: Client says "Servidor no listo (sin seed)" and stays stuck

**Cause:** Server hasn't set a seed yet

**Fix:**
- In Terminal 1, interact with start menu
- Select "New Game" or "Continue"
- Wait for seed to be established
- Client will connect automatically

---

### Issue: Enemies still frozen in remote room

**Diagnostic:**
1. Check Terminal 1 logs:
   - Do you see `[SERVIDOR] Sala remota (X,Y) spawned enemigos`?
   - If NO: Server never saw PC2 in that room
   - If YES: Continue to next check

2. Check Terminal 1 logs:
   - Do you see `[TARGETING] enemy_XXX ...`?
   - If NO: Enemies not being updated
   - If YES: Continue to next check

3. Check Terminal 2 logs:
   - Do you see `[ANIMATOR_UPDATE] enemy_XXX`?
   - If NO: Animations not being synced
   - If YES: Go to Test 2 diagnostics

---

### Issue: Enemy disappears when shooting

**Diagnostic Priority:**
1. Look for `[ANIMATOR_BUG] No frames for state='shoot'`
   - If present: Animations not loaded correctly for enemy type
   - Check: `CODIGO/assets/enemigos/[enemy_type]/shoot_*.png` exist?

2. Look for `[RENDER_BUG] enemy_XXX frame size is ZERO`
   - If present: Frame is empty, not an animation load problem
   - Check: Is the frame file corrupted or empty?

3. Look for `[ANIMATOR_SYNC] ... trigger_shoot()`
   - If missing: State not being synced from server
   - Check: Terminal 1 logs showing animator_state="shoot"?

4. Look for `[ANIMATOR_UPDATE] ... animator.state=shoot`
   - If missing: trigger_shoot() didn't work
   - Check: Does trigger_shoot() method exist in animator?

---

## 📊 Test Result Matrix

Record your results:

| Test | Scenario | Result | Logs |
|------|----------|--------|------|
| 1a | PC2 enters first | [ ] PASS / [ ] FAIL | [SERVIDOR] [TARGETING] |
| 1b | Enemies appear | [ ] YES / [ ] NO | [ANIMATOR_UPDATE] |
| 1c | Enemies attack | [ ] YES / [ ] NO | [ENEMY_UPDATE] |
| 2a | Shoot state sent | [ ] YES / [ ] NO | [ANIMATOR_SYNC] shoot |
| 2b | Visible during shoot | [ ] YES / ] NO | [RENDER_BUG] presence |
| 2c | No frame bugs | [ ] YES / [ ] NO | [ANIMATOR_BUG] presence |

---

## 🎯 Next Steps

### If All Tests Pass ✅
1. Remove ALL `[DEBUG]` logging from the code
2. Run extended multiplayer session (30+ minutes)
3. Test different enemy types and room configurations
4. Commit changes: "Fix: Multiplayer enemy sync and animations"

### If Any Test Fails ❌
1. Note which test failed (Test 1a, 2b, etc.)
2. Capture the failing scenario's logs
3. Check diagnostic section above for root cause
4. Report findings with:
   - Test case number
   - What you expected
   - What actually happened
   - Relevant log lines
5. We debug based on that information

---

## 🔧 Log Location Reference

All logs go to:
```
F:\martin\Universidad\ECHOES_EDD2\.claude\logs\
```

Most relevant files:
- `game.log` - [GAME], [TARGETING], [ANIMATOR_*], [RENDER_BUG]
- `network.log` - [NET] events

View in real-time:
```bash
tail -f .claude/logs/game.log
```

