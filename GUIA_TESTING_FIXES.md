# Guía de Testing - Fixes para Enemigos

## Estado Actual de Fixes Implementados

### ✅ Fixes Implementados
1. **Seed Synchronization** (server.py): Servidor rechaza conexiones hasta tener seed válida
2. **Remote Room Spawning** (Game.py): Enemigos ahora se spawnean en salas donde solo está el cliente
3. **Animator Synchronization** (Game.py): Estados de ataque se sincronizan entre servidor y cliente
4. **Targeting Logic** (Game.py): Enemigos buscan tanto jugador local como remoto

### ❓ Síntomas a Verificar
1. **Symptom A**: Enemigos ignoran al cliente cuando este entra primero a una sala
2. **Symptom B**: Enemigos desaparecen cuando disparan en el cliente

---

## Protocolo de Testing

### Preparación
```bash
# Terminal 1 - Servidor (PC1)
cd F:\martin\Universidad\ECHOES_EDD2
python Main.py --server --port 5555 --skip-menu

# Terminal 2 - Cliente (PC2)
cd F:\martin\Universidad\ECHOES_EDD2
python Main.py --client --host 127.0.0.1 --port 5555 --role aliado --skip-menu
```

> **IMPORTANTE**: Ejecutar en este ORDEN exacto. El cliente debe conectarse DESPUÉS de que el servidor esté listo.

---

## Test 1: Enemigos Aparecen Cuando PC2 Entra Primero

### Paso 1: Verificar Seed Sincronizada
- En ambos terminals, debería aparecer algo como:
  ```
  Seed: 42
  ```
- Si el cliente vé "Servidor no listo (sin seed)" → el servidor aún no tiene seed (espera)

### Paso 2: Hacer que PC2 Entre a una Sala Diferente
1. **En Terminal 1 (PC1/Servidor)**: Muévete a una sala (ej: entra a puerta)
2. **En Terminal 2 (PC2/Cliente)**: Entra a una sala DIFERENTE (norte, sur, este, oeste)
   - Ejemplo: Si PC1 está en (0,0), PC2 entra a (1,0)

### Paso 3: Verificar en Logs

**Terminal 1 debería mostrar**:
```
[DEBUG] [GAME] [SERVIDOR] Sala remota (1, 0) spawned enemigos (difficulty=3)
[DEBUG] [GAME] [SERVIDOR] Sala remota (1, 0) sincronizada (3 enemigos)
[DEBUG] [GAME] [TARGETING] enemy_000001 local_dist=15.0 remote_dist=22.5 REMOTE (100.0,200.0)
```

**Terminal 2 debería mostrar**:
```
[DEBUG] [GAME] [ANIMATOR_SYNC] enemy_000001 animator_state=RUN → set_base_state()
[DEBUG] [GAME] [ANIMATOR_UPDATE] enemy_000001 animator.state=run frame_idx=2
```

### Paso 4: Verificar Visualmente
- ✅ **SUCCESS**: Ves enemigos en la sala de PC2, se mueven hacia ti
- ❌ **FAIL**: Los enemigos están quietos/congelados
- ❌ **FAIL**: No hay enemigos en la sala

**Si falla**: Revisa "Troubleshooting" abajo.

---

## Test 2: Enemigos Permanecen Visibles Cuando Atacan

### Paso 1: Asegúrate de que ambos jugadores estén en la MISMA sala
- PC1 y PC2 en la misma ubicación (ej: ambos en sala (0,0))

### Paso 2: Atacar un Enemigo
- **En Terminal 2 (Cliente)**: Colócate cerca de un enemigo y haz que ataque
  - Método: Atácalo para que entre en modo CHASE, luego espera a que dispare

### Paso 3: Verificar Logs Durante Ataque

**Terminal 1 debería mostrar**:
```
[DEBUG] [GAME] [SERVIDOR] Sala remota (0, 0) sincronizada (3 enemigos)
[DEBUG] [GAME] [TARGETING] enemy_000001 local_dist=25.0 remote_dist=20.0 REMOTE (...)
```

**Terminal 2 debería mostrar**:
```
[DEBUG] [GAME] [ANIMATOR_SYNC] enemy_000001 animator_state=SHOOT → trigger_shoot()
[DEBUG] [GAME] [ANIMATOR_UPDATE] enemy_000001 animator.state=shoot frame_idx=1
```

### Paso 4: Verificar Visualmente
- ✅ **SUCCESS**: El enemigo dispara Y permanece visible en pantalla
- ❌ **FAIL**: El enemigo desaparece cuando inicia el ataque
- ❌ **FAIL**: No ves la animación de disparo

**Si falla**: Revisa "Troubleshooting" abajo.

---

## Troubleshooting

### Problema: Enemigos siguen congelados en sala remota

**Logs a buscar**:
- ¿Aparece el mensaje `[SERVIDOR] Sala remota (X,Y) spawned enemigos`?
  - Si **SÍ**: Enemigos fueron spawneados → ver targeting
  - Si **NO**: El servidor no vio a PC2 en esa sala

**Acciones**:
1. Verifica que PC2 se conectó exitosamente (debería ver seed sincronizada)
2. Espera 1-2 segundos después de que PC2 entra a la sala
3. Revisa que PC2 realmente cambió de sala (mira en pantalla)

---

### Problema: Enemigos desaparecen cuando atacan

**Logs a buscar**:
```
[ANIMATOR_SYNC] enemy_XXX animator_state=SHOOT → trigger_shoot()
[ANIMATOR_UPDATE] enemy_XXX animator.state=shoot frame_idx=...
[RENDER_BUG] enemy_XXX frame size is ZERO at animator.state=shoot
```

**Si ves `[RENDER_BUG]`**:
- El animator está retornando un frame vacío para el estado "shoot"
- Problema en animator.frames["shoot"] o las animaciones no están cargadas correctamente

**Acciones**:
1. Verifica que los assets de disparo existen: `CODIGO/assets/enemies/Caster/shoot/`
2. Comprueba que el animator tiene frames para "shoot" cargados
3. Si no hay frames, aumentar logs en Animator para diagnosticar

---

### Problema: Cliente nunca se conecta

**Síntoma**: Terminal 2 dice "Servidor no listo (sin seed)"

**Causas posibles**:
- PC1 no ha seleccionado una seed aún
- El puerto está ocupado (cambiar a --port 5556)

**Acciones**:
1. En Terminal 1: Selecciona "New Game" y elige una seed
2. Espera a ver en el log del servidor: "Seed establecida: ..."
3. Terminal 2 debería conectarse automáticamente

---

## Próximos Pasos Después de Testing

### Si TODO pasa ✅
1. Remover TODOS los `[DEBUG]` logs
2. Cambiar a pruebas de rendimiento y multijugador real (LAN/IP)
3. Documentar los fixes para registro

### Si algo falla ❌
1. Capturar logs completos del error
2. Anotar cuál test falló exactamente
3. Proceder a debugging específico

---

## Notas Técnicas

- **Sincronización**: 50ms (20Hz) entre servidor y cliente
- **Spawning**: Happens when server sees remote player in new room
- **Animator**: Protege oneshot states automáticamente via `set_base_state()`
- **Targeting**: Busca distancia a AMBOS jugadores, ataca al más cercano

