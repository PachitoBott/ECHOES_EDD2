"""
Profesor Eduardo Ibarra — NPC hologramático de ECHOES.

Orientador universitario del mundo real que se proyecta como holograma
en la Red para guiar a Daniel Vega. Aparece como tienda especial:
antes de abrir el inventario obliga al jugador a responder una pregunta
educativa sobre ciberacoso.

Flujo de estado:
  IDLE  ->  (E)  ->  PREGUNTA  ->  (1/2/3)  ->  FEEDBACK  ->  (E/Enter/Space)  ->  ABRIR_TIENDA
  LISTO ->  (E)  ->  ABRIR_TIENDA  (pregunta ya respondida en esta sala)
"""
from __future__ import annotations
import math
import pygame


# ---------------------------------------------------------------------------
# Banco de preguntas (una por zona; agregar más aquí)
# ---------------------------------------------------------------------------
PREGUNTAS: list[dict] = [
    {
        "zona": 1,
        "texto": [
            "Si una publicación falsa sobre ti empieza a circular,",
            "¿qué es lo primero que deberías hacer?",
        ],
        "opciones": [
            "1. Compartirla para defenderte.",
            "2. Guardar capturas, enlaces y buscar apoyo.",
            "3. Responder atacando a todos.",
        ],
        "correcta": 1,   # índice 0-based → opción 2
        "feedback_correcto": [
            "Correcto. La evidencia y el apoyo son",
            "la mejor forma de empezar a defenderte.",
        ],
        "feedback_incorrecto": [
            "No exactamente. Responder con rabia puede empeorar la situación.",
            "Primero guarda pruebas y busca apoyo.",
        ],
    },
    {
        "zona": 2,
        "texto": [
            "Si ves que están atacando a alguien en redes,",
            "¿cuál es la mejor acción?",
        ],
        "opciones": [
            "1. Compartirlo porque todos lo están haciendo.",
            "2. Ignorarlo siempre.",
            "3. No compartir, reportar y apoyar a la persona afectada.",
        ],
        "correcta": 2,   # índice 0-based → opción 3
        "feedback_correcto": [
            "Bien. No todo se combate con fuerza.",
            "A veces la mejor defensa es guardar pruebas y pedir ayuda.",
        ],
        "feedback_incorrecto": [
            "Todavía estás reaccionando desde el miedo.",
            "Respira. Primero evidencia, luego apoyo, luego acción.",
        ],
    },
    {
        "zona": 0,   # Zona 0 = alternativa/comodín
        "texto": [
            "¿Por qué no deberías compartir una publicación",
            "ofensiva aunque parezca graciosa?",
        ],
        "opciones": [
            "1. Porque puedes ayudar a que el daño se vuelva más grande.",
            "2. Porque las redes se dañan.",
            "3. Porque pierdes monedas automáticamente.",
        ],
        "correcta": 0,   # índice 0-based → opción 1
        "feedback_correcto": [
            "Exacto. Compartir aumenta el alcance del daño.",
            "Detenerlo empieza por no propagarlo.",
        ],
        "feedback_incorrecto": [
            "No es eso. Compartir contenido ofensivo amplifica el daño",
            "real sobre la persona afectada.",
        ],
    },
]

RECOMPENSA_CORRECTA   = 15   # microchips de evidencia
RECOMPENSA_INCORRECTA = 5


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------
class ProfesorIbarra:
    """NPC hologramático del Profesor Eduardo Ibarra."""

    IDLE         = "idle"
    PREGUNTA     = "pregunta"
    FEEDBACK     = "feedback"
    ABRIR_TIENDA = "abrir_tienda"
    LISTO        = "listo"

    def __init__(self, pos: tuple[int, int], zona: int = 1) -> None:
        self.pos = pos
        cx, cy = pos
        self.rect = pygame.Rect(cx - 16, cy - 30, 32, 60)
        self.interact_radius = 28

        # Seleccionar pregunta por zona; cae al comodín si no hay
        candidates = [p for p in PREGUNTAS if p["zona"] == zona]
        self.pregunta: dict = candidates[0] if candidates else PREGUNTAS[0]

        self.estado            = self.IDLE
        self.pregunta_respondida = False
        self._feedback_lines: list[str] = []

        self._time      = 0.0
        self._last_tick = pygame.time.get_ticks()

    # ------------------------------------------------------------------
    # Interacción
    # ------------------------------------------------------------------
    def can_interact(self, player_rect) -> bool:
        if not isinstance(player_rect, pygame.Rect):
            try:
                player_rect = pygame.Rect(*player_rect)
            except Exception:
                return False
        area = self.rect.inflate(self.interact_radius * 2, self.interact_radius * 2)
        return area.colliderect(player_rect)

    def iniciar_interaccion(self) -> None:
        if self.pregunta_respondida:
            self.estado = self.ABRIR_TIENDA
        else:
            self.estado = self.PREGUNTA

    def responder(self, opcion_idx: int, player) -> None:
        """Registra la respuesta, otorga recompensa y cambia a FEEDBACK."""
        if opcion_idx == self.pregunta["correcta"]:
            reward = RECOMPENSA_CORRECTA
            lines  = list(self.pregunta["feedback_correcto"])
        else:
            reward = RECOMPENSA_INCORRECTA
            lines  = list(self.pregunta["feedback_incorrecto"])

        player.gold = getattr(player, "gold", 0) + reward
        lines.append("")
        lines.append(f"+{reward} microchips de evidencia.")
        lines.append("")
        lines.append("Ahora sí. Te enviaré algunos recursos desde el mundo real.")
        lines.append("(Presiona E, Enter o Espacio para abrir la tienda)")

        self._feedback_lines   = lines
        self.pregunta_respondida = True
        self.estado              = self.FEEDBACK

    def handle_event(self, ev: pygame.event.Event, player) -> None:
        """Procesa un evento dentro del estado activo del profesor."""
        if ev.type != pygame.KEYDOWN:
            return

        if self.estado == self.PREGUNTA:
            key_to_idx = {
                pygame.K_1: 0, pygame.K_KP1: 0,
                pygame.K_2: 1, pygame.K_KP2: 1,
                pygame.K_3: 2, pygame.K_KP3: 2,
            }
            idx = key_to_idx.get(ev.key)
            if idx is not None:
                self.responder(idx, player)

        elif self.estado == self.FEEDBACK:
            if ev.key in (pygame.K_e, pygame.K_RETURN, pygame.K_SPACE):
                self.estado = self.ABRIR_TIENDA

    def update(self) -> None:
        """Actualiza el timer interno del holograma."""
        now = pygame.time.get_ticks()
        self._time += (now - self._last_tick) / 1000.0
        self._last_tick = now

    # ------------------------------------------------------------------
    # Renderizado
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        self.update()
        self._draw_hologram(surface)
        if self.estado == self.PREGUNTA:
            self._draw_question_ui(surface, font)
        elif self.estado == self.FEEDBACK:
            self._draw_feedback_ui(surface, font)

    def draw_idle_hint(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        cx, cy = self.pos
        hint = font.render("E - Hablar con el Profesor Ibarra", True, (140, 210, 255))
        surface.blit(hint, (cx - hint.get_width() // 2, cy - 58))

    # --- hologram body ---
    def _draw_hologram(self, surface: pygame.Surface) -> None:
        t   = self._time
        cx, cy = self.pos

        alpha   = int(155 + 65 * math.sin(t * 3.7))
        flicker = int(18 * math.sin(t * 11.3))
        head_c  = (50 + flicker, 170 + flicker, 240)
        body_c  = (30 + flicker, 140 + flicker, 215)

        tmp = pygame.Surface((44, 72), pygame.SRCALPHA)

        # cabeza
        pygame.draw.circle(tmp, (*head_c, alpha), (22, 10), 9)
        # torso
        pygame.draw.rect(tmp, (*body_c, alpha), (14, 21, 16, 22))
        # brazos
        pygame.draw.rect(tmp, (*body_c, alpha), (5,  22, 9, 16))
        pygame.draw.rect(tmp, (*body_c, alpha), (30, 22, 9, 16))
        # piernas
        pygame.draw.rect(tmp, (*body_c, alpha), (14, 43, 7, 16))
        pygame.draw.rect(tmp, (*body_c, alpha), (23, 43, 7, 16))

        # scanlines horizontales
        scan_a = max(0, min(255, 65 + flicker))
        for yl in range(0, 72, 4):
            pygame.draw.line(tmp, (*head_c, scan_a), (0, yl), (43, yl))

        surface.blit(tmp, (cx - 22, cy - 36))

        # indicador de señal (parpadea)
        sig_a = int(175 + 80 * math.sin(t * 2.8))
        sig   = pygame.Surface((6, 6), pygame.SRCALPHA)
        pygame.draw.circle(sig, (120, 230, 255, sig_a), (3, 3), 3)
        surface.blit(sig, (cx + 16, cy - 44))

    # --- panel helper ---
    def _draw_panel(self, surface: pygame.Surface, pw: int, ph: int) -> tuple[int, int]:
        sw, sh = surface.get_size()
        px = max(4, sw // 2 - pw // 2)
        py = max(4, sh // 2 - ph // 2)
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((8, 16, 38, 218))
        pygame.draw.rect(panel, (65, 165, 255, 210), (0, 0, pw, ph), 2)
        surface.blit(panel, (px, py))
        return px, py

    # --- pregunta ---
    def _draw_question_ui(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        lh   = font.get_height() + 3
        rows = (1                               # nombre
                + 2                             # intro
                + len(self.pregunta["texto"])   # pregunta
                + len(self.pregunta["opciones"])# opciones
                + 1                             # hint teclas
                + 2)                            # padding
        ph = 14 + rows * lh
        pw = min(surface.get_width() - 8, 500)
        px, py = self._draw_panel(surface, pw, ph)

        y = py + 8
        surface.blit(
            font.render("Profesor Eduardo Ibarra:", True, (100, 200, 255)),
            (px + 10, y)); y += lh

        for line in [
            "Daniel, antes de comprar nada, necesito saber",
            "si estás entendiendo cómo sobrevivir a esto.",
        ]:
            surface.blit(font.render(line, True, (170, 210, 255)), (px + 10, y)); y += lh

        y += 3
        for line in self.pregunta["texto"]:
            surface.blit(font.render(line, True, (255, 255, 200)), (px + 10, y)); y += lh

        y += 3
        for opcion in self.pregunta["opciones"]:
            surface.blit(font.render(opcion, True, (210, 210, 148)), (px + 18, y)); y += lh

        y += 3
        surface.blit(
            font.render("Presiona 1, 2 o 3 para responder.", True, (130, 175, 130)),
            (px + 10, y))

    # --- feedback ---
    def _draw_feedback_ui(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        lh   = font.get_height() + 3
        rows = 1 + len(self._feedback_lines) + 1
        ph   = 14 + rows * lh
        pw   = min(surface.get_width() - 8, 500)
        px, py = self._draw_panel(surface, pw, ph)

        y = py + 8
        surface.blit(
            font.render("Profesor Eduardo Ibarra:", True, (100, 200, 255)),
            (px + 10, y)); y += lh

        for line in self._feedback_lines:
            color = (255, 225, 90) if line.startswith("+") else (185, 225, 255)
            surface.blit(font.render(line, True, color), (px + 10, y)); y += lh
