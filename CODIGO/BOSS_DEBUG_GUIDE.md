# Boss Movement Debug Guide

## How to Test

1. Run the game
2. Use debug command: press `F1` and type `boss` to teleport to boss room
3. Watch the console output for debug messages
4. Check what messages appear

## Expected Debug Output

### When Boss is Activated (should appear once when entering boss room):
```
[BOSS] ✅ ACTIVADO
      Posición inicial: (X, Y)
      Sala rect: left=..., right=..., width=...
      Límites de movimiento: izq=..., der=..., rango=...px
      Sprite: render_w=..., render_h=...
      Parámetros: SPEED=... px/sec, MARGIN=...px
```

### Every 30 Frames During Movement:
```
[BOSS] UPDATE: x=123.4, vel=60, dt=0.0166, sala_rect=(0, 1600)
```

### When Boss Bounces at Boundaries:
```
[BOSS] ⬅️ Rebotó en límite izquierdo: x=50.0→50.0, vel→60
[BOSS] ➡️ Rebotó en límite derecho: x=1350.0→1350.0, vel→60
```

## What to Check

1. **Is "ACTIVADO" message appearing?**
   - YES → Boss is being activated correctly
   - NO → Boss is never activated (check if you're in boss room)

2. **Is "UPDATE" message appearing every second (30 frames)?**
   - YES → update() is being called
   - NO → update() is not being called (shouldn't happen)

3. **Is `x` value changing in UPDATE message?**
   - YES → Movement is working, check if visual is visible
   - NO → Movement is not happening (we need to investigate)

4. **Are bounce messages appearing?**
   - YES → Boss is hitting boundaries and reversing (good sign of movement)
   - NO → Boss is not reaching boundaries

5. **What is "rango" (movement range)?**
   - Should be hundreds of pixels (200+ ideally)
   - If too small (like 50px), boss might bounce constantly
   - If 0 or negative, there's a calculation error

## Common Issues and Solutions

### Issue: No "ACTIVADO" message
- **Cause:** Boss not being entered or activated
- **Solution:** Use `F1` → `boss` command to ensure you reach boss room

### Issue: UPDATE messages show x not changing
- **Cause:** Movement equation not working
- **Possible causes:**
  - velocidad_x is 0
  - dt is 0
  - Position is being reset somewhere
- **Solution:** Check if rango is valid and limits make sense

### Issue: Rango is negative or 0
- **Cause:** Limits are calculated wrong
- **Solution:** Check if sala_rect.width > render_w + 2*MARGIN
  - MARGIN = 50px
  - render_w = 184px  
  - Minimum room width needed: 184 + 100 = 284px
  - Boss room should be at least 20 tiles wide (640px) so this shouldn't be an issue

### Issue: Boss bounces too often
- **Cause:** rango is very small
- **Solution:** Increase boss room size or decrease MARGIN

## Console Output Location

- **Windows (PyCharm):** Bottom panel "Run" tab
- **Windows (Terminal):** Same terminal window where you ran the game
- **Scroll up** to see messages from the beginning

## Next Steps

Report what you see in the debug output and we can diagnose the exact issue!
