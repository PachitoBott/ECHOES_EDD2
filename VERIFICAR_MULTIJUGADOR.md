# Verificación: Multijugador Restaurado

## ¿Qué se arregló?

**Problema**: Al implementar el menú sincronizado (ServidorMenu/ClienteMenu en puerto 5555), la conexión de red del juego se perdía. El menú funcionaba, pero al iniciar el juego, cada PC quedaba sin conexión.

**Causa raíz**: NetworkManager intentaba iniciar en `Game.__init__()` mientras ServidorMenu/ClienteMenu ya estaban usando puerto 5555.

**Solución**:
1. ❌ NO iniciar NetworkManager en `Game.__init__()` (solo crear instancia)
2. ✅ Iniciar NetworkManager en `start_new_run()` DESPUÉS de cerrar ServidorMenu/ClienteMenu
3. ✅ Esperar 0.5 segundos para que puerto 5555 se libere completamente

---

## Plan de Testing

### Escenario 1: Servidor + Cliente en misma red

**Terminal 1 (Servidor en PC1)**:
```bash
cd F:\martin\Universidad\ECHOES_EDD2
git pull
python Main.py --server --port 5555
```

**Terminal 2 (Cliente en PC2)**:
```bash
cd F:\martin\Universidad\ECHOES_EDD2
git pull
python Main.py --client --host 192.168.1.9 --port 5555 --role victim
```

**Pasos**:
1. Ambas PCs llegan al menú principal
2. PC1 presiona "JUGAR" → lobby
3. PC2 recibe cambio automáticamente → ve "JUGADOR 2 CONECTADO"
4. PC1 ve "JUGADOR 2 LISTO" con animación del personaje 2
5. **CRÍTICO**: PC1 presiona "INICIAR PARTIDA"
6. Ambas PCs entran a cinemáticas
7. Ambas PCs entran al juego

---

## Checklist de Verificación

### ✓ Fase 1: Menú Sincronizado
- [ ] PC1 ve lobby con "JUGADOR 1" (rojo, dice HOST)
- [ ] PC2 se conecta y ve lobby con "JUGADOR 2" (azul, dice CLIENTE)
- [ ] PC1 ve cambio en PC2 en tiempo real (estado de conexión)
- [ ] Animaciones de personajes se renderan correctamente en ambos (P1 en PC1, P2 en PC2)

### ✓ Fase 2: Transición al Juego (LA CRÍTICA)
- [ ] PC1 presiona "INICIAR PARTIDA"
- [ ] **Logs esperados en PC1**:
  ```
  [GAME] Iniciando nueva partida, seed=XXXXX, modo_coop=True
  [GAME] Nueva partida cargada exitosamente
  [NET] Iniciando NetworkManager después de cerrar menú...
  [OK] NetworkManager del juego iniciado correctamente
  [OK] Servidor escuchando en puerto 5555
  [OK] Seed compartida con clientes: XXXXX
  ```
- [ ] **Logs esperados en PC2**:
  ```
  [MENU CLIENT] ✓ Recibido START_GAME del servidor, seed=XXXXX
  [MENU CLIENT] Transicionando a juego cooperativo...
  [GAME] Iniciando nueva partida, seed=XXXXX, modo_coop=True
  [GAME] Nueva partida cargada exitosamente
  [NET] Iniciando NetworkManager después de cerrar menú...
  [OK] NetworkManager del juego iniciado correctamente
  [OK] Cliente conectado como victima
  ```

### ✓ Fase 3: Gameplay Sincronizado
- [ ] Ambos PCs en el juego simultáneamente
- [ ] **PC1**: Ve su personaje (VÍCTIMA) con skin + ve P2 como cubo negro
- [ ] **PC2**: Ve P1 como cubo negro + ve su personaje (ALIADO) con skin
- [ ] Enemigos en la misma sala en ambas PCs
- [ ] Movimiento de PC1 se refleja en PC2 (P2 aparece moviéndose)
- [ ] Daño recibido por PC1 se ve en PC2
- [ ] **PC2 puede usar acciones de soporte** (si está implementado):
  - Enviar curaciones
  - Compartir oro
  - Revelar mapa
- [ ] Salas generadas son idénticas (misma seed → mismo dungeon)

### ✓ Fase 4: Cierre Correcto
- [ ] Un PC se desconecta → el otro vuelve a juego offline (si es posible)
- [ ] O ambos vuelven al menú
- [ ] Reiniciar juego multiusuario funciona (menú sincronizado nuevamente)

---

## Logs Clave a Vigilar

### En PC1 (Servidor):
```
[NET] NetworkManager creado como SERVIDOR (iniciará después del menú)
[OK] Servidor del menú cerrado
[NET] Iniciando NetworkManager después de cerrar menú...
[OK] NetworkManager del juego iniciado correctamente
[OK] Servidor escuchando en puerto 5555
```

### En PC2 (Cliente):
```
[NET] NetworkManager creado como CLIENTE (iniciará después del menú)
[OK] Cliente del menú cerrado
[NET] Iniciando NetworkManager después de cerrar menú...
[OK] NetworkManager del juego iniciado correctamente
[OK] Cliente conectado como victima
```

---

## Síntomas de ERROR (Si algo falla)

| Error | Causa Probable | Fix |
|-------|----------------|-----|
| `[ERROR] No se pudo iniciar NetworkManager del juego` en PC1 | Otro proceso usa puerto 5555 | Cerrar otro juego/servidor |
| `[ERROR] No se pudo conectar a IP:5555` en PC2 | Servidor no está escuchando | Verificar que PC1 mostró "Servidor escuchando" |
| PC2 nunca recibe START_GAME | ServidorMenu cerró mal | Revisar ClienteMenu.cerrar() |
| Juego comienza offline (sin sincronización) | NetworkManager está None | Verificar logs de inicialización |
| Enemigos en diferentes lugares en PC1 vs PC2 | Seed diferente o no sincronizada | Verificar "Seed compartida con clientes" |

---

## Cambios de Código (Para referencia)

### Game.__init__() (Líneas 387-410)
**ANTES**: `self.net.iniciar()` se llamaba aquí (conflicto de puerto)
**AHORA**: Solo `self.net = NetworkManager.como_servidor()` sin iniciar

### Game.start_new_run() (Líneas 572-587)
**NUEVO**: Bloque que inicia NetworkManager DESPUÉS de cerrar ServidorMenu/ClienteMenu
```python
if self.net and not self.net._iniciado:
    if not self.net.iniciar():
        self.net = None  # Juego offline
    else:
        log_game.info("[OK] NetworkManager iniciado")
```

### StartMenu.py (Línea 348)
**MEJORADO**: Mejor logging cuando cliente recibe START_GAME

---

## Próximos Pasos (Post-Verificación)

Si todo funciona:
1. ✅ Remover logs de debug `[NET]` después de confirmar
2. ✅ Subir a main
3. ✅ Testing en dos PCs diferentes
4. ✅ Verificar que Player 2 renderiza animación correctamente
5. ✅ Verificar sincronización de enemigos/salas
6. ✅ Testing de acciones de soporte (Aliado → Víctima)

Si algo falla:
1. 📋 Capturar TODOS los logs (completos desde inicio)
2. 📋 Describir exactamente qué no funciona
3. 📋 Reportar en el canal/issue del proyecto
