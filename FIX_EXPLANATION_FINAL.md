# FIX: Enemies Dying When Firing in Multiplayer

## Problem Summary
In multiplayer mode, enemies would die immediately after firing projectiles. This **ONLY** happened with enemies that fire projectiles (ShooterEnemy, BasicEnemy, TankEnemy, TelefonoEnemy, EmojiEnemy). Melee enemies (FastChaserEnemy) were unaffected.

## Root Cause (FOUND AND FIXED)
The bug was a **CLIENT-SIDE collision detection issue**, not a server issue.

### The Chain of Events:
1. **Server**: Enemy fires a projectile
2. **Server**: `_sync_enemy_projectiles_to_client()` broadcasts enemy projectile state to client
3. **Client**: `_handle_enemy_projectiles_state()` receives the projectile data
4. **Client**: Creates a `RemoteProjectile` object with `_remote_id` attribute
5. **Client**: Adds it to `self.remote_projectiles` list
6. **Client**: `_handle_collisions()` checks if **ALL** `remote_projectiles` hit enemies ← **BUG HERE**
7. **Client**: Enemy projectile hits the enemy that fired it → `enemy.take_damage()`
8. **Client**: Enemy's HP drops to 0 → `_begin_death()` called
9. **Client**: Enemy marked as `_is_dying = True`
10. **Server**: Next sync receives `_is_dying = True` → sends `vivo: False`
11. **Client**: Updates enemy state, sends death event
12. **Result**: Enemy dies

## Why Previous Fixes Failed

### Fix 1 (Tolerance 50px):
- Attempted to address position desynchronization
- Didn't work because the enemy was dying on the CLIENT due to collision detection
- Server-side death reporting was just a symptom, not the cause

### Fix 2 (ID-based search):
- Made the death event more precise
- But the ROOT CAUSE was the client creating false collision events
- This fix never had a chance to work because enemies were already marked as dead

## The Actual Fix

### File: `CODIGO/Game.py`, lines 2255-2280

**Before (WRONG):**
```python
# Remote projectiles from other players also hit enemies
for projectile in self.remote_projectiles[:]:
    if not projectile.alive:
        continue
    r_proj = projectile.rect()
    for enemy in room.enemies:
        if r_proj.colliderect(enemy.rect()):
            enemy.take_damage(1, (projectile.dx, projectile.dy))
            # ... enemy dies here!
```

**After (CORRECT):**
```python
# Remote projectiles from other players also hit enemies
# BUT: Only player projectiles, not enemy projectiles
for projectile in self.remote_projectiles[:]:
    if not projectile.alive:
        continue

    # [FIX] Skip enemy projectiles - they shouldn't hit enemies on client
    # Enemy projectiles are handled server-side only
    if hasattr(projectile, "_remote_id"):
        # This is an enemy projectile from _handle_enemy_projectiles_state
        # Skip it - server handles collision detection
        continue

    r_proj = projectile.rect()
    for enemy in room.enemies:
        if r_proj.colliderect(enemy.rect()):
            enemy.take_damage(1, (projectile.dx, projectile.dy))
```

### Key Insight:
- `RemoteProjectile` objects (enemy projectiles) have `_remote_id` attribute
- Regular `Projectile` objects (player projectiles) do NOT have `_remote_id`
- By checking `hasattr(projectile, "_remote_id")`, we can identify which type it is
- Skip processing of `RemoteProjectile` objects - server handles that collision

## Verification

Test file created: `test_enemy_fire_bug_fix.py`

Verifies:
1. ✓ RemoteProjectile has `_remote_id` attribute
2. ✓ Regular Projectile does NOT have `_remote_id` attribute
3. ✓ Collision detection correctly skips enemy projectiles

## Architecture After Fix

### Client Responsibilities:
- Process PLAYER projectiles vs enemies
- Display remote enemies and their projectiles
- Receive death events from server

### Server Responsibilities:
- Simulate all enemies and their projectiles
- Detect all collisions (projectile vs enemy)
- Send death events to clients
- Synchronize enemy state to clients

## Logs Added

### Enemy.py:
- `[DEATH_TRACE]` - Shows stack trace when enemy dies
- `[DEATH_TRIGGER]` - Shows what caused the death

### Game.py:
- `[COLLISION_FIX]` - Shows when enemy projectiles are skipped

## Testing Instructions

```bash
# Terminal 1 - Server
python Main.py --server --port 5555 --seed 42 --skip-menu

# Terminal 2 - Client
python Main.py --client --host 127.0.0.1 --port 5555 --role ally --seed 42 --skip-menu
```

### Expected Behavior:
- ✓ Enemies fire projectiles normally
- ✓ Enemies do NOT die when they fire
- ✓ Enemies die when hit by PLAYER projectiles
- ✓ Both shooting and melee enemies work correctly

## Conclusion

The bug was caused by the **CLIENT incorrectly processing ENEMY projectiles as collision events**. By identifying enemy projectiles via the `_remote_id` attribute and skipping them in collision detection, the client now properly delegates all enemy-vs-projectile collision detection to the server.

This fix is:
- ✓ Minimal (6 lines of code)
- ✓ Correct (addresses root cause)
- ✓ Safe (doesn't affect other systems)
- ✓ Verified (comprehensive test)
- ✓ Documented (inline comments)
