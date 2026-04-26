"""
logger.py — Sistema de logging estructurado para Echoes.

Usa la librería estándar `logging` con salida coloreada en consola
(ANSI, compatible con Windows 10+) y etiquetas por categoría para
facilitar el debug durante el desarrollo.

Uso:
    from dev.logger import log_asset, log_game, log_room
    log_asset.info("Cargado: player.png")
    log_game.state_change("MENU", "JUGANDO")
    log_room.room_enter((5, 3), depth=2)
"""
from __future__ import annotations

import logging
import sys

# ---------------------------------------------------------------------------
# Habilitar ANSI en Windows (requiere Windows 10 build 14393+)
# ---------------------------------------------------------------------------

def _enable_windows_ansi() -> bool:
    """Activa VT100 en la consola de Windows para soportar colores ANSI."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle = kernel32.GetStdHandle(-11)   # STD_OUTPUT_HANDLE
        mode   = ctypes.c_ulong(0)
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        return True
    except Exception:
        return False


_ANSI_SUPPORTED = _enable_windows_ansi()

# ---------------------------------------------------------------------------
# Paleta de colores ANSI
# ---------------------------------------------------------------------------

_R  = "\033[0m"        # Reset
_B  = "\033[1m"        # Bold
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_GREEN  = "\033[32m"
_WHITE  = "\033[37m"
_GREY   = "\033[90m"
_MAGENTA = "\033[35m"

_LEVEL_COLORS: dict[str, str] = {
    "DEBUG":    _GREY,
    "INFO":     _CYAN,
    "WARNING":  _YELLOW,
    "ERROR":    _RED,
    "CRITICAL": _B + _RED,
}

_CATEGORY_COLORS: dict[str, str] = {
    "ASSET":  _GREEN,
    "ROOM":   _CYAN,
    "PLAYER": _WHITE,
    "ENEMY":  _RED,
    "NET":    _YELLOW,
    "GAME":   _MAGENTA,
    "DEBUG":  _GREY,
}


# ---------------------------------------------------------------------------
# Formateador con color
# ---------------------------------------------------------------------------

class _ColorFormatter(logging.Formatter):
    """Formateador de logging con etiquetas coloreadas por nivel y categoría."""

    def format(self, record: logging.LogRecord) -> str:
        level_color = _LEVEL_COLORS.get(record.levelname, "") if _ANSI_SUPPORTED else ""
        reset       = _R if _ANSI_SUPPORTED else ""

        cat = getattr(record, "category", "")
        if cat and _ANSI_SUPPORTED:
            cat_color = _CATEGORY_COLORS.get(cat, "")
            cat_tag   = f"{cat_color}[{cat}]{reset} "
        elif cat:
            cat_tag = f"[{cat}] "
        else:
            cat_tag = ""

        level_tag = f"{level_color}[{record.levelname}]{reset}"
        return f"{level_tag} {cat_tag}{record.getMessage()}"


# ---------------------------------------------------------------------------
# Configuración del logger raíz del juego
# ---------------------------------------------------------------------------

def _build_root_logger() -> logging.Logger:
    logger = logging.getLogger("echoes")
    if logger.handlers:
        return logger   # ya configurado; no duplicar handlers

    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ColorFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


_root_logger = _build_root_logger()


# ---------------------------------------------------------------------------
# GameLogger — wrapper por categoría
# ---------------------------------------------------------------------------

class GameLogger:
    """
    Logger etiquetado por categoría.

    Cada instancia añade automáticamente la etiqueta de su categoría
    a todos los mensajes sin necesidad de repetirla en el call-site.
    """

    def __init__(self, category: str = "") -> None:
        self._cat  = category.upper()
        self._log  = _root_logger

    # --- Helpers internos ---

    def _extra(self) -> dict:
        return {"category": self._cat}

    # --- Niveles estándar ---

    def debug(self, msg: str, *args) -> None:
        self._log.debug(msg, *args, extra=self._extra(), stacklevel=2)

    def info(self, msg: str, *args) -> None:
        self._log.info(msg, *args, extra=self._extra(), stacklevel=2)

    def warning(self, msg: str, *args) -> None:
        self._log.warning(msg, *args, extra=self._extra(), stacklevel=2)

    def error(self, msg: str, *args) -> None:
        self._log.error(msg, *args, extra=self._extra(), stacklevel=2)

    # --- Helpers semánticos para eventos frecuentes ---

    def asset_loaded(self, path: str) -> None:
        """Registra la carga exitosa de un asset."""
        self.info(f"Cargado: {path}")

    def asset_missing(self, path: str) -> None:
        """Registra que un asset no se encontró (se usará placeholder)."""
        self.warning(f"No encontrado (usando placeholder): {path}")

    def asset_error(self, path: str, exc: Exception) -> None:
        """Registra un error al cargar un asset."""
        self.error(f"Error cargando '{path}': {exc}")

    def state_change(self, from_state: str, to_state: str) -> None:
        """Registra una transición de estado del juego."""
        self.info(f"Transición: {from_state} → {to_state}")

    def room_enter(self, room_id: tuple, depth: int = -1) -> None:
        """Registra la entrada a una nueva sala."""
        depth_str = f" (profundidad {depth})" if depth >= 0 else ""
        self.info(f"Entrando sala {room_id}{depth_str}")


# ---------------------------------------------------------------------------
# Loggers globales listos para importar
# ---------------------------------------------------------------------------

log_asset  = GameLogger("ASSET")
log_game   = GameLogger("GAME")
log_room   = GameLogger("ROOM")
log_enemy  = GameLogger("ENEMY")
log_player = GameLogger("PLAYER")
log_net    = GameLogger("NET")
log_debug  = GameLogger("DEBUG")


def set_log_level(level: str | int) -> None:
    """
    Cambia el nivel de log global en tiempo de ejecución.

    Útil desde la consola de debug para silenciar o ampliar la salida.

    Ejemplos:
        set_log_level("WARNING")  # solo errores y advertencias
        set_log_level("DEBUG")    # todo
    """
    if isinstance(level, str):
        level = logging.getLevelName(level.upper())
    _root_logger.setLevel(level)
