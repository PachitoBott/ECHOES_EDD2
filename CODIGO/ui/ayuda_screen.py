"""
Sistema de pantalla de ayuda con navegación entre 30 mensajes.
Incluye fade animations, soporte emoji, y controles keyboard/mouse.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import pygame
import math


class PantallaAyuda:
    """Pantalla de ayuda con 30 mensajes rotativos y navegación."""

    # Colores (coinciden con PauseMenu)
    COLOR_CRIMSON = (210, 35, 55)
    COLOR_EMBER = (255, 110, 50)
    COLOR_DARK_BG = (8, 3, 6)
    COLOR_TEXT_WHITE = (230, 218, 218)
    COLOR_TEXT_DIM = (150, 150, 150)

    # Mensajes de ayuda (30 mensajes)
    MENSAJES = [
        # Mecánicas de combate
        "🎮 Usa WASD para moverte en todas direcciones. El movimiento es fluido y constante.",
        "🔫 Presiona IJKL para disparar: I=arriba, K=abajo, J=izquierda, L=derecha.",
        "💨 Usa SPACE para hacer un dash defensivo. Te hace invulnerable mientras te mueves rápido.",
        "🛡️ No se puede esquivar mientras disparas. Usa el movimiento para evadir proyectiles.",
        "⚡ Algunas armas disparan en múltiples direcciones. Experimenta con cada una.",

        # Recursos y mejoras
        "💎 Recolecta microchips dorados. Los necesitas para comprar mejoras en la tienda.",
        "🏪 El Mercader ofrece armas, salud y mejoras permanentes. Visita su tienda.",
        "❤️ Recoge corazones rojos para recuperar salud. Son raros, cuídalos.",
        "🔋 La munición se recarga automáticamente. No tienes que preocuparte por ella.",
        "⭐ Los enemigos de élite sueltan mejores recompensas. Enfócate en ellos.",

        # Estrategia y enemigos
        "🤖 Los enemigos rojos (Zona 1) son más lentos. Fáciles para principiantes.",
        "🟣 Los enemigos morados (Zona 2) son rápidos y peligrosos. Ten cuidado.",
        "🔄 Los enemigos apuntan y disparan en patrón. Aprende sus ritmos.",
        "🎯 Prioriza a los enemigos que disparan a distancia. Son más peligrosos.",
        "💥 Algunos barriles rojos explotan. Úsalos para dañar enemigos a distancia.",

        # Jefes y progresión
        "👹 Cada zona tiene un jefe único con ataques telegráfiados. Aprende sus patrones.",
        "⏱️ Los jefes tienen fases de ataque predecibles. Memoriza los tiempos.",
        "🌊 Mantén distancia de los bordes. Los ataques pueden cubrir el área completamente.",
        "🎪 Algunos jefes tienen área de efecto. Necesitas movimiento rápido y preciso.",
        "🏆 Vence jefes para avanzar a nuevas zonas con enemigos más fuertes.",

        # Educación sobre ciberacoso
        "📱 El ciberacoso es acoso real. Las palabras en internet lastiman de verdad.",
        "🚫 Si ves acoso en línea, no lo ignores. Reporta y apoya a la víctima.",
        "💬 Sé respetuoso en línea como serías en persona. El anonimato no excusa.",
        "🤝 Trata a otros jugadores como quieres ser tratado. La comunidad es mejor juntos.",
        "⚠️ Si alguien te acosa, guarda pruebas y reporta. No estás solo.",

        # Tips avanzados
        "🎨 Distintas armas tienen velocidades diferentes. Elige según tu playstyle.",
        "🔐 Algunos cofres contienen trampa. Pueden ser enemigos en disfraz.",
        "🌙 Los patrones enemigos cambian en fases. Mantente atento a cambios.",
        "🎵 El sonido te advierte de enemigos fuera de pantalla. Mantén volumen alto.",
        "🏃 La velocidad es defensa. Mantente en movimiento constante.",
    ]

    def __init__(self, screen: pygame.Surface, font_path: Optional[str] = None) -> None:
        self.screen = screen
        self.width, self.height = screen.get_size()
        self.clock = pygame.time.Clock()

        # Fuentes
        self.title_font = self._load_font(font_path or "VT323-Regular.ttf", 64)
        self.message_font = self._load_font(font_path or "VT323-Regular.ttf", 32)
        self.nav_font = self._load_font(font_path or "VT323-Regular.ttf", 24)

        # Estado
        self.current_index = 0
        self.fade_alpha = 0  # Para efecto fade in
        self.fade_in_duration = 0.3  # segundos
        self.fade_timer = 0.0
        self.fading_in = True

    def _load_font(self, font_name: str, size: int) -> pygame.font.Font:
        """Carga fuente o usa sistema si no existe."""
        candidates = [
            Path(__file__).parent / "assets" / "ui" / font_name,
            Path(__file__).parent / ".." / "assets" / "ui" / font_name,
            Path.cwd() / "assets" / "ui" / font_name,
        ]
        for path in candidates:
            if path.exists():
                try:
                    return pygame.font.Font(str(path), size)
                except pygame.error:
                    pass
        return pygame.font.SysFont("consolas", int(size * 0.7))

    def _get_current_message(self) -> str:
        """Obtiene el mensaje actual."""
        return self.MENSAJES[self.current_index % len(self.MENSAJES)]

    def next_message(self) -> None:
        """Avanza al próximo mensaje."""
        self.current_index = (self.current_index + 1) % len(self.MENSAJES)
        self._reset_fade()

    def prev_message(self) -> None:
        """Retrocede al mensaje anterior."""
        self.current_index = (self.current_index - 1) % len(self.MENSAJES)
        self._reset_fade()

    def _reset_fade(self) -> None:
        """Reinicia el efecto fade in."""
        self.fade_alpha = 0
        self.fade_timer = 0.0
        self.fading_in = True

    def update(self, dt: float) -> None:
        """Actualiza animaciones."""
        if self.fading_in:
            self.fade_timer += dt
            if self.fade_timer >= self.fade_in_duration:
                self.fade_alpha = 255
                self.fading_in = False
            else:
                ratio = self.fade_timer / self.fade_in_duration
                self.fade_alpha = int(255 * ratio)

    def draw(self, surface: pygame.Surface) -> None:
        """Renderiza la pantalla de ayuda."""
        self.update(self.clock.get_time() / 1000.0)

        width, height = surface.get_size()

        # Fondo oscuro con overlay
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))

        # Caja principal
        box_width = min(800, width - 80)
        box_height = 500
        box_rect = pygame.Rect(0, 0, box_width, box_height)
        box_rect.center = (width // 2, height // 2)

        # Dibujar caja con borde
        pygame.draw.rect(surface, (20, 10, 10), box_rect, border_radius=16)
        pygame.draw.rect(surface, self.COLOR_CRIMSON, box_rect, 4, border_radius=16)

        # Título
        title_surf = self.title_font.render("AYUDA", True, self.COLOR_EMBER)
        title_rect = title_surf.get_rect(centerx=box_rect.centerx, y=box_rect.top + 30)
        surface.blit(title_surf, title_rect)

        # Contador (Mensaje X / Total)
        counter_text = f"[{self.current_index + 1}/{len(self.MENSAJES)}]"
        counter_surf = self.nav_font.render(counter_text, True, self.COLOR_TEXT_DIM)
        counter_rect = counter_surf.get_rect(
            centerx=box_rect.centerx,
            y=title_rect.bottom + 10
        )
        surface.blit(counter_surf, counter_rect)

        # Mensaje con fade in
        message = self._get_current_message()
        self._draw_wrapped_text(
            surface,
            message,
            self.message_font,
            box_rect,
            self.fade_alpha
        )

        # Botones de navegación (< | >)
        nav_y = box_rect.bottom - 60
        self._draw_nav_buttons(surface, box_rect.centerx, nav_y)

        # Instrucción
        hint_surf = self.nav_font.render(
            "[ FLECHAS o A/D | ESC PARA CERRAR ]",
            True,
            self.COLOR_TEXT_DIM
        )
        hint_rect = hint_surf.get_rect(
            centerx=box_rect.centerx,
            y=box_rect.bottom - 30
        )
        surface.blit(hint_surf, hint_rect)

    def _draw_wrapped_text(
        self,
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        box_rect: pygame.Rect,
        alpha: int
    ) -> None:
        """Dibuja texto con word wrapping y alpha."""
        # Calcular ancho disponible
        available_width = box_rect.width - 60

        # Word wrap
        words = text.split(' ')
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            if font.size(test_line)[0] <= available_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        # Renderizar líneas
        start_y = box_rect.top + 120
        line_height = 50

        for line in lines:
            line_surf = font.render(line, True, self.COLOR_TEXT_WHITE)
            line_surf.set_alpha(alpha)

            line_rect = line_surf.get_rect(
                centerx=box_rect.centerx,
                y=start_y
            )
            surface.blit(line_surf, line_rect)
            start_y += line_height

    def _draw_nav_buttons(
        self,
        surface: pygame.Surface,
        center_x: int,
        y: int
    ) -> None:
        """Dibuja botones de navegación < y >."""
        button_size = 50
        button_spacing = 100

        # Botón izquierdo
        left_rect = pygame.Rect(
            center_x - button_spacing - button_size // 2,
            y - button_size // 2,
            button_size,
            button_size
        )
        pygame.draw.rect(surface, self.COLOR_CRIMSON, left_rect, border_radius=8)
        pygame.draw.rect(surface, self.COLOR_EMBER, left_rect, 2, border_radius=8)

        left_text = self.nav_font.render("<", True, self.COLOR_TEXT_WHITE)
        left_text_rect = left_text.get_rect(center=left_rect.center)
        surface.blit(left_text, left_text_rect)

        # Botón derecho
        right_rect = pygame.Rect(
            center_x + button_spacing - button_size // 2,
            y - button_size // 2,
            button_size,
            button_size
        )
        pygame.draw.rect(surface, self.COLOR_CRIMSON, right_rect, border_radius=8)
        pygame.draw.rect(surface, self.COLOR_EMBER, right_rect, 2, border_radius=8)

        right_text = self.nav_font.render(">", True, self.COLOR_TEXT_WHITE)
        right_text_rect = right_text.get_rect(center=right_rect.center)
        surface.blit(right_text, right_text_rect)

        # Guardar rects para detección de clics
        self._left_button_rect = left_rect
        self._right_button_rect = right_rect

    def handle_input(self, events: list) -> bool:
        """
        Procesa eventos de input.
        Retorna True si debe cerrar la pantalla (ESC presionado).
        """
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return True
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    self.prev_message()
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    self.next_message()

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if hasattr(self, '_left_button_rect') and self._left_button_rect.collidepoint(event.pos):
                    self.prev_message()
                elif hasattr(self, '_right_button_rect') and self._right_button_rect.collidepoint(event.pos):
                    self.next_message()

        return False

    def run(self) -> None:
        """Loop principal de la pantalla de ayuda."""
        running = True
        while running:
            self.clock.tick(60)

            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    return

            if self.handle_input(events):
                return

            self.update(self.clock.get_time() / 1000.0)
            self.draw(self.screen)
            pygame.display.flip()
