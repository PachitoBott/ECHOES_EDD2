# Sincronización de Animator de Enemigos - Cambios Implementados

## Problema Identificado

Los enemigos desaparecían cuando disparaban en PC2 (cliente) porque:
1. El animator del enemigo en el servidor entraba en estado "shoot" (oneshot) cuando disparaba
2. El cliente no sabía sobre este cambio de estado
3. El cliente estaba reseteando el animator con `set_base_state()` cada frame, interrumpiendo la animación de disparo
4. Esto causaba que frames incorrectos se renderizaran o que el sprite desapareciera

## Solución Implementada

### 1. **Sincronización de Animator State en Protocol**
   - **Archivo**: `CODIGO/network/protocol.py`
   - **Cambio**: Documentación actualizada de `msg_enemies_state()` para incluir:
     - `animator_state`: estado actual del animator ("idle", "run", "shoot", "attack")
     - `facing_right`: dirección del sprite (bool)

### 2. **Server: Enviar Animator State a Cliente**
   - **Archivo**: `CODIGO/Game.py` - método `_sync_enemies_to_client()`
   - **Cambios**:
     ```python
     # Obtener estado del animator
     animator_state = "idle"
     if hasattr(enemy, "animator"):
         animator_state = getattr(enemy.animator, "state", "idle")

     enemies_list.append({
         # ... campos existentes ...
         "animator_state": animator_state,
         "facing_right": getattr(enemy, "_facing_right", True),
     })
     ```
   - **Beneficio**: El servidor ahora envia el estado exacto del animator al cliente

### 3. **Client: Recibir y Aplicar Animator State**
   - **Archivo**: `CODIGO/Game.py` - método `_handle_enemies_state()`
   - **Cambios principales**:
     ```python
     # Sincronizar animator_state desde el servidor
     animator_state = server_data.get("animator_state", "idle")
     if hasattr(enemy, "animator"):
         if animator_state == "shoot":
             if hasattr(enemy.animator, "trigger_shoot"):
                 enemy.animator.trigger_shoot()
         elif animator_state == "attack":
             if hasattr(enemy.animator, "trigger_attack"):
                 enemy.animator.trigger_attack()
         else:
             # Para otros estados, cambiar el base_state directamente
             if hasattr(enemy.animator, "set_base_state"):
                 enemy.animator.set_base_state(animator_state)

     # Sincronizar dirección del sprite
     facing_right = server_data.get("facing_right", True)
     enemy._facing_right = facing_right

     # Actualizar el animator para avanzar frames
     if hasattr(enemy, "animator"):
         enemy.animator.update(getattr(self, "dt", 0.016))
     ```
   - **Beneficio**: El cliente ahora aplica exactamente el estado que el servidor envía

### 4. **Remover Interferencia en Cliente**
   - **Archivo**: `CODIGO/Game.py` - método `_update_enemies()` (rama cliente)
   - **Cambio**: Removida la llamada a `enemy._update_animation(dt)` en el cliente
   - **Razón**: Esa llamada estaba reseteando el animator cada frame, interrumpiendo animaciones oneshot
   - **Nuevo flujo**: El animator ahora SOLO se actualiza cuando llega `enemies_state` del servidor

### 5. **Agregar Logging para Debug**
   - **Archivo**: `CODIGO/Game.py` - método `_update_enemies()` (rama cliente)
   - **Cambios**:
     ```python
     if not self.player:
         log_game.debug(f"[CLIENTE] WARNING: self.player es None o no existe")
     else:
         # ... lógica de detección ...
         if dist <= detect_rad and has_los:
             log_game.debug(f"[CLIENTE] Enemy {enemy.enemy_id} detectó jugador: dist={dist:.1f}, detect_rad={detect_rad}, los={has_los}")
     ```
   - **Beneficio**: Ayuda a diagnosticar por qué enemigos no persiguen al jugador

### 6. **Guardar dt para Sincronización**
   - **Archivo**: `CODIGO/Game.py` - método `_update()`
   - **Cambio**: Agregar `self.dt = dt` al inicio de `_update()`
   - **Razón**: Necesario para actualizar el animator en `_handle_enemies_state()`

## Flujo de Sincronización Corregido

### Antes (Problema)
```
SERVIDOR (PC1)              CLIENTE (PC2)
┌──────────────────────────────────────┐
│ Enemy dispara               │
│ animator.state = "shoot"    │
│ Envía animator_state="shoot"│
│     ────────→  Recibe      │
│                animator_state="shoot"
│                Pero luego:
│                _update_animation()
│                set_base_state("idle")
│                Animator = "idle"      ✗ PROBLEMA
│                
│                Renderiza frame idle
│                Sprite desaparece
└──────────────────────────────────────┘
```

### Después (Solución)
```
SERVIDOR (PC1)              CLIENTE (PC2)
┌──────────────────────────────────────┐
│ Enemy dispara               │
│ animator.trigger_shoot()    │
│ animator.state = "shoot"    │
│ animator.oneshot = "shoot"  │
│ Envía animator_state="shoot"│
│     ────────→  Recibe      │
│                animator_state="shoot"
│                trigger_shoot()
│                animator.state = "shoot"
│                animator.oneshot = "shoot"
│                
│                Renderiza frame shoot ✓ CORRECTO
│                La animación oneshot
│                se completa naturalmente
│                
│                Después de frames:
│                Vuelve a base_state
└──────────────────────────────────────┘
```

## Problema Secundario: Enemigos No Detectan Jugador en PC2

Se agregó logging en `_update_enemies()` para debuggear esto:
- Verifica si `self.player` existe
- Log distance calculation
- Log FSM state changes

**Para activar logs**: En el cliente, buscar líneas con `[CLIENTE]` en la consola

## Testing Checklist

- [ ] **Server dispara**: PC1 dispara y mata enemigos - deben desaparecer en ambos PCs sin flashear
- [ ] **Client dispara**: PC2 dispara y mata enemigos - deben desaparecer en ambos PCs sin flashear
- [ ] **Animación de disparo**: Ver que enemigos muestran animación correcta cuando disparan (no desaparecen)
- [ ] **Dirección correcta**: Verificar que `facing_right` se sincroniza - sprites miran en dirección correcta
- [ ] **PC2 primero**: Cuando PC2 entra primero, enemigos deben detectar y perseguir (revisar logs [CLIENTE])
- [ ] **Sin crashes**: Conectar/desconectar sin errores

## Notas Técnicas

- **Frecuencia de sync**: 20 Hz (cada 50ms) - no cambió
- **Animator synchronization**: Ahora es la parte crítica - oneshot states se respetan
- **dt para animator**: Necesario para que animator.update() avance correctamente
- **Logging en cliente**: Muy útil para debuggear detección de jugador

## Si algo sigue fallando

1. **Enemigos aún desaparecen**: Revisar logs [CLIENTE] para ver si animator_state llega correctamente
2. **Enemigos no persiguen**: Revisar log "Enemy X detectó jugador" - si no aparece, el problema es la detección de LOS o distancia
3. **Dirección incorrecta**: Revisar que facing_right se sincroniza en _handle_enemies_state()

## Rollback si es necesario
```bash
git checkout HEAD -- CODIGO/Game.py CODIGO/network/protocol.py
```
