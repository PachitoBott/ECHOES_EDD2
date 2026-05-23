"""
ui/lobby_screen.py
==================
Pantalla de lobby que aparece al presionar JUGAR.
Muestra el estado de conexión de ambos jugadores
antes de iniciar la partida.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
import pygame


class PantallaLobby:
    """
    Pantalla de lobby que aparece al presionar JUGAR.
    Muestra el estado de conexión de ambos jugadores
    antes de iniciar la partida.
    """

    # Colores
    COLOR_CARD_BG = (12, 6, 18)
    COLOR_CARD_BORDER_P1 = (80, 0, 0)      # borde rojo P1
    COLOR_CARD_BORDER_P2 = (0, 60, 100)    # borde azul P2
    COLOR_LISTO = (0, 200, 80)             # verde
    COLOR_ESPERANDO = (80, 80, 100)        # gris
    COLOR_TITULO_P = (180, 120, 255)       # morado claro
    COLOR_TEXTO = (200, 180, 220)          # blanco cálido

    # Tamaños
    CARD_W = 280
    CARD_H = 320
    CARD_GAP = 60  # separación entre cards

    def __init__(
        self,
        logical_w: int,
        logical_h: int,
        fondo_menu: pygame.Surface | None = None,
        btn_asset: pygame.Surface | None = None,
        anim_p1: object = None,
    ) -> None:
        """
        Args:
            logical_w, logical_h: resolución lógica
            fondo_menu: surface del fondo del menú principal
            btn_asset: PNG del botón del menú (puede ser None)
            anim_p1: objeto Animation idle del jugador 1
        """
        self.lw = logical_w
        self.lh = logical_h
        self.fondo_menu = fondo_menu
        self.btn_asset = btn_asset
        self.anim_p1 = anim_p1

        # Si no se recibió animación, intentar cargarla desde assets
        if not self.anim_p1:
            self.anim_p1 = self._cargar_animacion_p1()

        # Estado
        self.p2_conectado = False
        # Cargar animación de P2 (Aliado/Cyborg) automáticamente
        self.anim_p2 = self._cargar_animacion_p2()
        self.resultado = None  # "jugar", "volver", None
        self.terminado = False

        # Efectos parpadeantes para "Esperando..."
        self.parpadeo_timer = 0.0
        self.parpadeo_vis = True

        # Rects de botones
        self.rect_btn_iniciar: pygame.Rect | None = None
        self.rect_btn_volver: pygame.Rect | None = None

        # Hover
        self.hover_iniciar = False
        self.hover_volver = False

        self._cargar_fuentes()
        self._calcular_layouts()

    def _cargar_animacion_p1(self) -> object | None:
        """Intenta cargar la animación idle de P1 desde los assets."""
        try:
            from systems.animation import AnimationManager

            json_path = "assets/sprites/player/animations.json"
            sprite_dir = "assets/sprites/player"
            animations = AnimationManager.load_from_json(json_path, sprite_dir)
            return animations.get("idle")
        except Exception as e:
            print(f"[LOBBY_SCREEN] Error cargando animación P1: {e}")
            return None

    def _cargar_animacion_p2(self) -> object | None:
        """Intenta cargar la animación idle de P2 desde los assets."""
        try:
            from systems.animation import AnimationManager

            json_path = "assets/sprites/player2/animations.json"
            sprite_dir = "assets/sprites/player2"
            animations = AnimationManager.load_from_json(json_path, sprite_dir)
            return animations.get("idle")
        except Exception as e:
            print(f"[LOBBY_SCREEN] Error cargando animación P2: {e}")
            return None

    def _cargar_fuentes(self) -> None:
        """Carga fuentes desde assets/ui."""
        base_path = Path(__file__).parent.parent.resolve()
        ui_path = base_path / "assets" / "ui"

        def _cargar_fuente(filename: str, size: int) -> pygame.font.Font:
            font_path = ui_path / filename
            if font_path.exists():
                try:
                    return pygame.font.Font(str(font_path), size)
                except Exception:
                    pass
            return pygame.font.SysFont("monospace", size, bold=True)

        self.font_titulo = _cargar_fuente("VT323-Regular.ttf", 36)   # Aumentado de 18
        self.font_nombre = _cargar_fuente("VT323-Regular.ttf", 28)   # Aumentado de 14
        self.font_estado = _cargar_fuente("VT323-Regular.ttf", 24)   # Aumentado de 12
        self.font_btn = _cargar_fuente("VT323-Regular.ttf", 32)      # Aumentado de 16

    def _calcular_layouts(self) -> None:
        """Calcula posiciones de cards y botones."""
        cx = self.lw // 2
        cy = self.lh // 2

        # Cards centradas
        total_w = self.CARD_W * 2 + self.CARD_GAP
        self.card_p1_x = cx - total_w // 2
        self.card_p1_y = cy - self.CARD_H // 2 - 20
        self.card_p2_x = self.card_p1_x + self.CARD_W + self.CARD_GAP
        self.card_p2_y = self.card_p1_y

        # Botones debajo de las cards
        btn_y_iniciar = self.card_p1_y + self.CARD_H + 30
        btn_y_volver = btn_y_iniciar + 60

        BTN_W = 280
        BTN_H = 48

        self.rect_btn_iniciar = pygame.Rect(
            cx - BTN_W // 2, btn_y_iniciar, BTN_W, BTN_H
        )
        self.rect_btn_volver = pygame.Rect(
            cx - BTN_W // 2, btn_y_volver, BTN_W, BTN_H
        )

    def set_p2_conectado(self, conectado: bool) -> None:
        """Llamar cuando el cliente se conecta o desconecta."""
        self.p2_conectado = conectado

    def set_p2_animacion(self, animacion) -> None:
        """Establece la animación idle de P2 para renderizar."""
        self.anim_p2 = animacion

    def update(self, dt: float) -> None:
        """Actualiza estado, animaciones y efectos parpadeantes."""
        # Actualizar animación P1
        if self.anim_p1:
            self.anim_p1.update(dt)

        # Actualizar animación P2
        if self.anim_p2:
            self.anim_p2.update(dt)

        # Efecto parpadeante "Esperando..."
        self.parpadeo_timer += dt
        if self.parpadeo_timer >= 0.6:
            self.parpadeo_timer = 0.0
            self.parpadeo_vis = not self.parpadeo_vis

        # Hover de botones
        mx, my = pygame.mouse.get_pos()
        self.hover_iniciar = (
            self.rect_btn_iniciar.collidepoint(mx, my)
            if self.rect_btn_iniciar
            else False
        )
        self.hover_volver = (
            self.rect_btn_volver.collidepoint(mx, my)
            if self.rect_btn_volver
            else False
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        """Maneja eventos del teclado y mouse."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if (
                self.rect_btn_iniciar
                and self.rect_btn_iniciar.collidepoint(mx, my)
            ):
                self.resultado = "jugar"
                self.terminado = True
            elif (
                self.rect_btn_volver
                and self.rect_btn_volver.collidepoint(mx, my)
            ):
                self.resultado = "volver"
                self.terminado = True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.resultado = "volver"
                self.terminado = True
            elif event.key == pygame.K_RETURN:
                self.resultado = "jugar"
                self.terminado = True

    def render(self, surface: pygame.Surface) -> None:
        """Renderiza la pantalla de lobby."""
        width, height = surface.get_size()

        # CAPA 1: Fondo del menú principal
        if self.fondo_menu:
            fondo_scaled = pygame.transform.smoothscale(
                self.fondo_menu, (width, height)
            )
            surface.blit(fondo_scaled, (0, 0))
        else:
            surface.fill((4, 2, 8))

        # CAPA 2: Overlay oscuro sutil
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 80))
        surface.blit(overlay, (0, 0))

        # CAPA 3: Título
        self._render_titulo(surface)

        # CAPA 4: Cards de jugadores
        self._render_card_p1(surface)
        self._render_card_p2(surface)

        # CAPA 5: Botones
        self._render_botones(surface)

    def _render_titulo(self, surface: pygame.Surface) -> None:
        """Renderiza título 'SELECCIÓN DE JUGADORES' arriba."""
        txt = self.font_titulo.render(
            "◈  SELECCIÓN DE JUGADORES  ◈", True, (150, 100, 200)
        )
        surface.blit(
            txt,
            (
                self.lw // 2 - txt.get_width() // 2,
                self.card_p1_y - 45,
            ),
        )

    def _render_card_p1(self, surface: pygame.Surface) -> None:
        """Card del Jugador 1 — siempre listo."""
        x = self.card_p1_x
        y = self.card_p1_y
        w = self.CARD_W
        h = self.CARD_H

        # Fondo card
        pygame.draw.rect(surface, self.COLOR_CARD_BG, (x, y, w, h))

        # Borde rojo P1
        pygame.draw.rect(surface, self.COLOR_CARD_BORDER_P1, (x, y, w, h), 2)
        pygame.draw.rect(surface, (40, 15, 15), (x + 2, y + 2, w - 4, h - 4), 1)

        # Header card
        HEADER_H = 30
        pygame.draw.rect(surface, (20, 8, 8), (x, y, w, HEADER_H))
        pygame.draw.line(
            surface,
            self.COLOR_CARD_BORDER_P1,
            (x, y + HEADER_H),
            (x + w, y + HEADER_H),
            1,
        )

        # Título P1
        txt_p1 = self.font_nombre.render("JUGADOR  1", True, (220, 100, 100))
        surface.blit(
            txt_p1,
            (x + w // 2 - txt_p1.get_width() // 2, y + HEADER_H // 2 - txt_p1.get_height() // 2),
        )

        # Sprite idle P1
        SPRITE_SIZE = 120
        sprite_x = x + w // 2 - SPRITE_SIZE // 2
        sprite_y = y + HEADER_H + 20

        if self.anim_p1:
            try:
                frame = self.anim_p1.current_frame()
                if frame and frame.get_size() != (1, 1):  # No es fallback vacío
                    frame_scaled = pygame.transform.scale(
                        frame, (SPRITE_SIZE, SPRITE_SIZE)
                    )
                    surface.blit(frame_scaled, (sprite_x, sprite_y))
                else:
                    self._render_sprite_placeholder(surface, sprite_x, sprite_y, SPRITE_SIZE, "P1")
            except Exception:
                self._render_sprite_placeholder(surface, sprite_x, sprite_y, SPRITE_SIZE, "P1")
        else:
            self._render_sprite_placeholder(surface, sprite_x, sprite_y, SPRITE_SIZE, "P1")

        # Indicador LISTO
        estado_y = sprite_y + SPRITE_SIZE + 15
        punto = self.font_estado.render("●", True, self.COLOR_LISTO)
        txt_listo = self.font_estado.render(" LISTO", True, self.COLOR_LISTO)
        total_w = punto.get_width() + txt_listo.get_width()
        px = x + w // 2 - total_w // 2
        surface.blit(punto, (px, estado_y))
        surface.blit(txt_listo, (px + punto.get_width(), estado_y))

        # Línea decorativa abajo
        pygame.draw.line(surface, (40, 15, 15), (x + 20, estado_y + 25), (x + w - 20, estado_y + 25), 1)

        # Texto "HOST" pequeño
        txt_host = self.font_estado.render("HOST", True, (80, 40, 40))
        surface.blit(
            txt_host,
            (x + w // 2 - txt_host.get_width() // 2, estado_y + 32),
        )

    def _render_card_p2(self, surface: pygame.Surface) -> None:
        """Card del Jugador 2 — listo si conectado, vacío si no."""
        x = self.card_p2_x
        y = self.card_p2_y
        w = self.CARD_W
        h = self.CARD_H

        # Fondo card
        bg_color = self.COLOR_CARD_BG if self.p2_conectado else (8, 6, 14)
        pygame.draw.rect(surface, bg_color, (x, y, w, h))

        # Borde — azul si conectado, gris si no
        border_color = (
            self.COLOR_CARD_BORDER_P2 if self.p2_conectado else (30, 25, 45)
        )
        pygame.draw.rect(surface, border_color, (x, y, w, h), 2)

        # Header card
        HEADER_H = 30
        header_color = (8, 15, 22) if self.p2_conectado else (10, 8, 15)
        pygame.draw.rect(surface, header_color, (x, y, w, HEADER_H))
        pygame.draw.line(
            surface,
            border_color,
            (x, y + HEADER_H),
            (x + w, y + HEADER_H),
            1,
        )

        # Título P2
        txt_color = (100, 160, 220) if self.p2_conectado else (60, 55, 80)
        txt_p2 = self.font_nombre.render("JUGADOR  2", True, txt_color)
        surface.blit(
            txt_p2,
            (x + w // 2 - txt_p2.get_width() // 2, y + HEADER_H // 2 - txt_p2.get_height() // 2),
        )

        SPRITE_SIZE = 120
        sprite_x = x + w // 2 - SPRITE_SIZE // 2
        sprite_y = y + HEADER_H + 20

        if self.p2_conectado:
            # Renderizar animación de P2 si existe, sino placeholder
            if self.anim_p2:
                try:
                    frame = self.anim_p2.current_frame()
                    if frame and frame.get_size() != (1, 1):  # No es fallback vacío
                        frame_scaled = pygame.transform.scale(
                            frame, (SPRITE_SIZE, SPRITE_SIZE)
                        )
                        surface.blit(frame_scaled, (sprite_x, sprite_y))
                    else:
                        self._render_sprite_placeholder(surface, sprite_x, sprite_y, SPRITE_SIZE, "P2")
                except Exception as e:
                    # Si hay error renderizando, mostrar placeholder
                    print(f"[LOBBY] Error renderizando P2: {e}")
                    self._render_sprite_placeholder(surface, sprite_x, sprite_y, SPRITE_SIZE, "P2")
            else:
                # No hay animación, mostrar placeholder
                self._render_sprite_placeholder(surface, sprite_x, sprite_y, SPRITE_SIZE, "P2")

            # Indicador LISTO
            estado_y = sprite_y + SPRITE_SIZE + 15
            punto = self.font_estado.render("●", True, self.COLOR_LISTO)
            txt_listo = self.font_estado.render(" LISTO", True, self.COLOR_LISTO)
            total_w2 = punto.get_width() + txt_listo.get_width()
            px = x + w // 2 - total_w2 // 2
            surface.blit(punto, (px, estado_y))
            surface.blit(txt_listo, (px + punto.get_width(), estado_y))

            pygame.draw.line(surface, (15, 30, 45), (x + 20, estado_y + 25), (x + w - 20, estado_y + 25), 1)
            txt_client = self.font_estado.render("CLIENTE", True, (30, 60, 80))
            surface.blit(
                txt_client,
                (x + w // 2 - txt_client.get_width() // 2, estado_y + 32),
            )
        else:
            # Slot vacío con animación parpadeante
            # Marco punteado
            for i in range(0, SPRITE_SIZE, 8):
                if (i // 8) % 2 == 0:
                    pygame.draw.line(
                        surface,
                        (40, 35, 55),
                        (sprite_x + i, sprite_y),
                        (sprite_x + min(i + 4, SPRITE_SIZE), sprite_y),
                        1,
                    )
                    pygame.draw.line(
                        surface,
                        (40, 35, 55),
                        (sprite_x + i, sprite_y + SPRITE_SIZE),
                        (sprite_x + min(i + 4, SPRITE_SIZE), sprite_y + SPRITE_SIZE),
                        1,
                    )
            for i in range(0, SPRITE_SIZE, 8):
                if (i // 8) % 2 == 0:
                    pygame.draw.line(
                        surface,
                        (40, 35, 55),
                        (sprite_x, sprite_y + i),
                        (sprite_x, sprite_y + min(i + 4, SPRITE_SIZE)),
                        1,
                    )
                    pygame.draw.line(
                        surface,
                        (40, 35, 55),
                        (sprite_x + SPRITE_SIZE, sprite_y + i),
                        (sprite_x + SPRITE_SIZE, sprite_y + min(i + 4, SPRITE_SIZE)),
                        1,
                    )

            # Signo + en el centro del slot vacío
            cx_slot = sprite_x + SPRITE_SIZE // 2
            cy_slot = sprite_y + SPRITE_SIZE // 2
            pygame.draw.line(surface, (50, 45, 65), (cx_slot - 15, cy_slot), (cx_slot + 15, cy_slot), 2)
            pygame.draw.line(surface, (50, 45, 65), (cx_slot, cy_slot - 15), (cx_slot, cy_slot + 15), 2)

            # Texto parpadeante "Esperando..."
            estado_y = sprite_y + SPRITE_SIZE + 15
            if self.parpadeo_vis:
                txt_esp = self.font_estado.render(
                    "○ Esperando jugador...", True, self.COLOR_ESPERANDO
                )
                surface.blit(
                    txt_esp,
                    (x + w // 2 - txt_esp.get_width() // 2, estado_y),
                )

    def _render_sprite_placeholder(
        self, surface: pygame.Surface, x: int, y: int, size: int, label: str
    ) -> None:
        """Renderiza un placeholder cuando no hay sprite disponible."""
        pygame.draw.rect(surface, (40, 20, 60), (x, y, size, size))
        txt = self.font_estado.render(label, True, (150, 100, 200))
        surface.blit(
            txt,
            (
                x + size // 2 - txt.get_width() // 2,
                y + size // 2 - txt.get_height() // 2,
            ),
        )

    def _render_botones(self, surface: pygame.Surface) -> None:
        """Renderiza los botones INICIAR y VOLVER."""
        if not self.rect_btn_iniciar or not self.rect_btn_volver:
            return

        # --- BOTÓN INICIAR PARTIDA ---
        r = self.rect_btn_iniciar

        if self.btn_asset:
            btn_scaled = pygame.transform.scale(self.btn_asset, (r.width, r.height))
            surface.blit(btn_scaled, r.topleft)
        else:
            # Fallback dibujado
            color_bg = (80, 0, 0) if self.hover_iniciar else (50, 0, 0)
            color_br = (200, 0, 0) if self.hover_iniciar else (120, 0, 0)
            pygame.draw.rect(surface, color_bg, r)
            pygame.draw.rect(surface, color_br, r, 2)

        txt_iniciar = self.font_btn.render(
            "▶  INICIAR PARTIDA",
            True,
            (255, 200, 200) if self.hover_iniciar else (200, 150, 150),
        )
        surface.blit(
            txt_iniciar,
            (
                r.centerx - txt_iniciar.get_width() // 2,
                r.centery - txt_iniciar.get_height() // 2,
            ),
        )

        # --- BOTÓN VOLVER ---
        rv = self.rect_btn_volver

        if self.btn_asset:
            btn_scaled2 = pygame.transform.scale(self.btn_asset, (rv.width, rv.height))
            btn_scaled2.set_alpha(180)
            surface.blit(btn_scaled2, rv.topleft)
        else:
            color_bg2 = (20, 15, 30) if self.hover_volver else (12, 8, 20)
            color_br2 = (60, 45, 80) if self.hover_volver else (35, 25, 50)
            pygame.draw.rect(surface, color_bg2, rv)
            pygame.draw.rect(surface, color_br2, rv, 1)

        txt_volver = self.font_btn.render(
            "←  VOLVER AL MENÚ",
            True,
            (160, 130, 200) if self.hover_volver else (100, 80, 130),
        )
        surface.blit(
            txt_volver,
            (
                rv.centerx - txt_volver.get_width() // 2,
                rv.centery - txt_volver.get_height() // 2,
            ),
        )


__all__ = ["PantallaLobby"]
