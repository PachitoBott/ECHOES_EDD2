# Diagnóstico: Último Enemigo Congelado cuando PC2 hace el Kill

## ⚠️ PROBLEMA RAÍZ IDENTIFICADO Y CORREGIDO

**CAUSA ENCONTRADA**: Acceso incorrecto a `dungeon.rooms`

En `_handle_remote_enemy_death` (línea 1004) y `_handle_remote_damage` (línea 1127):
```python
# INCORRECTO (trata rooms como matriz anidada [0][1]):
room = self.dungeon.rooms[sala_remota[0]][sala_remota[1]]

# CORRECTO (rooms es un diccionario con tuplas como claves):
room = self.dungeon.rooms.get(sala_remota)
```

**EFECTO DEL BUG**:
- Cuando llega el evento "enemigo_muerto", el código intenta acceder a rooms con indexación [0][1]
- Esto causa una excepción (TypeError, KeyError, o IndexError)
- La excepción es atrapada y la función retorna sin hacer nada
- El enemigo NUNCA se elimina de room.enemies
- El sprite queda congelado en pantalla

**FIXES APLICADOS**:
1. Línea ~1004: Cambiar acceso a rooms en `_handle_remote_enemy_death`
2. Línea ~1127: Cambiar acceso a rooms en `_handle_remote_damage`
3. Ambos usan `.get(sala_remota)` que es correcto para diccionarios

## Estado Actual de Logs
Hemos implementado logs de diagnóstico en Game.py en 3 puntos clave:

### 1. Server-side: `_process_client_bullet` (línea ~1390)
- Logs cuando el servidor recibe disparo del cliente
- Logs cuando se detecta colisión con enemigo
- Logs cuando se genera el evento "enemigo_muerto"
- Incluye HP antes/después, contador de enemigos

### 2. Client-side: `_handle_remote_enemy_death` (línea ~976)
- Logs cuando cliente recibe evento de muerte remota
- Logs de búsqueda del enemigo en room.enemies
- Logs si se encontró o no
- Logs después de eliminación del dict

### 3. Render loop: `_render_world` (línea ~2866)
- Logs frecuentes cuando hay 0-2 enemigos en sala
- Muestra qué enemigos están en room.enemies
- Muestra HP, posición, estado "dying" de cada uno

## Próximos Pasos

### Para reproducir el bug:
1. Ejecutar juego en modo multijugador
2. PC1 como servidor
3. PC2 como cliente (aliado)
4. Llegar a una sala con enemigos
5. **PC2 mata el ÚLTIMO enemigo**
6. Observar si sprite queda congelado en pantalla

### Esperado en logs:
```
[DISPARO_CLIENTE] Disparo desde cliente...
[DISPARO_CLIENTE] [HIT] Enemigo[0]...
[DISPARO_CLIENTE] [DEATH] Enemigo muere. Enviando evento...
[MUERTE_REMOTA] ENTRADA: tipo=..., pos=(...)
[MUERTE_REMOTA] ANTES: 1 enemigos en lista
[MUERTE_REMOTA] [MATCH] Encontrado en índice 0
[MUERTE_REMOTA] [DELETE] Eliminando índice 0...
[MUERTE_REMOTA] [DONE] ELIMINADO. Antes=1, Después=0
[MUERTE_REMOTA] [CLEAR] ¡SALA LIMPIA! (era el último)
[RENDER] room.enemies=0 (vivos=0, muriendo=0)
```

### Si hay bug:
- Logs mostrarán si el enemigo se eliminó de room.enemies o no
- Logs mostrarán si _handle_remote_enemy_death fue llamado
- Logs mostrarán si se encontró el enemigo en la búsqueda

## Instrucciones para recolectar logs
1. Ejecutar con DEBUG_MODE=1 o similar
2. Capturar stdout/stderr a archivo
3. Buscar líneas con [DISPARO_CLIENTE], [MUERTE_REMOTA], [RENDER]
4. Seguir la secuencia temporal (ts=...)

## Notas sobre el bug
- Solo ocurre cuando **PC2 mata el ÚLTIMO enemigo**
- PC1 mata el último → funciona bien
- Esto sugiere un bug en el orden de eventos o en _handle_remote_enemy_death para ese caso específico
- Posible Causa B (del documento original): ROOM_CLEAR llega antes que ENEMY_DEATH

## Código modificado
- CODIGO/Game.py: líneas ~1390, ~976, ~2866
- Cambios son SOLO para diagnóstico (logs WARNING)
- Se pueden remover después del fix
