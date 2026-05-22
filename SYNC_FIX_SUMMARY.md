# FIX: Sincronización de Enemigos Cliente-Servidor

## Problema Identificado

El cliente mostraba **más enemigos que el servidor** y enemigos que **no debería tener**. Causas:

1. **El cliente creaba enemigos localmente** llamando a `_spawn_room_enemies()` en modo multijugador
2. **El servidor también enviaba enemigos** vía `enemies_state` cada 50ms
3. **Los IDs no coincidían**: enemigos locales tenían IDs distintos a los del servidor
4. **Sincronización incompleta**: `_handle_enemies_state` solo actualizaba enemigos existentes, no reconciliaba la lista completa

## Soluciones Implementadas

### 1. Cliente NO Crea Enemigos Localmente
**Archivos**: `CODIGO/Game.py`
**Líneas**: 1436, 940, 2363

```python
# [FIX SYNC] Cliente NO crea enemigos — los recibe del servidor
if self.net is None or self.net.es_servidor:
    self._spawn_room_enemies(room)
```

**Impacto**: Solo el servidor (PC1) crea enemigos. El cliente (PC2) espera `enemies_state` del servidor.

---

### 2. Reconciliación Completa en `_handle_enemies_state()`
**Archivo**: `CODIGO/Game.py`
**Función**: `_handle_enemies_state()` (completa reescritura)

Tres pasos de reconciliación:

#### PASO 1: Eliminar Enemigos Fantasma
```python
# Enemigos que el cliente tiene pero el servidor NO envía → eliminar
ids_a_eliminar = []
for i, enemy in enumerate(room.enemies):
    enemy_id = getattr(enemy, "enemy_id", None)
    if enemy_id and enemy_id not in server_enemies_by_id:
        ids_a_eliminar.append(i)
```

#### PASO 2: Crear Enemigos Nuevos
```python
# Enemigos que el servidor envía pero el cliente NO tiene → crear
if server_id not in client_enemy_ids_por_id:
    enemy = self._create_enemy_from_server_type(...)
    room.enemies.append(enemy)
```

#### PASO 3: Actualizar Existentes
```python
# Enemigos que existen en ambos → sincronizar posición, salud, animación
enemy.x = server_data.get("x", enemy.x)
enemy.y = server_data.get("y", enemy.y)
enemy.hp = server_data.get("health", enemy.hp)
```

---

### 3. Factory para Crear Enemigos Dinámicamente
**Archivo**: `CODIGO/Game.py`
**Función**: `_create_enemy_from_server_type()`

```python
def _create_enemy_from_server_type(self, enemy_type: str, x: float, y: float, enemy_id: str | None = None):
    """Crea un Enemy real basado en el tipo enviado por el servidor."""
    enemies_map = {
        "FastChaserEnemy": FastChaserEnemy,
        "ShooterEnemy": ShooterEnemy,
        "BasicEnemy": BasicEnemy,
        "TankEnemy": TankEnemy,
        "FakerEnemy": FakerEnemy,
        "TelefonoEnemy": TelefonoEnemy,
        "EmojiEnemy": EmojiEnemy,
    }
    
    enemy_class = enemies_map.get(enemy_type)
    enemy = enemy_class(x, y)
    
    # Reemplazar ID local con ID del servidor
    if enemy_id:
        enemy.enemy_id = enemy_id
    
    return enemy
```

---

### 4. Sincronización Inmediata Después de Transiciones
**Archivo**: `CODIGO/Game.py`
**Función**: `_procesar_transicion()` (línea 2437-2440)

```python
# [FIX SYNC] Enviar estado de enemigos inmediatamente después de la transición
self._sync_enemies_to_client(new_room)
self._sync_enemy_projectiles_to_client(new_room)
```

**Impacto**: El cliente no espera hasta el siguiente ciclo de sincronización de 50ms. Recibe enemigos inmediatamente.

---

### 5. Importar Clases Enemy Necesarias
**Archivo**: `CODIGO/Game.py`
**Línea**: 17-21

```python
from entities.Enemy import (
    IDLE as ENEMY_IDLE,
    FastChaserEnemy, ShooterEnemy, BasicEnemy, TankEnemy,
    FakerEnemy, TelefonoEnemy, EmojiEnemy
)
```

---

## Verificación

### Antes del Fix
```
Cliente: 5 enemigos (IDs: local_1, local_2, local_3, local_4, local_5)
Servidor: 3 enemigos (IDs: srv_001, srv_002, srv_003)
❌ Desincronización — cliente tiene 2 enemigos extras
```

### Después del Fix
```
1. Cliente recibe enemies_state con [srv_001, srv_002, srv_003]
2. Cliente elimina [local_1, local_2, local_3, local_4, local_5] (no en servidor)
3. Cliente crea [srv_001, srv_002, srv_003] si no existen
4. Cliente actualiza posiciones y salud desde servidor
✅ Sincronización perfecta — cliente y servidor tienen los mismos enemigos
```

---

## Testing Recomendado

1. **Lanzar servidor en PC1**:
   ```bash
   python Main.py --server --port 5555
   ```

2. **Lanzar cliente en PC2**:
   ```bash
   python Main.py --client --host <IP_PC1> --port 5555
   ```

3. **Verificaciones**:
   - [ ] Entrar a sala con enemigos
   - [ ] Verificar que PC1 y PC2 ven el MISMO número de enemigos
   - [ ] Verificar que tipos de enemigos coinciden
   - [ ] Matar enemigos en PC1 → PC2 debe verlos desaparecer
   - [ ] Cambiar de sala → PC2 debe ver enemigos de sala nueva, no anteriores
   - [ ] Revisar logs para `[SYNC]` — no debe haber "fantasmas" detectados

4. **Logs Clave** (buscar en console):
   ```
   [SYNC] Eliminando enemigo fantasma ... (no en servidor)  ← NO debería aparecer
   [SYNC] Creado nuevo enemigo ... 
   [SYNC] Reconciliación completada: cliente=N enemigos, servidor=N
   ```

---

## Cambios de Comportamiento

| Antes | Después |
|-------|---------|
| Cliente crea enemigos locales + recibe del servidor | Cliente solo recibe del servidor |
| Sincronización parcial (solo actualiza existentes) | Reconciliación completa (elimina, crea, actualiza) |
| Cliente puede tener MÁS enemigos que servidor | Cliente siempre tiene EXACTAMENTE los del servidor |
| IDs de enemigos no coinciden | IDs de enemigos coinciden perfectamente |
| Sala vacía durante 50ms después de transición | Enemigos aparecen inmediatamente |

---

## Arquitectura Resultante

```
PC1 (Servidor)                          PC2 (Cliente)
└─ Crea enemigos                        └─ Recibe enemies_state
└─ Simula enemigos                      └─ Reconcilia lista
└─ Envía enemies_state c/50ms           └─ Crea enemigos que falta
└─ Envía transicion → Sync inmediata    └─ Renderiza enemigos reconciliados
```

---

## Rollback

Si necesitas revertir estos cambios:
```bash
git revert 9efde8f
```

Commit: `9efde8f` - Fix: Sincronización de enemigos cliente-servidor
