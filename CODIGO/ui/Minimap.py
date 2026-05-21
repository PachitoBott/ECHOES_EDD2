import pygame
from typing import Tuple, Set, Dict, List

class Minimap:
    """
    Renderiza el minimapa como un grafo de nodos conectados.
    Cada sala es un nodo circular, y las conexiones entre salas
    se representan como líneas que unen los nodos.

    La posición de cada nodo refleja la posición relativa de la sala
    en el mapa del juego.
    """

    # ====== Configuración de nodos ======
    NODE_RADIUS = 6                     # radio base de cada nodo
    NODE_RADIUS_CURRENT = 8             # radio del nodo actual (más grande)
    NODE_BORDER_WIDTH = 1               # grosor del borde

    # Colores de nodos
    NODE_COLOR_VISITED = (70, 70, 90)       # sala visitada
    NODE_COLOR_CURRENT = (255, 255, 255)    # sala actual (blanco)
    NODE_COLOR_UNVISITED = (25, 25, 35)     # no descubierta (muy oscuro)
    NODE_COLOR_SPECIAL = (220, 180, 0)      # sala especial (Mara, Boss, etc)
    NODE_COLOR_BORDER = (0, 0, 0)           # borde de nodos
    NODE_RING_COLOR = (255, 255, 255, 80)   # anillo exterior del nodo actual (semitransparente)
    NODE_RING_WIDTH = 1

    # ====== Configuración de aristas (conexiones) ======
    EDGE_COLOR = (45, 45, 60)           # color de líneas
    EDGE_COLOR_VISITED = (80, 80, 100)  # línea entre salas visitadas
    EDGE_WIDTH = 1                      # grosor de línea

    # ====== Configuración del minimapa ======
    MINIMAP_WIDTH = 180                 # ancho del minimapa en px lógicos
    MINIMAP_HEIGHT = 160                # alto del minimapa en px lógicos
    MINIMAP_MARGIN = 12                 # margen interno
    MINIMAP_BG_COLOR = (8, 8, 15)      # color de fondo
    MINIMAP_BG_ALPHA = 200              # semitransparencia
    MINIMAP_BG_BORDER_COLOR = (30, 30, 45)
    MINIMAP_BG_BORDER_WIDTH = 1

    # Salas especiales que siempre son visibles
    ALWAYS_VISIBLE_TYPES = {"shop", "boss", "profesor_ibarra"}

    def __init__(self, cell: int = 20, padding: int = 10) -> None:
        """
        Inicializa el minimapa.
        Los parámetros 'cell' y 'padding' se mantienen por compatibilidad
        pero no se usan en el nuevo sistema de grafo.
        """
        self.cell = cell
        self.padding = padding
        self._node_positions: Dict[Tuple[int, int], Tuple[int, int]] = {}

    def render(self, dungeon) -> pygame.Surface:
        """
        Renderiza el minimapa como un grafo de nodos.

        Args:
            dungeon: objeto del dungeon con rooms, explored, etc.

        Returns:
            Superficie con el minimapa renderizado
        """
        # Crear superficie con fondo semitransparente
        surf = pygame.Surface(
            (self.MINIMAP_WIDTH, self.MINIMAP_HEIGHT),
            pygame.SRCALPHA
        )

        # Fondo del minimapa
        surf.fill((self.MINIMAP_BG_COLOR[0], self.MINIMAP_BG_COLOR[1],
                   self.MINIMAP_BG_COLOR[2], self.MINIMAP_BG_ALPHA))
        pygame.draw.rect(
            surf,
            (*self.MINIMAP_BG_BORDER_COLOR, self.MINIMAP_BG_ALPHA),
            (0, 0, self.MINIMAP_WIDTH, self.MINIMAP_HEIGHT),
            self.MINIMAP_BG_BORDER_WIDTH
        )

        # Obtener datos del dungeon
        explored = getattr(dungeon, "explored", set())
        current_pos = (int(getattr(dungeon, "i", 0)), int(getattr(dungeon, "j", 0)))
        rooms = getattr(dungeon, "rooms", {})

        if not rooms:
            return surf

        # Calcular posiciones de nodos
        self._calcular_posiciones_nodos(rooms)

        # Dibujar aristas (conexiones entre nodos)
        self._dibujar_aristas(surf, rooms, explored, current_pos)

        # Dibujar nodos
        self._dibujar_nodos(surf, rooms, explored, current_pos)

        return surf

    def _calcular_posiciones_nodos(self, rooms: Dict[Tuple[int, int], any]) -> None:
        """
        Calcula la posición de cada nodo en el minimapa basándose
        en la posición relativa de la sala en el mapa del juego.
        """
        if not rooms:
            self._node_positions = {}
            return

        # Encontrar rango de coordenadas
        coords = list(rooms.keys())
        if not coords:
            self._node_positions = {}
            return

        min_x = min(c[0] for c in coords)
        max_x = max(c[0] for c in coords)
        min_y = min(c[1] for c in coords)
        max_y = max(c[1] for c in coords)

        range_x = max(1, max_x - min_x)
        range_y = max(1, max_y - min_y)

        # Normalizar y mapear al espacio del minimapa
        self._node_positions = {}
        for (grid_x, grid_y) in coords:
            norm_x = (grid_x - min_x) / range_x if range_x > 0 else 0.5
            norm_y = (grid_y - min_y) / range_y if range_y > 0 else 0.5

            # Mapear al espacio del minimapa con margen
            px = self.MINIMAP_MARGIN + norm_x * (self.MINIMAP_WIDTH - 2 * self.MINIMAP_MARGIN)
            py = self.MINIMAP_MARGIN + norm_y * (self.MINIMAP_HEIGHT - 2 * self.MINIMAP_MARGIN)

            self._node_positions[(grid_x, grid_y)] = (int(px), int(py))

    def _dibujar_aristas(self, surf: pygame.Surface, rooms: Dict,
                         explored: Set[Tuple[int, int]],
                         current_pos: Tuple[int, int]) -> None:
        """
        Dibuja las líneas de conexión entre nodos.
        Solo dibuja una arista si AMBOS nodos son visibles.
        """
        drawn_edges = set()

        for (grid_x, grid_y), room in rooms.items():
            # Si la sala no es visible, saltar
            if not self._es_visible(room, (grid_x, grid_y), explored):
                continue

            if (grid_x, grid_y) not in self._node_positions:
                continue

            pos1 = self._node_positions[(grid_x, grid_y)]

            # Obtener vecinos de la sala (si están disponibles)
            neighbors = getattr(room, "neighbors", [])
            if not neighbors:
                # Fallback: generar vecinos por proximidad
                neighbors = [
                    (grid_x + 1, grid_y),
                    (grid_x - 1, grid_y),
                    (grid_x, grid_y + 1),
                    (grid_x, grid_y - 1),
                ]

            for neighbor_pos in neighbors:
                # Solo dibujar si el vecino existe y es visible
                if neighbor_pos not in rooms:
                    continue
                if neighbor_pos not in self._node_positions:
                    continue

                neighbor_room = rooms[neighbor_pos]
                if not self._es_visible(neighbor_room, neighbor_pos, explored):
                    continue

                # Evitar dibujar la misma arista dos veces
                edge = tuple(sorted([(grid_x, grid_y), neighbor_pos]))
                if edge in drawn_edges:
                    continue
                drawn_edges.add(edge)

                pos2 = self._node_positions[neighbor_pos]

                # Elegir color: más brillante si ambos están explorados
                both_explored = (grid_x, grid_y) in explored and neighbor_pos in explored
                color = self.EDGE_COLOR_VISITED if both_explored else self.EDGE_COLOR

                # Dibujar línea
                pygame.draw.line(surf, color, pos1, pos2, self.EDGE_WIDTH)

    def _dibujar_nodos(self, surf: pygame.Surface, rooms: Dict,
                       explored: Set[Tuple[int, int]],
                       current_pos: Tuple[int, int]) -> None:
        """
        Dibuja los nodos (círculos) de las salas.
        """
        for (grid_x, grid_y), room in rooms.items():
            if (grid_x, grid_y) not in self._node_positions:
                continue

            # Determinar si es la sala actual
            is_current = (grid_x, grid_y) == current_pos

            # Determinar color del nodo
            color = self._obtener_color_nodo(room, (grid_x, grid_y), explored, is_current)

            # Determinar radio del nodo
            radius = self.NODE_RADIUS_CURRENT if is_current else self.NODE_RADIUS

            # Obtener posición
            pos = self._node_positions[(grid_x, grid_y)]

            # Dibujar nodo
            pygame.draw.circle(surf, color, pos, radius, 0)  # relleno
            pygame.draw.circle(surf, self.NODE_COLOR_BORDER, pos, radius, self.NODE_BORDER_WIDTH)

            # Si es la sala actual, dibujar anillo exterior
            if is_current:
                ring_radius = radius + 4
                ring_color = (self.NODE_RING_COLOR[0], self.NODE_RING_COLOR[1],
                             self.NODE_RING_COLOR[2], self.NODE_RING_COLOR[3])
                # Crear superficie con alpha para el anillo
                ring_surf = pygame.Surface((ring_radius * 2, ring_radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(ring_surf, ring_color, (ring_radius, ring_radius),
                                 ring_radius, self.NODE_RING_WIDTH)
                surf.blit(ring_surf, (pos[0] - ring_radius, pos[1] - ring_radius))

    def _es_visible(self, room, pos: Tuple[int, int],
                   explored: Set[Tuple[int, int]]) -> bool:
        """
        Determina si una sala debe ser visible en el minimapa.
        """
        room_type = getattr(room, "type", "normal")

        # Salas especiales siempre visibles
        if room_type in self.ALWAYS_VISIBLE_TYPES:
            return True

        # Salas normales solo visibles si fueron exploradas
        return pos in explored

    def _obtener_color_nodo(self, room, pos: Tuple[int, int],
                           explored: Set[Tuple[int, int]],
                           is_current: bool) -> Tuple[int, int, int]:
        """
        Devuelve el color del nodo según su tipo y estado.
        """
        room_type = getattr(room, "type", "normal")

        # La sala actual siempre es blanca
        if is_current:
            return self.NODE_COLOR_CURRENT

        # Salas especiales: color especial
        if room_type in self.ALWAYS_VISIBLE_TYPES:
            if room_type == "boss":
                return (220, 40, 40)  # rojo intenso para boss
            else:
                return (60, 200, 80)  # verde (shop, prof. ibarra)

        # Salas normales
        if pos in explored:
            return self.NODE_COLOR_VISITED
        else:
            return self.NODE_COLOR_UNVISITED
