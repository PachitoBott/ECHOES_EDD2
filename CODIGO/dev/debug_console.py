"""
debug_console.py — Consola de debug in-game para Echoes.

Abrir / cerrar con F1.  Escribir comandos y pulsar Enter para ejecutar.
Historial de comandos navegable con flecha ↑ / ↓.

Comandos disponibles
────────────────────
  help                    Muestra esta lista
  spawn <tipo>            Spawnea un enemigo en la sala actual
                            tipos: basic | fast | shooter | tank | faker | telefono | emoji
  set hp <n>              Cambia HP del jugador
  set gold <n>            Cambia oro del jugador
  set lives <n>           Cambia vidas del jugador
  set speed <n>           Cambia velocidad del jugador (temporal)
  teleport <i> <j>        Teletransporta a sala (i, j)
  clear                   Elimina todos los enemigos de la sala actual
  god                     Alterna modo invulnerable
  reload                  Recarga todos los assets monitoreados
  skip                    Avanza a la siguiente sala del camino principal
  seed                    Muestra la seed actual
  rooms                   Lista las salas del dungeon
  log <nivel>             Cambia nivel de logging (DEBUG|INFO|WARNING|ERROR)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pygame

if TYPE_CHECKING:
    from Game import Game

from dev.logger import log_debug, set_log_level


class DebugConsole:
    """
    Consola de debug in-game superpuesta sobre el HUD.

    Se integra en Game: recibe eventos de pygame, actualiza el estado
    interno y se dibuja encima de todo lo demás.
    """

    # --- Paleta ---
    _BG_COLOR      = (10,  10, 20,  210)   # fondo del panel (semi-transparente)
    _BORDER_COLOR  = (80, 200, 255)         # borde cian
    _INPUT_BG      = (25,  25, 45,  230)   # fondo del campo de entrada
    _TEXT_COLOR    = (220, 240, 255)        # texto normal
    _ERROR_COLOR   = (255, 100, 100)        # mensajes de error
    _OK_COLOR      = (100, 255, 150)        # mensajes de éxito
    _PROMPT_COLOR  = (80,  200, 255)        # prefijo ">"
    _DIM_COLOR     = (140, 150, 165)        # texto de ayuda / atenuado

    PROMPT          = "> "
    MAX_OUTPUT      = 24                    # líneas máximas visibles en el buffer
    PANEL_HEIGHT_R  = 0.42                  # fracción de la altura de pantalla
    FONT_SIZE       = 15

    def __init__(self, game: "Game") -> None:
        self._game = game
        self.visible   = False
        self._input:   str   = ""
        self._output:  list[tuple[str, tuple[int, int, int]]] = []
        self._history: list[str] = []
        self._hist_idx: int = -1
        self._god_mode: bool = False

        pygame.font.init()
        # Intentar Consolas primero (Windows), luego Courier New, luego mono genérico
        self._font = pygame.font.SysFont("Consolas,Courier New,monospace", self.FONT_SIZE)

        # Registro de comandos: nombre -> handler(args) -> str | None
        self._commands: dict[str, Callable[[list[str]], str | None]] = {}
        self._register_commands()

        self._print("Consola de debug — escribe 'help' para ver los comandos.", self._DIM_COLOR)

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #

    def toggle(self) -> None:
        """Alterna la visibilidad de la consola."""
        self.visible = not self.visible
        self._input  = ""
        log_debug.debug("Consola %s", "abierta" if self.visible else "cerrada")

    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Procesa un evento de pygame.

        Retorna True si el evento fue consumido por la consola (y no debe
        propagarse al resto del juego).
        """
        if not self.visible:
            return False

        if event.type != pygame.KEYDOWN:
            return True   # la consola bloquea todos los eventos mientras está abierta

        key = event.key

        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._submit()
        elif key == pygame.K_BACKSPACE:
            self._input = self._input[:-1]
        elif key == pygame.K_UP:
            self._history_nav(-1)
        elif key == pygame.K_DOWN:
            self._history_nav(1)
        elif key == pygame.K_ESCAPE:
            self.visible = False
        elif key == pygame.K_TAB:
            self._autocomplete()
        else:
            char = event.unicode
            if char and char.isprintable():
                self._input += char

        return True

    def draw(self, surface: pygame.Surface) -> None:
        """Dibuja la consola encima de la pantalla si está visible."""
        if not self.visible:
            return

        sw, sh = surface.get_size()
        panel_h = int(sh * self.PANEL_HEIGHT_R)
        line_h  = self._font.get_height() + 2
        padding = 8
        input_h = line_h + padding

        # --- Fondo del panel ---
        overlay = pygame.Surface((sw, panel_h), pygame.SRCALPHA)
        overlay.fill(self._BG_COLOR)
        surface.blit(overlay, (0, 0))
        pygame.draw.rect(surface, self._BORDER_COLOR, (0, 0, sw, panel_h), 2)

        # --- Área de salida ---
        output_area_h   = panel_h - input_h - padding
        visible_lines   = max(1, output_area_h // line_h)
        lines_to_show   = self._output[-visible_lines:]

        y = padding
        for text, color in lines_to_show:
            surf = self._font.render(text, True, color)
            surface.blit(surf, (padding, y))
            y += line_h

        # --- Separador + campo de entrada ---
        input_y = panel_h - input_h
        pygame.draw.line(surface, self._BORDER_COLOR, (0, input_y), (sw, input_y), 1)

        input_bg = pygame.Surface((sw, input_h), pygame.SRCALPHA)
        input_bg.fill(self._INPUT_BG)
        surface.blit(input_bg, (0, input_y))

        # Cursor parpadeante: visible la mitad del tiempo (toggle cada ~0.5 s)
        cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        prompt_surf = self._font.render(
            self.PROMPT + self._input + cursor, True, self._PROMPT_COLOR
        )
        surface.blit(prompt_surf, (padding, input_y + padding // 2))

        # --- Indicador en esquina ---
        label = self._font.render("[F1] DEBUG", True, self._BORDER_COLOR)
        surface.blit(label, (sw - label.get_width() - padding, padding))

    # ------------------------------------------------------------------ #
    # Registro de comandos
    # ------------------------------------------------------------------ #

    def _register_commands(self) -> None:
        self._commands = {
            "help":     self._cmd_help,
            "spawn":    self._cmd_spawn,
            "set":      self._cmd_set,
            "teleport": self._cmd_teleport,
            "tp":       self._cmd_teleport,      # alias corto
            "clear":    self._cmd_clear,
            "god":      self._cmd_god,
            "hitboxes": self._cmd_hitboxes,
            "reload":   self._cmd_reload,
            "skip":     self._cmd_skip,
            "seed":     self._cmd_seed,
            "rooms":    self._cmd_rooms,
            "log":      self._cmd_log,
            "boss":     self._cmd_boss,
        }

    # ------------------------------------------------------------------ #
    # Implementación de cada comando
    # ------------------------------------------------------------------ #

    def _cmd_help(self, args: list[str]) -> None:
        lines = [
            "─── Comandos disponibles ─────────────────────────────────",
            "  spawn <tipo>          spawnea enemigo  (basic|fast|shooter|tank|faker|telefono|emoji)",
            "  set hp/gold/lives/speed <n>  modifica atributo del jugador",
            "  teleport <i> <j>      teletransporta a sala (i,j)  [alias: tp]",
            "  boss                  teletransporta directamente a la sala del boss",
            "  clear                 elimina enemigos de la sala actual",
            "  god                   toggle invulnerabilidad",
            "  hitboxes              toggle visualización de hitboxes de enemigos",
            "  reload                recarga todos los assets monitoreados",
            "  skip                  avanza al siguiente nodo del camino principal",
            "  seed                  muestra seed actual",
            "  rooms                 lista las salas del dungeon",
            "  log <nivel>           cambia nivel de log (DEBUG|INFO|WARNING|ERROR)",
            "  help                  muestra esta ayuda",
            "──────────────────────────────────────────────────────────",
        ]
        for line in lines:
            self._print(line, self._DIM_COLOR)

    def _cmd_spawn(self, args: list[str]) -> str:
        if not args:
            return "Uso: spawn <tipo>   (basic | fast | shooter | tank | faker | telefono | emoji)"

        # importación diferida para no crear ciclos
        from entities.Enemy import (
            BasicEnemy, FastChaserEnemy, ShooterEnemy, TankEnemy,
            FakerEnemy, TelefonoEnemy, EmojiEnemy
        )

        tipo_map: dict[str, type] = {
            "basic":    BasicEnemy,
            "fast":     FastChaserEnemy,
            "shooter":  ShooterEnemy,
            "tank":     TankEnemy,
            "faker":    FakerEnemy,
            "telefono": TelefonoEnemy,
            "emoji":    EmojiEnemy,
        }
        tipo = args[0].lower()
        cls  = tipo_map.get(tipo)
        if cls is None:
            return f"Tipo desconocido: '{tipo}'. Opciones: {', '.join(tipo_map)}"

        room = self._game.dungeon.current_room
        cx, cy = room.center_px()
        enemy = cls(float(cx), float(cy))
        room.enemies.append(enemy)
        log_debug.info(f"Spawneado {tipo} en ({cx}, {cy})")
        return f"OK — {tipo} spawneado en ({cx}, {cy})"

    def _cmd_set(self, args: list[str]) -> str:
        if len(args) < 2:
            return "Uso: set <hp | gold | lives | speed> <valor>"

        attr, val_str = args[0].lower(), args[1]
        try:
            val = int(val_str)
        except ValueError:
            return f"Valor inválido: '{val_str}' (debe ser entero)"

        player = self._game.player

        if attr == "hp":
            max_hp     = int(getattr(player, "max_hp", val))
            player.hp  = max(0, min(val, max_hp))
            return f"OK — HP → {player.hp}/{max_hp}"

        if attr == "gold":
            player.gold = max(0, val)
            return f"OK — Oro → {player.gold}"

        if attr == "lives":
            max_lives    = int(getattr(player, "max_lives", val))
            player.lives = max(0, min(val, max_lives))
            return f"OK — Vidas → {player.lives}/{max_lives}"

        if attr == "speed":
            player.speed = max(1, val)
            return f"OK — Velocidad → {player.speed} (solo esta run)"

        return f"Atributo desconocido: '{attr}'.  Opciones: hp, gold, lives, speed"

    def _cmd_teleport(self, args: list[str]) -> str:
        if len(args) < 2:
            return "Uso: teleport <i> <j>  (o tp <i> <j>)"
        try:
            i, j = int(args[0]), int(args[1])
        except ValueError:
            return "Coordenadas inválidas — deben ser enteros"

        dungeon = self._game.dungeon
        if (i, j) not in dungeon.rooms:
            sample = list(dungeon.rooms.keys())[:6]
            return f"Sala ({i},{j}) no existe. Ejemplos: {sample}"

        dungeon.i, dungeon.j = i, j
        dungeon.explored.add((i, j))

        room   = dungeon.current_room
        cx, cy = room.center_px()
        player = self._game.player
        player.x = float(cx) - player.w / 2.0
        player.y = float(cy) - player.h / 2.0

        self._game.projectiles.clear()
        self._game.enemy_projectiles.clear()

        depth = dungeon.depth_map.get((i, j), -1)
        log_debug.info(f"Teletransportado a ({i},{j}) profundidad={depth}")
        return f"OK — sala ({i},{j})  profundidad={depth}"

    def _cmd_boss(self, args: list[str]) -> str:
        """Teletransporta directamente a la sala del boss."""
        dungeon = self._game.dungeon

        # Buscar la sala del tipo "boss"
        boss_pos = None
        for pos, room in dungeon.rooms.items():
            if getattr(room, "type", "") == "boss":
                boss_pos = pos
                break

        if boss_pos is None:
            return "ERROR — no se encontró sala del boss"

        i, j = boss_pos
        dungeon.i, dungeon.j = i, j
        dungeon.explored.add((i, j))

        room = dungeon.current_room
        cx, cy = room.center_px()
        player = self._game.player
        player.x = float(cx) - player.w / 2.0
        player.y = float(cy) - player.h / 2.0

        self._game.projectiles.clear()
        self._game.enemy_projectiles.clear()

        depth = dungeon.depth_map.get((i, j), -1)
        log_debug.info(f"Teletransportado a sala del BOSS ({i},{j}) profundidad={depth}")
        return f"OK — sala del BOSS en ({i},{j})  profundidad={depth}"

    def _cmd_clear(self, args: list[str]) -> str:
        room  = self._game.dungeon.current_room
        count = len(getattr(room, "enemies", []))
        room.enemies = []
        if hasattr(room, "cleared"):
            room.cleared = True
        if hasattr(room, "locked"):
            room.locked = False
        return f"OK — {count} enemigo(s) eliminado(s)"

    def _cmd_god(self, args: list[str]) -> str:
        self._god_mode = not self._god_mode
        player = self._game.player
        # El flag es consultado cada frame en Game._update_player para
        # mantener el timer en alto sin tocar Player directamente.
        player._debug_god_mode = self._god_mode
        if self._god_mode:
            player.invulnerable_timer = 9999.0
        else:
            player.invulnerable_timer = 0.0
        estado = "ACTIVADO" if self._god_mode else "DESACTIVADO"
        log_debug.info(f"Modo dios {estado}")
        return f"Modo dios: {estado}"

    def _cmd_hitboxes(self, args: list[str]) -> str:
        from entities.Enemy import Enemy
        Enemy._debug_draw_hitboxes = not Enemy._debug_draw_hitboxes
        estado = "ACTIVADO" if Enemy._debug_draw_hitboxes else "DESACTIVADO"
        log_debug.info(f"Visualización de hitboxes {estado}")
        return f"Hitboxes: {estado}"

    def _cmd_reload(self, args: list[str]) -> str:
        watcher = getattr(self._game, "asset_watcher", None)
        if watcher is None:
            return "Error — AssetWatcher no inicializado"
        count = watcher.reload_all()
        return f"OK — {count} asset(s) recargado(s)"

    def _cmd_skip(self, args: list[str]) -> str:
        dungeon    = self._game.dungeon
        main_path  = getattr(dungeon, "main_path", [])
        if not main_path:
            return "No hay camino principal definido en este dungeon"

        current = (dungeon.i, dungeon.j)
        try:
            idx = main_path.index(current)
        except ValueError:
            idx = -1   # no estamos en el camino principal → ir al inicio

        next_idx = idx + 1
        if next_idx >= len(main_path):
            return "Ya estás en la última sala del camino principal"

        ni, nj = main_path[next_idx]
        dungeon.i, dungeon.j = ni, nj
        dungeon.explored.add((ni, nj))

        room   = dungeon.current_room
        cx, cy = room.center_px()
        player = self._game.player
        player.x = float(cx) - player.w / 2.0
        player.y = float(cy) - player.h / 2.0

        self._game.projectiles.clear()
        self._game.enemy_projectiles.clear()

        return f"OK — saltado a sala {(ni, nj)}  ({next_idx + 1}/{len(main_path)})"

    def _cmd_seed(self, args: list[str]) -> str:
        seed = getattr(self._game, "current_seed", "desconocida")
        return f"Seed actual: {seed}"

    def _cmd_rooms(self, args: list[str]) -> None:
        dungeon = self._game.dungeon
        rooms   = list(dungeon.rooms.keys())
        current = (dungeon.i, dungeon.j)

        self._print(f"Total de salas: {len(rooms)}  |  Actual: {current}", self._DIM_COLOR)
        for r in rooms:
            depth  = dungeon.depth_map.get(r, "?")
            on_mp  = "★" if r in getattr(dungeon, "main_path", []) else " "
            marker = " ← AQUÍ" if r == current else ""
            self._print(f"  {on_mp} {r}  prof={depth}{marker}")

    def _cmd_log(self, args: list[str]) -> str:
        if not args:
            return "Uso: log <DEBUG|INFO|WARNING|ERROR>"
        level = args[0].upper()
        valid = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if level not in valid:
            return f"Nivel inválido: '{args[0]}'. Opciones: {', '.join(sorted(valid))}"
        set_log_level(level)
        return f"OK — nivel de log → {level}"

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    def _submit(self) -> None:
        """Envía el comando actual, lo guarda en historial y lo ejecuta."""
        cmd_str = self._input.strip()
        self._input = ""
        if not cmd_str:
            return

        self._history.append(cmd_str)
        self._hist_idx = -1

        self._print(self.PROMPT + cmd_str, self._PROMPT_COLOR)
        log_debug.debug("Ejecutando: %s", cmd_str)
        self._execute(cmd_str)

    def _execute(self, cmd_str: str) -> None:
        parts  = cmd_str.split()
        if not parts:
            return
        name   = parts[0].lower()
        args   = parts[1:]
        handler = self._commands.get(name)

        if handler is None:
            self._print(
                f"Comando desconocido: '{name}'. Escribe 'help' para ver los disponibles.",
                self._ERROR_COLOR,
            )
            return

        try:
            result = handler(args)
            if result:
                is_error = result.lower().startswith("error") or result.lower().startswith("uso:")
                color    = self._ERROR_COLOR if is_error else self._OK_COLOR
                self._print(result, color)
        except Exception as exc:
            msg = f"Error interno ejecutando '{name}': {exc}"
            log_debug.error(msg)
            self._print(msg, self._ERROR_COLOR)

    def _print(
        self,
        text: str,
        color: tuple[int, int, int] | None = None,
    ) -> None:
        """Añade texto al buffer de salida, respetando el límite máximo."""
        if color is None:
            color = self._TEXT_COLOR
        for line in text.split("\n"):
            self._output.append((line, color))
        # Mantener el buffer dentro del límite
        if len(self._output) > self.MAX_OUTPUT:
            self._output = self._output[-self.MAX_OUTPUT:]

    def _history_nav(self, direction: int) -> None:
        """Navega el historial con flecha ↑ (direction=-1) o ↓ (direction=+1)."""
        if not self._history:
            return
        self._hist_idx = max(-1, min(len(self._history) - 1, self._hist_idx + direction))
        if self._hist_idx >= 0:
            self._input = self._history[-(self._hist_idx + 1)]
        else:
            self._input = ""

    def _autocomplete(self) -> None:
        """Autocompletado básico de nombres de comandos."""
        prefix  = self._input.split()[0].lower() if self._input.strip() else ""
        matches = [c for c in self._commands if c.startswith(prefix)]
        if len(matches) == 1:
            self._input = matches[0] + " "
        elif len(matches) > 1:
            self._print("  " + "  ".join(sorted(matches)), self._DIM_COLOR)
