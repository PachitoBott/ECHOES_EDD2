# Diagnóstico: Enemigos Mueren al Atacar en Multijugador

## Estado Actual
He agregado logs diagnósticos en los siguientes puntos críticos para rastrear exactamente dónde y cuándo los enemigos reciben daño:

### Logs Agregados

**Enemy.py - take_damage():**
```
[DAMAGE] {enemy_id} recibió {amount} daño en ({x:.0f},{y:.0f}). HP: {hp_antes} -> {hp_nuevo}
[DEATH] {enemy_id} muere en ({x:.0f},{y:.0f}). HP final: {hp}
```

**Enemy.py - ShooterEnemy.maybe_shoot():**
```
[SHOOT] {enemy_id} disparando desde ({ex:.0f},{ey:.0f}) hacia jugador en ({px:.0f},{py:.0f}), dist={dist:.1f}
```

**Game.py - Estado Remoto:**
```
[ESTADO_REMOTO_NUEVA] {origen} pos=({x:.0f},{y:.0f}) sala={sala}
```

**Game.py - Targeting:**
```
[TARGETING] {enemy_id} APUNTA A REMOTO: local_dist={dist1} remote_dist={dist2} pos_remota=({x:.0f},{y:.0f})
[TARGETING] {enemy_id} APUNTA A LOCAL: dist={dist} remoto_dist={dist2}
```

**Game.py - Disparos del Cliente:**
```
[DISPARO_CLIENTE] [HIT] Enemigo {enemy_id} ({type} @ ({x:.0f}, {y:.0f})) - IMPACTADO POR BALA DESDE ({bx:.0f},{by:.0f})
```

**Game.py - Daño Remoto:**
```
[DAÑO_REMOTO_APLICADO] {enemy_id} recibe {damage} daño (evento DAÑO_REMOTO desde otro jugador)
```

**Game.py - Limpieza de Enemigos:**
```
[ENEMIES_CLEANUP] {enemy_id} eliminado: hp={hp}, dying={dying_state}, ready_to_remove={ready_state}
```

## Próximos Pasos

Para reproducir el bug y ver los logs:

```bash
# Terminal 1 - Servidor
python Main.py --server --port 5555 --skip-menu --debug

# Terminal 2 - Cliente
python Main.py --client --host 127.0.0.1 --port 5555 --role ally --skip-menu --debug
```

Los logs mostrarán exactamente:
1. Cuándo el cliente envía su posición (o si no la envía)
2. A qué objetivos apuntan los enemigos (LOCAL vs REMOTE)
3. Cuándo disparan los enemigos
4. Cuándo y por qué reciben daño
5. Cómo mueren

## Hipótesis a Verificar

1. **Posición inicial de P2 (0,0):** ¿El cliente envía su posición en (0,0)?
   - Búsqueda: logs `[ESTADO_REMOTO_NUEVA]` al conectar

2. **Targeting incorrecto:** ¿Los enemigos apuntan a (0,0)?
   - Búsqueda: logs `[TARGETING]` mostrando `APUNTA A REMOTO` con pos_remota=(0,0)

3. **Daño desde proyectiles enemigos:** ¿Los proyectiles del enemigo causan daño al enemigo?
   - Búsqueda: logs `[DISPARO_CLIENTE]` O `[DAÑO_REMOTO_APLICADO]` justo antes de `[DEATH]`

4. **Daño remoto:** ¿Se aplica daño remoto al enemigo?
   - Búsqueda: logs `[DAÑO_REMOTO_APLICADO]` justo antes de `[DEATH]`

## Datos a Reportar

Una vez reproducido el bug, reportar:
1. Primer log `[ESTADO_REMOTO_NUEVA]` - ¿Cuál es la pos?
2. Logs `[TARGETING]` - ¿A quién apunta?
3. Logs `[SHOOT]` - ¿A cuál objetivo dispara?
4. Logs antes de `[DEATH]` - ¿Qué evento causa la muerte?

Esto revelará la causa raíz del bug.
