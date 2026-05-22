# Testing - Transiciones de Cuarto Sincronizadas

## ✅ Implementación Completada

Se han hecho los siguientes cambios:

1. ✅ **protocol.py**: Función `msg_transicion_completada()` agregada
2. ✅ **Game.py**: `_handle_room_transition()` modificada para cliente/servidor
3. ✅ **Game.py**: `_procesar_transicion()` nueva función
4. ✅ **Game.py**: `_procesar_accion()` nueva función para servidor
5. ✅ **Game.py**: `_handle_transicion_completada()` nueva función para cliente
6. ✅ **Game.py**: `_procesar_evento_red()` modificada para manejar acciones y transiciones

---

## 🎯 Comportamiento Esperado

### Escenario 1: Servidor Activa Puerta
```
PC1 (Servidor) toca puerta → [TRANSICION] Servidor procesando...
                          → PC1 se mueve a nueva sala
                          → PC2 recibe evento
PC2 (Cliente) → [TRANSICION] Cliente recibió transición completada
              → PC2 teletransportado a nueva sala
Resultado: AMBOS en misma sala ✓
```

### Escenario 2: Cliente Activa Puerta
```
PC2 (Cliente) toca puerta → [TRANSICION] Cliente detectó puerta
                         → Envía "transicion" al servidor
PC1 (Servidor) recibe → [TRANSICION] Servidor procesando transición de aliado
                      → PC1 se mueve a nueva sala
                      → Notifica al PC2
PC2 (Cliente) recibe → [TRANSICION] Cliente recibió transición completada
                    → Se teletransporta a nueva sala
Resultado: AMBOS en misma sala ✓
```

### Escenario 3: Ambos Tocan Simultáneamente
```
Con el cooldown de 0.25s, solo UNO puede transicionar
El otro es teletransportado
Resultado: AMBOS en misma sala ✓
```

---

## 🧪 Protocolo de Testing

### Paso 1: Iniciar Servidores

**Terminal 1 (Servidor):**
```bash
cd F:\martin\Universidad\ECHOES_EDD2
python Main.py --server --port 5555 --skip-menu
```

**Terminal 2 (Cliente) - Esperar 2-3 segundos:**
```bash
cd F:\martin\Universidad\ECHOES_EDD2
python Main.py --client --host 127.0.0.1 --port 5555 --role aliado --skip-menu
```

Ambos deben estar en la misma sala inicial.

---

### Paso 2: Test 1 - Servidor Activa Puerta

**Acción:**
1. En PC1 (Servidor): Acércate a una puerta y presiona la dirección (N/S/E/O)
2. Observa lo que pasa en PC2 (Cliente)

**Logs Esperados:**

Terminal 1:
```
[TRANSICION] Servidor procesando transición en dirección N
Room enter: (0, 1) at depth...
[TRANSICION] Servidor notificó transición completada a sala (0, 1)
```

Terminal 2:
```
[TRANSICION] Cliente recibió transición completada a sala (0, 1), pos=(...)
```

**Resultado Visual:**
- ✅ PC1 se mueve a sala superior
- ✅ PC2 también se mueve a sala superior (automáticamente)
- ✅ Ambos ven los mismos enemigos
- ✅ Las puertas cargan correctamente

---

### Paso 3: Test 2 - Cliente Activa Puerta

**Acción:**
1. En PC2 (Cliente): Acércate a una puerta y presiona la dirección
2. Observa lo que pasa en PC1 (Servidor)

**Logs Esperados:**

Terminal 2:
```
[TRANSICION] Cliente detectó puerta en dirección S
```

Terminal 1:
```
[TRANSICION] Servidor procesando transición de aliado en dirección S
Room enter: (0, -1) at depth...
[TRANSICION] Servidor notificó transición completada a sala (0, -1)
```

Terminal 2:
```
[TRANSICION] Cliente recibió transición completada a sala (0, -1), pos=(...)
```

**Resultado Visual:**
- ✅ PC2 espera (NO se mueve inmediatamente)
- ✅ PC1 se mueve a nueva sala
- ✅ PC2 se teletransporta automáticamente
- ✅ Ambos llegan al mismo sitio

---

### Paso 4: Test 3 - Movimiento Libre Entre Salas

**Acción:**
1. Alterna entre PC1 y PC2 activando diferentes puertas
2. Muévete varias salas en cualquier dirección
3. Verifica que siempre estén sincronizados

**Resultado Esperado:**
- ✅ Independientemente de quién active la puerta, ambos se sincronizan
- ✅ No hay desincronización
- ✅ Los enemigos aparecen correctamente en nuevas salas
- ✅ El minimapa se actualiza igual en ambas máquinas

---

## 🔍 Checklist de Validación

### Transiciones Correctas
- [ ] Servidor activa puerta → ambos se mueven
- [ ] Cliente activa puerta → ambos se mueven
- [ ] Ambos tocan puerta al mismo tiempo → se resuelve sin errores

### Sincronización
- [ ] Los enemigos en nueva sala son los mismos en ambas máquinas
- [ ] Las posiciones de los jugadores coinciden
- [ ] El cooldown de puertas (0.25s) funciona

### Sin Errores
- [ ] No hay crashes cuando se activa puerta
- [ ] No hay mensajes de error de red
- [ ] Los logs muestran [TRANSICION] correctamente

### Cinemática y Efectos
- [ ] Transición es suave (sin teleportación visible)
- [ ] Los enemigos cargan en nueva sala
- [ ] Las balas y projectiles se limpian correctamente

---

## ⚠️ Problemas Comunes y Soluciones

### Problema: Cliente no se teletransporta después de activar puerta

**Checklist:**
1. ¿Ves el log "[TRANSICION] Cliente detectó puerta"? 
   - Si NO: El cliente no detectó la puerta (problema de colisión)
   - Si SÍ: Continúa

2. ¿Ves en Terminal 1 "[TRANSICION] Servidor procesando transición de aliado"?
   - Si NO: El mensaje no llegó al servidor (problema de red)
   - Si SÍ: Continúa

3. ¿Ves en Terminal 2 "[TRANSICION] Cliente recibió transición completada"?
   - Si NO: El cliente no recibió la respuesta del servidor

---

### Problema: Ambos jugadores desincronizados después de transición

**Causa Probable:** La posición no se sincronizó correctamente

**Verificación:**
- Chequea que `pos_aliado` en el mensaje sea correcta
- Verifica que `self.dungeon.i, self.dungeon.j` se actualicen correctamente

---

### Problema: Error "accion no reconocida"

**Checklist:**
- La acción debe ser manejada en `_procesar_accion()`
- Verifica que el tipo sea exactamente "transicion"

---

## 📊 Logs a Monitorear

```bash
# Ver todos los logs de transición en tiempo real
tail -f .claude/logs/game.log | grep TRANSICION

# Ver solo errores
tail -f .claude/logs/game.log | grep -E "ERROR|WARN"
```

---

## ✅ Cuando Todo Esté Listo

Si todos los tests pasan:

1. Documente los cambios realizados
2. Agregue comentarios al código si es necesario
3. Considere agregar cinemática de transición si lo desea
4. Prepare para la siguiente feature

