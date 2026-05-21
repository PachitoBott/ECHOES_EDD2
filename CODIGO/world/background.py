"""
Fondo animado estilo matrix con datos cayendo.
Se renderiza detrás de las salas del nivel.
"""

import pygame
import random
from dataclasses import dataclass, field


CHARS = list("0123456789#@%&*/\\|<!>?")


@dataclass
class Columna:
    """Representa una columna de caracteres cayendo."""
    x: int
    y: float
    velocidad: float
    longitud: int
    caracteres: list = field(default_factory=list)
    activa: bool = True
    timer_reset: float = 0.0
    char_timer: float = 0.0

    def __post_init__(self):
        self.caracteres = [
            random.choice(CHARS)
            for _ in range(self.longitud)
        ]


class MatrixBackground:
    """
    Fondo animado estilo matrix con datos cayendo.
    Paleta azul-morado oscuro.
    Se renderiza detrás de las salas del nivel.
    """

    # Paleta de colores
    COLOR_HEAD = (140, 100, 220)    # Cabeza de la columna (más brillante)
    COLOR_BRIGHT = (80, 60, 160)    # Mitad superior de la cola
    COLOR_MID = (40, 30, 100)       # Mitad inferior de la cola
    COLOR_TAIL = (20, 15, 55)       # Final de la cola (más oscuro)
    COLOR_BG = (4, 3, 12)           # Fondo base muy oscuro

    # Configuración
    CHAR_SIZE = 12                  # píxeles por carácter (ancho y alto)
    ALPHA = 150                     # opacidad global del fondo (0-255)

    def __init__(self, logical_w: int, logical_h: int):
        """Inicializa el fondo matrix.

        Args:
            logical_w: ancho lógico de la pantalla (antes de escalar)
            logical_h: alto lógico de la pantalla (antes de escalar)
        """
        self.w = logical_w
        self.h = logical_h
        self.columnas = []

        # Surface para renderizar el fondo
        self.surface = pygame.Surface(
            (logical_w, logical_h),
            pygame.SRCALPHA
        )

        # Fuente monoespaciada para los caracteres
        try:
            self.font = pygame.font.SysFont("monospace", 11)
        except Exception:
            self.font = pygame.font.Font(None, 12)

        self._init_columnas()

    def _init_columnas(self):
        """Genera todas las columnas con parámetros aleatorios."""
        num_columnas = self.w // self.CHAR_SIZE

        for i in range(num_columnas):
            # 50% de probabilidad de que la columna empiece activa
            activa = random.random() < 0.5

            col = Columna(
                x=i * self.CHAR_SIZE,
                y=random.uniform(-200, self.h) if activa else -random.uniform(50, 500),
                velocidad=random.uniform(60, 180),      # píxeles/segundo
                longitud=random.randint(5, 20),         # cantidad de caracteres
                activa=activa,
                timer_reset=0.0
            )
            self.columnas.append(col)

    def update(self, dt: float):
        """Actualiza posición y caracteres de todas las columnas.

        Args:
            dt: delta time en segundos desde el frame anterior
        """
        for col in self.columnas:
            if not col.activa:
                # Columna inactiva: esperar a que se reinicie
                col.timer_reset -= dt
                if col.timer_reset <= 0:
                    # Reiniciar la columna
                    col.y = -col.longitud * self.CHAR_SIZE
                    col.velocidad = random.uniform(60, 180)
                    col.longitud = random.randint(5, 20)
                    col.caracteres = [
                        random.choice(CHARS)
                        for _ in range(col.longitud)
                    ]
                    col.activa = True
                continue

            # Columna activa: mover hacia abajo
            col.y += col.velocidad * dt

            # Actualizar caracteres aleatoriamente
            col.char_timer += dt
            if col.char_timer >= random.uniform(0.1, 0.3):
                col.char_timer = 0
                idx = random.randint(0, len(col.caracteres) - 1)
                col.caracteres[idx] = random.choice(CHARS)

            # Verificar si llegó al fondo
            if col.y > self.h + col.longitud * self.CHAR_SIZE:
                col.activa = False
                col.timer_reset = random.uniform(0.5, 3.0)

    def render(self, target_surface: pygame.Surface):
        """Dibuja el fondo matrix completo sobre la superficie objetivo.

        Debe llamarse ANTES de dibujar salas, enemigos y jugador.

        Args:
            target_surface: superficie lógica donde dibujar (antes de escalar)
        """
        # Llenar el fondo con el color base
        self.surface.fill((*self.COLOR_BG, 255))

        # Dibujar todas las columnas activas
        for col in self.columnas:
            if col.activa:
                self._dibujar_columna(col)

        # Blit con opacidad reducida para que no compita con las salas
        self.surface.set_alpha(self.ALPHA)
        target_surface.blit(self.surface, (0, 0))

    def _dibujar_columna(self, col: Columna):
        """Dibuja una columna con su cola de caracteres.

        Args:
            col: objeto Columna a dibujar
        """
        for i, char in enumerate(col.caracteres):
            # Calcular posición Y del carácter
            char_y = col.y - i * self.CHAR_SIZE

            # Omitir caracteres fuera de pantalla
            if char_y < -self.CHAR_SIZE or char_y > self.h:
                continue

            # Obtener color según posición en la cola
            color = self._get_color(i, len(col.caracteres))

            # Parpadeo ocasional del carácter cabeza
            if i == 0 and random.random() < 0.1:
                char = random.choice(CHARS)

            # Renderizar y dibujar el carácter
            char_surface = self.font.render(char, False, color)
            self.surface.blit(
                char_surface,
                (col.x, int(char_y))
            )

    def _get_color(self, idx: int, total: int) -> tuple:
        """Devuelve el color del carácter según su posición en la cola.

        idx=0 es la cabeza (más brillante).
        idx=total-1 es el final (más oscuro).

        Args:
            idx: índice del carácter en la columna
            total: cantidad total de caracteres en la columna

        Returns:
            tupla RGB del color
        """
        if idx == 0:
            return self.COLOR_HEAD

        # Calcular ratio de posición (0 a 1)
        ratio = idx / max(1, total - 1)

        if ratio < 0.3:
            return self.COLOR_BRIGHT
        elif ratio < 0.6:
            return self.COLOR_MID
        else:
            return self.COLOR_TAIL
