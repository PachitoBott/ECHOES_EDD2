"""
accessibility/color_settings.py
=================================
Paletas de color y modos de contraste para Echoes.

Permite al jugador elegir entre varias combinaciones de color para mejorar
la visibilidad segun sus necesidades:

  "normal"          — paleta original del juego.
  "alto_contraste"  — blanco / negro / amarillo, maximo contraste.
  "daltonismo_rj"   — seguro para daltonismo rojo-verde (usa azules y naranjas).
  "daltonismo_az"   — seguro para daltonismo azul-amarillo (usa rojos y cianes).
  "oscuro_puro"     — fondos muy oscuros, texto blanco puro.

Uso desde Game.py::

    cs = ColorSettings()
    cs.aplicar("alto_contraste")

    col_jugador = cs.get("jugador")     # (R, G, B)
    col_enemigo = cs.get("enemigo")
    col_fondo   = cs.get("fondo")

Los nombres de clave son estandares; el juego debe usarlos en vez de
colores literales cuando renderiza entidades.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Tipo alias
# ---------------------------------------------------------------------------

Color = Tuple[int, int, int]


# ---------------------------------------------------------------------------
# Definicion de paletas
# ---------------------------------------------------------------------------

_PALETAS: Dict[str, Dict[str, Color]] = {
    "normal": {
        "jugador":       (100, 180, 255),
        "enemigo":       (220,  60,  60),
        "aliado":        ( 60, 220, 130),
        "npc":           ( 80, 160, 230),
        "fondo":         (  8,  12,  28),
        "pared":         ( 50,  55,  70),
        "suelo":         ( 28,  32,  45),
        "texto":         (230, 230, 230),
        "texto_nombre":  (100, 200, 255),
        "ui_borde":      ( 80, 120, 200),
        "ui_fondo":      ( 15,  20,  40),
        "item":          (255, 210,  60),
        "peligro":       (220,  50,  50),
        "curación":      ( 60, 200,  80),
        "apoyo":         ( 60, 180, 255),
    },
    "alto_contraste": {
        "jugador":       (255, 255,   0),   # amarillo
        "enemigo":       (255,   0,   0),   # rojo puro
        "aliado":        (  0, 255,   0),   # verde puro
        "npc":           (  0, 200, 255),   # cian
        "fondo":         (  0,   0,   0),   # negro puro
        "pared":         (200, 200, 200),   # gris claro
        "suelo":         ( 40,  40,  40),   # gris oscuro
        "texto":         (255, 255, 255),   # blanco puro
        "texto_nombre":  (  0, 255, 255),   # cian
        "ui_borde":      (255, 255, 255),
        "ui_fondo":      (  0,   0,   0),
        "item":          (255, 255,   0),
        "peligro":       (255,   0,   0),
        "curación":      (  0, 255,   0),
        "apoyo":         (  0, 200, 255),
    },
    "daltonismo_rj": {
        # Evita rojo-verde; usa azul y naranja
        "jugador":       ( 70, 130, 230),   # azul medio
        "enemigo":       (230, 130,  30),   # naranja
        "aliado":        (  0, 180, 220),   # cian oscuro
        "npc":           (130,  70, 230),   # violeta
        "fondo":         (  8,  12,  28),
        "pared":         ( 50,  55,  70),
        "suelo":         ( 28,  32,  45),
        "texto":         (230, 230, 230),
        "texto_nombre":  (130, 200, 255),
        "ui_borde":      ( 70, 130, 230),
        "ui_fondo":      ( 15,  20,  40),
        "item":          (200, 200,  60),
        "peligro":       (230, 130,  30),
        "curación":      (  0, 180, 220),
        "apoyo":         (130,  70, 230),
    },
    "daltonismo_az": {
        # Evita azul-amarillo; usa rojo y cian
        "jugador":       (200,  80, 180),   # magenta
        "enemigo":       (200,  50,  50),   # rojo
        "aliado":        (  0, 200, 200),   # cian
        "npc":           (180,  80, 200),   # violeta rosado
        "fondo":         (  8,  12,  28),
        "pared":         ( 50,  55,  70),
        "suelo":         ( 28,  32,  45),
        "texto":         (230, 230, 230),
        "texto_nombre":  (200, 150, 255),
        "ui_borde":      (200,  80, 180),
        "ui_fondo":      ( 15,  20,  40),
        "item":          (255, 180,  60),
        "peligro":       (200,  50,  50),
        "curación":      (  0, 200, 200),
        "apoyo":         (200,  80, 180),
    },
    "oscuro_puro": {
        "jugador":       (150, 200, 255),
        "enemigo":       (255, 100, 100),
        "aliado":        (100, 255, 160),
        "npc":           (120, 180, 255),
        "fondo":         (  0,   0,   0),
        "pared":         ( 30,  30,  30),
        "suelo":         ( 15,  15,  15),
        "texto":         (255, 255, 255),
        "texto_nombre":  (150, 220, 255),
        "ui_borde":      (100, 150, 220),
        "ui_fondo":      (  0,   0,   0),
        "item":          (255, 230, 100),
        "peligro":       (255, 100, 100),
        "curación":      (100, 255, 160),
        "apoyo":         (100, 200, 255),
    },
}

_PALETA_DEFAULT = "normal"


# ---------------------------------------------------------------------------
# ColorSettings
# ---------------------------------------------------------------------------

class ColorSettings:
    """
    Gestor de paletas de color con soporte para alto contraste y daltonismo.

    Parametros
    ----------
    paleta_inicial : str
        Nombre de la paleta a cargar al inicio.
    """

    def __init__(self, paleta_inicial: str = _PALETA_DEFAULT) -> None:
        self._nombre: str = _PALETA_DEFAULT
        self._paleta: Dict[str, Color] = dict(_PALETAS[_PALETA_DEFAULT])
        if paleta_inicial != _PALETA_DEFAULT:
            self.aplicar(paleta_inicial)

    # ------------------------------------------------------------------ #
    # API publica
    # ------------------------------------------------------------------ #

    def aplicar(self, nombre: str) -> bool:
        """
        Cambia la paleta activa.

        Retorna True si la paleta existe, False si no (no cambia nada).
        """
        if nombre not in _PALETAS:
            return False
        self._nombre  = nombre
        self._paleta  = dict(_PALETAS[nombre])
        return True

    def get(self, clave: str, fallback: Optional[Color] = None) -> Color:
        """
        Retorna el color de la clave en la paleta activa.

        Si la clave no existe, retorna *fallback* (o blanco si es None).
        """
        if clave in self._paleta:
            return self._paleta[clave]
        return fallback if fallback is not None else (255, 255, 255)

    def set_color(self, clave: str, color: Color) -> None:
        """Sobreescribe un color en la paleta activa (para personalizacion)."""
        self._paleta[clave] = color

    def exportar(self) -> Dict[str, Color]:
        """Retorna una copia del diccionario de colores actual."""
        return dict(self._paleta)

    # ------------------------------------------------------------------ #
    # Consultas
    # ------------------------------------------------------------------ #

    @property
    def nombre_paleta(self) -> str:
        return self._nombre

    @staticmethod
    def paletas_disponibles() -> List[str]:
        return list(_PALETAS.keys())

    @staticmethod
    def nombre_legible(nombre: str) -> str:
        nombres = {
            "normal":         "Normal",
            "alto_contraste": "Alto contraste",
            "daltonismo_rj":  "Daltonismo rojo-verde",
            "daltonismo_az":  "Daltonismo azul-amarillo",
            "oscuro_puro":    "Modo oscuro puro",
        }
        return nombres.get(nombre, nombre)

    def claves_disponibles(self) -> List[str]:
        return list(self._paleta.keys())

    def __getitem__(self, clave: str) -> Color:
        return self.get(clave)
