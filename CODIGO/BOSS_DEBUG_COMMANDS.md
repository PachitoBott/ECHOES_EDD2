# Boss Room Debug Commands

Para facilitar el desarrollo y testing en la sala del boss, se han agregado dos comandos de debug:

## Acceder a la Consola de Debug

**Atajo:** Presiona `F1` durante el juego para abrir/cerrar la consola de debug.

La consola aparecerá en la esquina superior izquierda. Escribe comandos y presiona Enter para ejecutar.

---

## Comandos Disponibles

### 1. `boss` - Teleportarse a la Sala del Boss

**Uso:**
```
boss
```

**Descripción:**
Teletransporta instantáneamente al jugador a la sala del boss, sin importar dónde estés en el dungeon.

**Ejemplo:**
```
> boss
OK — sala del BOSS en (0,1)  profundidad=5
```

**Ventaja:** Útil para acceder rápidamente a la sala del boss sin tener que pasar por todo el dungeon.

---

### 2. `skippapers` - Skipear el Minijuego PAPERS

**Uso:**
```
skippapers
```

**Descripción:**
Si el minijuego PAPERS está activo, lo completa automáticamente (marcándolo como "aprobado"). Esto permite acceder directamente a la sala del boss sin tener que completar el minijuego.

**Ejemplo:**
```
> skippapers
OK — minijuego PAPERS skipeado. Acceso a sala del boss permitido.
```

**Ventaja:** Evita tener que jugar el minijuego cada vez que quieres hacer cambios en la sala del boss.

---

## Flujo de Trabajo Recomendado

### Para Testing Rápido de la Sala del Boss:

1. **Inicia el juego**
2. **Presiona F1** para abrir la consola de debug
3. **Escribe `boss`** para teleportarte a la sala del boss
4. El minijuego PAPERS se activará automáticamente
5. **Escribe `skippapers`** para completarlo sin jugar
6. Ahora puedes testing libr en la sala del boss

### Ejemplo Completo:

```
[Juego abierto]
[Presiono F1]
> boss
OK — sala del BOSS en (0,1)  profundidad=5
[El minijuego PAPERS se activa]
[Presiono F1 para abrir consola mientras está el minijuego]
> skippapers
OK — minijuego PAPERS skipeado. Acceso a sala del boss permitido.
[Ahora estoy en la sala del boss sin minijuego]
```

---

## Otros Comandos Útiles

Mientras desarrollas en la sala del boss, estos otros comandos pueden ser útiles:

- **`clear`** - Elimina todos los enemigos de la sala actual
- **`god`** - Toggle modo invulnerable (útil para testing sin morir)
- **`set hp <n>`** - Ajusta tu HP (ej: `set hp 50`)
- **`set gold <n>`** - Ajusta el oro (ej: `set gold 1000`)
- **`seed`** - Muestra la seed actual del dungeon

---

## Notas Técnicas

### Cómo Funciona `skippapers`:

El minijuego PAPERS tiene dos propiedades:
- `terminado`: indica si el minijuego ha terminado
- `aprobado`: indica si el jugador lo aprobó o no

El comando `skippapers` establece ambas en `True`, lo cual hace que:
1. El juego detecte que el minijuego terminó
2. El juego verifique que fue aprobado (no reinicia la run)
3. El minijuego se desactiva y continúa el gameplay normal

---

## Troubleshooting

### Error: "no hay minijuego PAPERS activo"
- Significa que `skippapers` fue ejecutado fuera de la sala del boss, o el minijuego ya fue completado
- Uso correcto: ejecutar `skippapers` SOLO cuando estés en la sala del boss y el minijuego esté activo

### Error: "estado inconsistente"
- Indica un bug interno (nunca debería pasar)
- Si ocurre, reportar con la seed utilizada

---

## Status

✅ Comandos implementados y probados
✅ Integrados en la consola de debug
✅ Listos para uso en desarrollo
