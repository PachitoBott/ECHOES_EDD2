# Sincronización de Enemigos - Cambios Implementados

## Resumen

Se ha implementado un sistema completo de sincronización de enemigos en modo multijugador cooperativo. El servidor (PC1) es ahora la única fuente de autoridad para los enemigos, y el cliente (PC2) solo renderiza los estados que recibe.

## Archivos Modificados

### 1. `CODIGO/entities/Enemy.py`
**Cambio**: Agregado sistema de IDs únicos para enemigos
- Agregó contador global `_ENEMY_COUNTER`
- Agregó función `_generar_enemy_id()` que genera IDs únicos (ej: "enemy_000001")
- Cada enemigo instanciado ahora tiene `self.enemy_id` único

### 2. `CODIGO/network/protocol.py`
**Cambio**: Agregados dos nuevos mensajes de protocolo

#### `msg_enemies_state()`
- Sincronización continua del estado de TODOS los enemigos
- Se envía cada ~50ms (20 veces por segundo) desde servidor a cliente
- Contiene: lista de enemigos con id, tipo, posición (x,y), health, vivo

#### `msg_bullet_fired_by_client()`
- Evento del cliente para notificar al servidor sobre disparos
- Permite que el servidor procese colisiones contra sus enemigos
- Contiene: posición, dirección, daño

### 3. `CODIGO/Game.py`

#### Clase nueva: `RemoteEnemy`
- Representa un enemigo sincronizado del servidor en el cliente
- Solo propiedades: ID, tipo, posición, health, vivo
- Método `actualizar_desde_red()` para actualizar desde servidor
- SIN lógica de actualización (no se mueve localmente)

#### En `Game.__init__()`:
- Agregó `self.remote_enemies = {}` para almacenar enemigos sincronizados

#### Nueva método: `_sync_enemies_to_client()`
- Llamado cada frame después de `_update_enemies()`
- Solo ejecuta si es servidor
- Envía estado de todos los enemigos cada 50ms
- Optimizado: redondea posiciones, solo enemigos vivos

#### Método modificado: `_update_enemies()`
- **Cliente**: Ahora retorna sin hacer nada (no simula enemigos)
- **Servidor/Offline**: Funciona igual que antes

#### Método modificado: `_handle_collisions()`
- **Cliente**: NO procesa colisiones de sus propios proyectiles contra enemigos
- **Servidor/Offline**: Procesa normalmente

#### Nueva método: `_handle_enemies_state()`
- Procesa evento "enemies_state" del servidor
- Actualiza posición/estado de enemigos remotos
- Limpia enemigos que ya no existen

#### Nueva método: `_process_client_bullet()`
- El servidor procesa disparos del cliente
- Detecta colisiones contra sus enemigos
- Envía evento "enemigo_muerto" si hay muerte

#### Método modificado: `_on_player_shoot()`
- Ahora envía `msg_bullet_fired_by_client()` si es cliente
- Permite que servidor procese daño

#### En `_procesar_evento_red()`:
- Agregados manejadores para:
  - `"enemies_state"` → `_handle_enemies_state()`
  - `"bullet_fired_by_client"` → `_process_client_bullet()` (servidor)
  - `"room_clear"` → marca sala como limpia en cliente

#### Método modificado: `_handle_collisions()`
- Agregado envío de evento "room_clear" cuando sala se completa (servidor)

## Flujo de Sincronización

### Movimiento de Enemigos
```
SERVIDOR (PC1)                      CLIENTE (PC2)
┌─────────────────────────────────────────────────────┐
│ 1. Update enemies locales        (cada frame)       │
│ 2. Calcular targeting (ambos jug)                   │
│ 3. Enviar state cada 50ms        ──→  Recibe state │
│ 4. Renderizar                          Actualiza    │
│                                        Renderiza    │
└─────────────────────────────────────────────────────┘
```

### Disparos
```
CLIENTE (PC2)                       SERVIDOR (PC1)
┌─────────────────────────────────────────────────────┐
│ 1. Jugador dispara                                  │
│ 2. Envía bullet_fired ──→  Recibe disparo         │
│ 3. Renderiza visualización        Procesa colisión │
│                                   Aplica daño      │
│ 4. Si enemigo muere:         ← Envía "enemigo_muerto"
│    Recibe evento            │  Renderiza muerte    │
└─────────────────────────────────────────────────────┘
```

## Checklist de Verificación

Después de implementar, verificar:

- [ ] **Servidor ejecuta**: `python Main.py --server --port 5555 --skip-menu`
- [ ] **Cliente conecta**: `python Main.py --client --host 192.168.1.9 --port 5555 --role aliado --skip-menu`
- [ ] **Enemigos aparecen en misma posición inicial en ambos PCs**
- [ ] **Enemigos se mueven igual en ambos PCs** (no divergen)
- [ ] **Disparos del servidor matan enemigos en ambos lados**
- [ ] **Disparos del cliente matan enemigos en ambos lados**
- [ ] **Cuando muere un enemigo en un PC, muere en el otro**
- [ ] **Cuando sala se completa, puertas se abren en ambos PCs**
- [ ] **Modo offline sigue funcionando sin cambios**
- [ ] **Sin crasheos al conectar/desconectar**

## Pruebas Recomendadas

1. **Test básico de sincronización**:
   - Ambos PCs entran a una sala con enemigos
   - Verificar que aparecen en misma posición en ambos

2. **Test de movimiento**:
   - Un PC se queda parado, otro se mueve
   - Enemigos deben seguir al jugador que se mueve (en ambos PCs)

3. **Test de disparos del servidor (PC1)**:
   - PC1 dispara y mata un enemigo
   - Verificar que muere en PC2

4. **Test de disparos del cliente (PC2)**:
   - PC2 dispara y mata un enemigo
   - Verificar que muere en PC1

5. **Test de sala completada**:
   - Matar todos los enemigos
   - Verificar que puertas se abren en ambos PCs

## Notas Técnicas

- **Frecuencia de sync**: 20 Hz (cada 50ms) - balance entre precision y bandwidth
- **Tolerancia de búsqueda**: 5 píxeles para encontrar enemigos remotos
- **IDs de enemigos**: Generados secuencialmente (enemy_000001, enemy_000002, etc)
- **Arquitectura**: Cliente-Servidor con servidor único como autoridad

## Problemas Conocidos / Mejoras Futuras

1. **Interpolación de posiciones**: No implementada aún. Si la red es lenta, enemigos "teleportean" 
   - Solución: Implementar lerp suave hacia posición remota

2. **Detección de colisión de balas**: Actualmente usa rect simple en posición inicial
   - Mejora: Simular trayectoria de bala con line-of-intersection

3. **Sincronización de daño**: Si cliente y servidor disparan al mismo enemigo simultáneamente
   - Solución: Implementar lock/turnos para aplicar daño

4. **Timeout de sincronización**: Si cliente se atrasa, enemigos pueden quedarse fuera de sync
   - Solución: Mecanismo de corrección de desincronización

## Rollback / Reversión

Si necesitas revertir los cambios:
```bash
git checkout HEAD -- CODIGO/Game.py CODIGO/entities/Enemy.py CODIGO/network/protocol.py
```

