"""
accessibility/crash_guard.py
==============================
Utilidades de robustez para el game loop de Echoes.

Objetivo: evitar que un error en un subsistema (renderizado, narrativa,
red) derribe todo el proceso.  En lugar de propagar la excepcion,
se registra, se muestra un mensaje al jugador y el juego continua.

Herramientas
------------

  @safe_call
      Decorador para metodos/funciones que pueden fallar sin consecuencias
      criticas.  Si lanzan una excepcion, la loguea y retorna None.

  CrashGuard
      Clase que el game loop puede usar como contexto o llamando a
      run_safe() para envolver bloques de codigo.

  ErrorOverlay
      Superficie pygame semitransparente que muestra el ultimo error
      al jugador durante unos segundos (sin detener el juego).

Uso::

    from accessibility.crash_guard import safe_call, CrashGuard, ErrorOverlay

    overlay = ErrorOverlay(screen_w, screen_h)
    guard   = CrashGuard(on_error=overlay.mostrar)

    # Envolver bloque:
    with guard:
        nm.draw_cinematica(screen)

    # Decorador:
    @safe_call
    def cargar_nivel():
        ...

    # Game loop:
    overlay.tick(dt)
    overlay.draw(surface, screen_scale)
"""
from __future__ import annotations

import functools
import logging
import time
import traceback
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional, Type

try:
    import pygame
    _PYGAME_OK = True
except ImportError:
    _PYGAME_OK = False

_log = logging.getLogger("echoes.crash_guard")


# ---------------------------------------------------------------------------
# Decorador @safe_call
# ---------------------------------------------------------------------------

def safe_call(fn: Callable) -> Callable:
    """
    Decorador: si *fn* lanza cualquier excepcion, la loguea y retorna None.

    Uso::

        @safe_call
        def render_fancy():
            ...  # puede explotar sin matar el juego
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception:
            _log.error(
                "Error en %s:\n%s", fn.__qualname__, traceback.format_exc()
            )
            return None
    return wrapper


# ---------------------------------------------------------------------------
# CrashGuard — contexto
# ---------------------------------------------------------------------------

class CrashGuard:
    """
    Contexto que captura excepciones en bloques de codigo.

    Parametros
    ----------
    on_error : callable | None
        Funcion(mensaje: str) llamada cuando ocurre un error.
    excepciones : tuple de tipos
        Tipos de excepcion a capturar.  Por defecto: Exception (todas).
    relanzar : bool
        Si True, vuelve a lanzar la excepcion despues de loguear.
        Por defecto False (modo silencioso).
    """

    def __init__(
        self,
        on_error: Optional[Callable[[str], None]] = None,
        excepciones: tuple = (Exception,),
        relanzar: bool = False,
    ) -> None:
        self._on_error    = on_error
        self._excepciones = excepciones
        self._relanzar    = relanzar
        self.ultimo_error: Optional[str] = None

    def __enter__(self) -> "CrashGuard":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> bool:
        if exc_type is None:
            return False   # sin error
        if issubclass(exc_type, tuple(self._excepciones)):
            msg = f"{exc_type.__name__}: {exc_val}"
            self.ultimo_error = msg
            _log.error("CrashGuard capturó:\n%s", traceback.format_exc())
            if callable(self._on_error):
                try:
                    self._on_error(msg)
                except Exception:
                    pass
            return not self._relanzar   # True = suprimir, False = relanzar
        return False

    @contextmanager
    def zona(self, nombre: str = "") -> Generator:
        """
        Alternativa como generador con nombre de zona::

            with guard.zona("renderizado"):
                renderizar()
        """
        try:
            yield
        except tuple(self._excepciones) as exc:
            msg = f"[{nombre}] {type(exc).__name__}: {exc}"
            self.ultimo_error = msg
            _log.error("CrashGuard zona '%s':\n%s", nombre, traceback.format_exc())
            if callable(self._on_error):
                try:
                    self._on_error(msg)
                except Exception:
                    pass
            if self._relanzar:
                raise

    def run_safe(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Ejecuta fn(*args, **kwargs) con proteccion, retorna None si falla."""
        with self:
            return fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# ErrorOverlay — muestra el error en pantalla brevemente
# ---------------------------------------------------------------------------

_COL_BG_ERR  = (60, 0, 0, 200)
_COL_TEXTO   = (255, 180, 180)
_COL_TITULO  = (255, 100, 100)
_DURACION_DEFAULT = 5.0   # segundos


class ErrorOverlay:
    """
    Muestra un mensaje de error semitransparente en pantalla.

    El mensaje desaparece automaticamente despues de *duracion* segundos.

    Parametros
    ----------
    screen_w, screen_h : int
        Dimensiones logicas de la pantalla.
    duracion : float
        Segundos que el mensaje permanece visible.
    """

    def __init__(
        self,
        screen_w: int,
        screen_h: int,
        duracion: float = _DURACION_DEFAULT,
    ) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._duracion = duracion

        self._mensaje: Optional[str] = None
        self._inicio:  float = 0.0

        self._font: Any = None
        self._font_listo = False

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #

    def mostrar(self, mensaje: str) -> None:
        """Muestra *mensaje* en pantalla durante self._duracion segundos."""
        # Truncar si es demasiado largo
        self._mensaje = mensaje[:200] if len(mensaje) > 200 else mensaje
        self._inicio  = time.time()

    def tick(self, dt: float) -> None:
        """Elimina el mensaje si ya expiro."""
        if self._mensaje and time.time() - self._inicio >= self._duracion:
            self._mensaje = None

    def draw(self, surface: "pygame.Surface", screen_scale: int = 1) -> None:
        """Dibuja el mensaje si hay uno activo."""
        if not self._mensaje or not _PYGAME_OK:
            return

        self._init_font()
        w = surface.get_width()
        m = int(10 * screen_scale)

        # Fade-out en el ultimo segundo
        transcurrido = time.time() - self._inicio
        restante     = self._duracion - transcurrido
        alpha = 220
        if restante < 1.0:
            alpha = max(0, int(220 * restante))

        # Titulo
        tit = self._font.render("ERROR (el juego sigue)", True, _COL_TITULO)
        # Mensaje
        msg = self._font.render(self._mensaje[:90], True, _COL_TEXTO)

        total_h = tit.get_height() + msg.get_height() + 3 * m
        total_w = max(tit.get_width(), msg.get_width()) + 2 * m

        x = w // 2 - total_w // 2
        y = m

        bg = pygame.Surface((total_w, total_h), pygame.SRCALPHA)
        bg.fill(_COL_BG_ERR)
        bg.set_alpha(alpha)
        surface.blit(bg, (x, y))

        tit.set_alpha(alpha)
        msg.set_alpha(alpha)
        surface.blit(tit, (x + m, y + m))
        surface.blit(msg, (x + m, y + m + tit.get_height() + m // 2))

    @property
    def activo(self) -> bool:
        return self._mensaje is not None

    # ------------------------------------------------------------------ #

    def _init_font(self) -> None:
        if self._font_listo:
            return
        self._font = pygame.font.SysFont(None, max(12, 13))
        self._font_listo = True
