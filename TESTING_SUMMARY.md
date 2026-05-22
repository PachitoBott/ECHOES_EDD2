# Testing Summary - Multiplayer Enemy Fixes

## ✅ Pre-Testing Verification

### Assets Status
- **blue_shooter**: idle, run, shoot, death frames ✓
- **yellow_shooter**: idle, run, shoot, death frames ✓  
- **green_chaser**: idle, run, shoot, death frames ✓
- **tank**: idle, run, shoot, death frames ✓

All animator assets are present. If enemies disappear, it's NOT asset-related.

### Code Status
- **Server seed check**: Implemented and active
- **Remote room spawning**: Implemented  
- **Animator synchronization**: Implemented with trigger_shoot() and trigger_attack()
- **Targeting logic**: Checks both local and remote players
- **Debug logging**: Active throughout the system

---

## 🎯 Quick Testing Procedure

### 1. Start Server (Terminal 1)
```bash
cd F:\martin\Universidad\ECHOES_EDD2
python Main.py --server --port 5555 --skip-menu
```

**Expected**: Waits for seed to be set (game loads to main dungeon)

### 2. Start Client (Terminal 2)  
```bash
cd F:\martin\Universidad\ECHOES_EDD2
python Main.py --client --host 127.0.0.1 --port 5555 --role aliado --skip-menu
```

**Expected**: Connects and loads same game world (same seed visible on both screens)

---

## 📋 Test Case 1: PC2 Enters First to Remote Room

### Steps
1. **PC1 (Server)**: Stay in starting room, DON'T move
2. **PC2 (Client)**: Move to an adjacent room
3. **Observe**: Do you see enemies in PC2's room?

### Expected Result
```
Terminal 1 (Server) logs:
[DEBUG] [GAME] [SERVIDOR] Sala remota (1, 0) spawned enemigos (difficulty=3)
[DEBUG] [GAME] [SERVIDOR] Sala remota (1, 0) sincronizada (3 enemigos)
[DEBUG] [GAME] [TARGETING] enemy_000001 local_dist=... remote_dist=20.5 REMOTE

Visual: Enemies appear in PC2's screen and move toward PC2
```

### ✅ Pass Condition
- Enemies appear in PC2's room
- Enemies move toward PC2
- Enemies attack PC2

### ❌ Fail Condition
- Enemies are frozen/idle in PC2's room
- Enemies don't react to PC2's presence
- No enemies appear at all

---

## 📋 Test Case 2: Enemies Remain Visible During Attack

### Steps
1. **Both PC1 and PC2**: Move to same room
2. **PC2 (Client)**: Get close to an enemy
3. **PC2 (Client)**: Attack the enemy to trigger its shoot animation
4. **Observe**: Does the enemy disappear when firing?

### Expected Result
```
Terminal 2 (Client) logs:
[DEBUG] [GAME] [ANIMATOR_SYNC] enemy_000005 animator_state=SHOOT → trigger_shoot()
[DEBUG] [GAME] [ANIMATOR_UPDATE] enemy_000005 animator.state=shoot frame_idx=0

Visual: Enemy shoots and remains visible throughout animation
```

### ✅ Pass Condition
- Enemy plays shoot animation frame by frame
- Enemy is visible for entire animation
- Projectile appears

### ❌ Fail Condition
- Enemy disappears when entering shoot state
- You see "[RENDER_BUG] enemy_XXX frame size is ZERO" in logs
- Enemy suddenly vanishes mid-attack

---

## 🔍 If Test Case 2 Fails

### Quick Diagnostic Steps

1. **Check animator frame loading**:
   - Look for errors like "[RENDER_BUG] enemy_XXX frame size is ZERO"
   - If you see this, the animator is returning an empty frame

2. **Check if trigger_shoot() is being called**:
   - Look for logs containing "trigger_shoot()" 
   - If you don't see these logs, the animator state isn't being synced

3. **Check animator state transitions**:
   - Look for "[ANIMATOR_UPDATE] ... animator.state=shoot frame_idx=..."
   - If state stays "idle" or "run", the state isn't changing

### What to Report
If test fails, capture:
```bash
Terminal 1: All [SERVIDOR] and [TARGETING] lines when enemy attacks
Terminal 2: All [ANIMATOR_SYNC] and [ANIMATOR_UPDATE] lines when enemy attacks
Terminal 2: Any [RENDER_BUG] lines
```

---

## 📊 Test Coverage Matrix

| Test | Scenario | Expected | Pass |
|------|----------|----------|------|
| 1a | PC2 enters first, enemies spawn | Enemies appear and attack | ? |
| 1b | Both in same room, enemies target | Enemies attack nearest | ? |  
| 2a | Enemy shoot state synced | See "animator_state=SHOOT" | ? |
| 2b | Enemy visible during shoot | No "[RENDER_BUG]" lines | ? |
| 2c | Projectile appears | Bullet visible on screen | ? |

---

## Next Actions After Testing

### If ALL Tests Pass ✅
1. Remove all [DEBUG] logging
2. Run full multiplayer session (30+ min)
3. Test with different enemy types and rooms
4. Clean up code and document fixes

### If Any Test Fails ❌
1. Capture the failing scenario's logs
2. Check "Diagnostics" section in this document
3. Determine root cause from logs
4. Implement targeted fix
5. Re-test

---

## Common Issues & Quick Fixes

### "Servidor no listo (sin seed)"
- **Cause**: Server hasn't set seed yet
- **Fix**: Wait for "Seed establecida:" log in Terminal 1

### Enemies frozen in remote room
- **Cause**: Maybe _update_remote_player_rooms() not called
- **Fix**: Verify server logs show "Sala remota X,Y sincronizada" every ~50ms

### Enemy disappears when shooting
- **Cause**: Animator frame is empty or animator not transitioning state
- **Fix**: Check for "[RENDER_BUG]" or missing "[ANIMATOR_SYNC]" logs

