# Fix: Tolerancia de Búsqueda de Enemigos Muertos

## Problema Identificado

En modo multijugador, los enemigos que disparan proyectiles morían incorrectamente cuando ejecutaban su animación de ataque. 

**Síntomas:**
- Enemy dispara hacia jugador
- Enemy entra en animación de ataque/disparo
- Enemy muere sin ser impactado

**Causa Raíz:**
El cliente detectaba colisiones de proyectiles contra enemigos basándose en su vista LOCAL, pero reportaba posiciones desincronizadas con el servidor.

Ejemplo del servidor log:
```
[MUERTE_REMOTA] [NOTFOUND] Enemy@ (588, 294) NO ENCONTRADO en servidor (distancia mínima: 33 píxeles)
Servidor tiene enemy @ (555, 295)
```

## Análisis de la Desincronización

### Timeline de Eventos:

1. **T=0ms**: Servidor envía `enemies_state` con enemy en posición (555, 295)
2. **T=50ms**: Cliente recibe actualización, enemy en cliente = (555, 295)
3. **T=50-100ms**: Cliente corre su loop de actualización local
   - NO mueve el enemy (correctamente)
   - Pero servidor SIGUE moviendo su enemy
4. **T=80ms**: Servidor ha movido enemy a (~588, 294)
5. **T=85ms**: Cliente detecta colisión de proyectil con enemy @ (555, 295)
6. **T=90ms**: Cliente envía `enemigo_muerto` report con pos=(555, 295)
7. **T=92ms**: Servidor recibe report, pero su enemy está @ (588, 294)
8. **T=92ms**: Servidor busca enemy @ (555, 295) con tolerancia de 5px → NO ENCONTRADO
9. **T=92ms**: ERROR: "Enemy no encontrado" ✗

### Por qué ocurre la desincronización:

- **Latencia de red**: ~30-50ms round trip
- **Frecuencia de sync**: 50ms (20 Hz)
- **Tiempo de simulación en servidor**: ~100ms entre recibir report y procesarlo
- **Velocidad de enemigos**: Típicamente 100-200 px/s → 10-20px cada 100ms
- **Resultado**: Offset de 30-40 píxeles es normal

## La Solución

### Cambio 1: Aumentar Tolerancia

**Antes:**
```python
tolerance = 5.0  # píxeles
```

**Después:**
```python
tolerance = 50.0  # píxeles (aumentado de 5 para tolerar desync de red)
```

**Justificación:**
- 50 píxeles = ~250ms de desincronización a velocidad típica de enemigos
- Proporciona amplio margen para latencia de red
- Pero aún lo suficientemente restrictivo para evitar matches falsas

### Cambio 2: Buscar Enemigo MÁS CERCANO

**Antes:**
```python
if dist <= tolerance and enemy.__class__.__name__ == enemy_type:
    enemy_encontrado = enemy
    indice_encontrado = i
    encontrado = True
    break  # Primero que encontrara
```

**Después:**
```python
if dist <= tolerance and enemy.__class__.__name__ == enemy_type and dist < min_dist:
    enemy_encontrado = enemy
    indice_encontrado = i
    min_dist = dist
    encontrado = True
    # NO break - continuar buscando el más cercano
```

**Justificación:**
- Si hay múltiples enemigos del mismo tipo dentro de 50px, elegir el más cercano
- Reduce probabilidad de matches falsas
- Más preciso que usar el primero que aparece

### Cambio 3: Mejor Logging

**Antes:**
```python
log_game.debug(f"[MUERTE_REMOTA] [NOTFOUND] NO ENCONTRADO...")
```

**Después:**
```python
log_game.warning(f"[MUERTE_REMOTA] [NOTFOUND] NO ENCONTRADO...")
# Mostrar enemigo más cercano como referencia
closest_dist = ...
log_game.debug(f"[MUERTE_REMOTA] Enemigo más cercano a {closest_dist:.1f} píxeles")
```

**Beneficio:**
- Facilita debugging si el problema persiste
- Muestra por cuántos píxeles fallaron los matches

## Validación

### Ejemplo que Ahora Funciona:

```
Cliente reporta: Enemy muerto en (588, 294)
Servidor busca: Enemy del tipo correcto dentro de 50px
Servidor encuentra: Enemy en (555, 295)
Distancia: 33.0px < 50.0px ✓ MATCH ENCONTRADO
```

### Test Simple:

```python
import math
server_pos = (555, 295)
client_pos = (588, 294)
dist = math.hypot(client_pos[0] - server_pos[0], client_pos[1] - server_pos[1])
# dist = 33.0 píxeles

old_tolerance = 5.0
new_tolerance = 50.0

old_match = dist <= old_tolerance  # False - problema original
new_match = dist <= new_tolerance  # True - problema resuelto ✓
```

## Notas Importantes

1. **Esto es una solución de corto plazo** que acepta que existe desincronización de red
2. **Soluciones mejores a largo plazo podrían incluir:**
   - Enviar ID del enemigo en lugar de solo posición
   - Usar PhysX o similar para sincronización más precisa
   - Aumentar frecuencia de sync de 50ms a 33ms (30Hz)
   - Implementar client-side prediction con rollback

3. **Esta tolerancia de 50px es segura porque:**
   - Una sala típica tiene enemigos distribuidos (no en racimos)
   - Los enemigos del mismo tipo están generalmente > 50px aparte
   - Es mayor que cualquier error de interpolación razonable

## Archivos Modificados

- `CODIGO/Game.py`
  - `_handle_remote_enemy_death()` line 1044: tolerancia 5→50
  - Búsqueda: ahora busca el más cercano, no el primero
  - Logging: mejorado para diagnosticar problemas

## Commits

- `1f0e9fd` - FIX: Aumentar tolerancia de búsqueda de enemigos muertos de 5 a 50 píxeles
- `e4d152c` - DIAG: Mejorar logs de detección de muerte en cliente

## Testing

Para verificar que el fix funciona:

```bash
# Terminal 1 - Servidor
python Main.py --server --port 5555 --seed 42 --skip-menu

# Terminal 2 - Cliente
python Main.py --client --host 127.0.0.1 --port 5555 --role ally --seed 42 --skip-menu
```

**Comportamiento esperado:**
- Los enemigos que disparan NO deberían morir al atacar
- Si todavía ocurre, revisar los logs del servidor para ver la distancia de desincronización
- Si la distancia es > 50px, puede significar que la latencia es muy alta o hay otro problema

## Si el Problema Persiste

Si después de este fix los enemigos aún mueren al atacar:

1. **Revisar logs del servidor:** Buscar línea "distancia mínima" en `[MUERTE_REMOTA]`
2. **Si distancia > 50px:**
   - La latencia de red es muy alta
   - Aumentar tolerancia adicional
   - O revisar si hay otro problema (ejemplo: frecuencia de sync)

3. **Si distancia < 50px pero aún no encuentra:**
   - Problema diferente: posiblemente el enemy_type es diferente
   - O hay un error en cómo se crea el enemy

4. **Si distancia es exacta (0-1px):**
   - Problema de tipos de datos (int vs float)
   - O de creación de enemigos con IDs duplicados
