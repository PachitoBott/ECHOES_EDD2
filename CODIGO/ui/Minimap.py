import pygame

class Minimap:
    def __init__(self, cell: int = 20, padding: int = 10) -> None:
        self.cell = cell
        self.padding = padding

        # Colores
        self.bg       = (20, 20, 20)
        self.border   = (255, 255, 255)
        self.grid     = (120, 120, 140)   # celdas no exploradas
        self.explored = (180, 180, 200)   # celdas exploradas
        self.current  = (255, 100, 100)   # posición del jugador
        self.shop_col     = (60, 200, 80)    # verde para tienda regular
        self.ibarra_col   = (60, 200, 80)    # verde para Profesor Ibarra (misma tienda)
        self.treasure_col = (130, 205, 255)  # azul claro para cofres
        self.boss_col     = (255, 130, 60)   # naranja intenso para boss
        self.mara_col     = (255, 200, 100)  # amarillo/dorado para sala de Mara

        # Salas especiales SIEMPRE visibles en el mapa (no requieren exploración)
        self._always_visible = {"safe_mara", "shop", "treasure", "boss", "profesor_ibarra"}

        # Opcional: mostrar icono $ sobre la tienda
        self.show_shop_icon = True
        self._font = None  # se inicializa lazy en render()

    def _get_font(self) -> pygame.font.Font:
        if self._font is None:
            # Tamaño proporcional a la celda
            size = max(10, int(self.cell * 0.75))
            self._font = pygame.font.SysFont(None, size)
        return self._font

    def render(self, dungeon) -> pygame.Surface:
        gw = int(getattr(dungeon, "grid_w", 3))
        gh = int(getattr(dungeon, "grid_h", 3))
        explored = getattr(dungeon, "explored", set())
        cur = (int(getattr(dungeon, "i", 0)), int(getattr(dungeon, "j", 0)))

        w = gw * self.cell + self.padding * 2
        h = gh * self.cell + self.padding * 2

        surf = pygame.Surface((w, h))  # opaco
        surf.fill(self.bg)
        pygame.draw.rect(surf, self.border, (0, 0, w, h), 2)

        # Cache de font si se va a usar el icono
        font = self._get_font() if self.show_shop_icon else None
        shop_glyph = None
        if font:
            shop_glyph = font.render("$", True, (10, 10, 10))  # sombra oscura
            shop_glyph2 = font.render("$", True, (255, 255, 255))  # brillo
        else:
            shop_glyph2 = None

        for j in range(gh):
            for i in range(gw):
                x = self.padding + i * self.cell
                y = self.padding + j * self.cell
                rect = pygame.Rect(x, y, self.cell - 2, self.cell - 2)

                # Base: color de grilla
                color = self.grid

                # Info de la sala (si existe)
                room = dungeon.rooms.get((i, j)) if hasattr(dungeon, "rooms") else None
                room_type = getattr(room, "type", "normal")

                # Salas especiales: SIEMPRE visibles aunque no hayan sido exploradas
                if room_type in self._always_visible:
                    if room_type == "safe_mara":
                        color = self.mara_col
                    elif room_type in ("shop", "profesor_ibarra"):
                        color = self.shop_col
                    elif room_type == "treasure":
                        color = self.treasure_col
                    elif room_type == "boss":
                        color = self.boss_col
                    else:
                        color = self.explored
                # Salas normales: solo visibles si fueron exploradas
                elif (i, j) in explored:
                    color = self.explored

                # Jugador actual sobreescribe el color
                if (i, j) == cur:
                    color = self.current

                # Dibujo del bloque
                pygame.draw.rect(surf, color, rect)

                # Icono de tienda (encima del rect), siempre visible para salas de tienda
                if self.show_shop_icon and room_type in ("shop", "profesor_ibarra"):
                    if shop_glyph and shop_glyph2:
                        # Centrar el texto en la celda
                        gx = rect.x + rect.w // 2
                        gy = rect.y + rect.h // 2
                        # Sombra leve
                        surf.blit(shop_glyph, shop_glyph.get_rect(center=(gx+1, gy+1)))
                        # Glifo principal
                        surf.blit(shop_glyph2, shop_glyph2.get_rect(center=(gx, gy)))

        return surf
