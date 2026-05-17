import random
import math
from collections import deque
from typing import Dict, Tuple, Set
from Config import CFG
from world.Room import Room
from data_structures.graph import Grafo

Vec = Tuple[int, int]
DIRS: Dict[str, Vec] = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}
DIRS_INV: Dict[Vec, str] = {(0, -1): "N", (0, 1): "S", (1, 0): "E", (-1, 0): "W"}

class Dungeon:
    """
    Generador procedural:
    - Grilla fija (por defecto 7x7) como límites “mundiales”.
    - Genera un camino principal conectado desde el centro.
    - Puede añadir ramas cortas con probabilidad.
    - Marca rooms explorados y define puertas según adyacencia.
    """
    def __init__(self,
                 grid_w: int = 7,
                 grid_h: int = 7,
                 main_len: int = 8,
                 branch_chance: float = 0.45,
                 branch_min: int = 2,
                 branch_max: int = 4,
                 seed: int | None = None,
                 corrupted_room_chance: float = 0.08,
                 corrupted_bonus_mode: str = "upgrade",
                 corrupted_chip_bonus: float = 0.5) -> None:
        if seed is not None:
            random.seed(seed)
        if seed is None:
            seed = random.randrange(0, 10**9)
        self.seed = seed
        random.seed(self.seed)    

        self.grid_w, self.grid_h = grid_w, grid_h
        self.i, self.j = grid_w // 2, grid_h // 2  # posición actual (empieza centro)
        self.start = (self.i, self.j)
        self.rooms: Dict[Tuple[int, int], Room] = {}
        self.explored: Set[Tuple[int, int]] = set()
        self.main_path: list[Tuple[int, int]] = []  # <<< NUEVO: orden del camino principal
        self.depth_map: Dict[Tuple[int, int], int] = {}
        # Grafo académico (Fase 2): representa la red de salas del dungeon.
        # Se construye en _build_grafo_y_depth_map() tras generar todas las salas.
        self.grafo: Grafo = Grafo(dirigido=False)

        # Etiquetado de zonas para la narrativa (Fase 5)
        # zones[pos] = 1 o 2 según la profundidad BFS desde el inicio
        self.zones: Dict[Tuple[int, int], int] = {}


        # 1) Camino principal
        self._generate_main_path(length=main_len)

        # 2) Ramas opcionales
        self._generate_branches(branch_chance, branch_min, branch_max)

        # Tabla de botín compartida para cofres del tesoro
        self._treasure_loot_table: list[dict] = [
            {"name": "Monedas desperdigadas (+20)", "type": "gold", "amount": 20, "weight": 8},
            {"name": "Bolsa de oro (+40)", "type": "gold", "amount": 40, "weight": 6},
            {"name": "Saco pesado de oro (+65)", "type": "gold", "amount": 65, "weight": 4},
            {"name": "Lingote antiguo (+120)", "type": "gold", "amount": 120, "weight": 2},
            {"name": "Vida extra (+1)", "type": "upgrade", "id": "hp_up", "weight": 5},
            {"name": "Blindaje reforzado (+1 golpe)", "type": "upgrade", "id": "armor_up", "weight": 3},
            {"name": "Talismán de recarga (-10%)", "type": "upgrade", "id": "cdr_charm", "weight": 4},
            {"name": "Aumento de velocidad (+5%)", "type": "upgrade", "id": "spd_up", "weight": 4},
            {"name": "Manual de puntería (-12% cd)", "type": "upgrade", "id": "cdr_core", "weight": 2},
            {"name": "Botas relámpago (+10% sprint)", "type": "upgrade", "id": "sprint_core", "weight": 3},
            {"name": "Condensador de fase (-15% dash)", "type": "upgrade", "id": "dash_core", "weight": 2},
            {"name": "Impulso cinético (+duración dash)", "type": "upgrade", "id": "dash_drive", "weight": 2},
            {"name": "Tónico curativo (+2 HP)", "type": "heal", "amount": 2, "weight": 3},
            {"name": "Viales reparadores (curación total)", "type": "consumable", "id": "heal_full", "weight": 2},
            {"name": "Ración de campaña (+1 HP)", "type": "consumable", "id": "heal_small", "amount": 1, "weight": 4},
            {"name": "Pistolas dobles", "type": "weapon", "id": "reportar", "weight": 1},
            {"name": "Rifle ligero", "type": "weapon", "id": "apoyo_amigo", "weight": 1},
            {"name": "Guantes tesla", "type": "weapon", "id": "evidencia", "weight": 1},
            {"name": "Carabina incandescente", "type": "weapon", "id": "modo_incognito", "weight": 0.8},
            {
                "name": "Fardo del aventurero",
                "type": "bundle",
                "contents": [
                    {"type": "gold", "amount": 55},
                    {"type": "consumable", "id": "heal_small", "amount": 1},
                    {"type": "upgrade", "id": "spd_up"},
                ],
                "weight": 3,
            },
            {
                "name": "Mapa arrugado del tesoro",
                "type": "bundle",
                "contents": [
                    {"type": "gold", "amount": 70},
                    {"type": "consumable", "id": "heal_medium", "amount": 2},
                ],
                "weight": 2,
            },
        ]

        # 3) Definir puertas según vecinos + tallar corredores
        self._link_neighbors_and_carve()

        # 4) Construir el grafo académico y calcular el mapa de profundidades
        #    El grafo modela cada sala como nodo y cada puerta como arista.
        #    bfs_con_distancias() reemplaza el BFS manual de _build_depth_map().
        self._build_grafo_y_depth_map()

        # 4.5) Asignar zonas narrativas (Fase 5) según profundidad BFS
        self._assign_zones()

        # <<< COMENTADO: la tienda antigua se reemplaza por Profesor Ibarra como único NPC de compra
        # self._place_shop_room()

        # <<< NUEVO: sala segura con Mara en Zona 2
        self._place_mara_safe_room()

        # <<< NUEVO: ubicar salas de tesoro en el recorrido
        self._place_treasure_rooms()

        # <<< NUEVO: sala del Profesor Ibarra (una en Zona 1, una en Zona 2)
        self._place_profesor_ibarra_rooms()

        # Obstáculos en salas hostiles
        self._populate_hostile_obstacles()


        # marcar inicial como explorado
        self.explored.add((self.i, self.j))
        

    # ------------------ API usada por Game ------------------ #
    @property
    def current_room(self) -> Room:
        return self.rooms[(self.i, self.j)]

    def can_move(self, direction: str) -> bool:
        di, dj = DIRS[direction]
        ni, nj = self.i + di, self.j + dj
        return (ni, nj) in self.rooms

    def move(self, direction: str) -> None:
        di, dj = DIRS[direction]
        ni, nj = self.i + di, self.j + dj
        if (ni, nj) in self.rooms:
            self.i, self.j = ni, nj
            self.explored.add((self.i, self.j))
    def room_depth(self, pos: Tuple[int, int] | None = None) -> int:
        """Devuelve la profundidad (pasos desde el inicio) para la sala dada."""
        if pos is None:
            pos = (self.i, self.j)
        return self.depth_map.get(pos, 0)

    def room_zone(self, pos: Tuple[int, int] | None = None) -> int:
        """Devuelve la zona narrativa (1, 2 o 3) para la sala dada."""
        if pos is None:
            pos = (self.i, self.j)
        return self.zones.get(pos, 1)

    def entry_position(self, came_from: str, pw: int, ph: int) -> tuple[float, float]:
        # reutiliza tu lógica actual (Dungeon no necesita cambiarla)
        room = self.current_room
        rx, ry, rw, rh = room.bounds
        ts = CFG.TILE_SIZE
        cx_px = (rx + rw // 2) * ts
        cy_px = (ry + rh // 2) * ts
        margin = 6
        if came_from == "N":
            return float(cx_px - pw//2), float((ry + rh) * ts - ph - 2 - margin)
        if came_from == "S":
            return float(cx_px - pw//2), float(ry * ts + 2 + margin)
        if came_from == "E":
            return float(rx * ts + 2 + margin), float(cy_px - ph//2)
        return float((rx + rw) * ts - pw - 2 - margin), float(cy_px - ph//2)

    # ------------------ Procedural interno ------------------ #
    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.grid_w and 0 <= y < self.grid_h

    def _neighbors(self, x: int, y: int) -> list[Vec]:
        return [(x+dx, y+dy) for dx,dy in DIRS.values() if self._in_bounds(x+dx, y+dy)]

    def _place_room(self, x: int, y: int) -> None:
        if (x, y) not in self.rooms:
            r = Room()
            # Tamaños aleatorios dentro del rango, ajustados al múltiplo de sprite
            def aligned_choices(min_size: int, max_size: int) -> list[int]:
                alignment = CFG.SPRITE_SIZE
                tile = CFG.TILE_SIZE
                factor = alignment // math.gcd(alignment, tile)
                choices = [value for value in range(min_size, max_size + 1) if value % factor == 0]
                return choices if choices else list(range(min_size, max_size + 1))

            width_choices = aligned_choices(CFG.ROOM_W_MIN, CFG.ROOM_W_MAX)
            height_choices = aligned_choices(CFG.ROOM_H_MIN, CFG.ROOM_H_MAX)

            rw = random.choice(width_choices)
            rh = random.choice(height_choices)

            r.build_centered(rw, rh)

            # Puertas se setean luego cuando enlaces vecinos (si ya lo haces)
            self.rooms[(x, y)] = r

    def _generate_main_path(self, length: int) -> None:
        x, y = self.i, self.j
        self._place_room(x, y)

        # <<< NUEVO: registra el inicio
        self.main_path.clear()
        self.main_path.append((x, y))

        last_dir: Vec | None = None

        for _ in range(max(1, length)):
            # Evitar retroceder inmediatamente para caminos más “limpios”
            choices = [d for d in DIRS.values() if last_dir is None or (d[0], d[1]) != (-last_dir[0], -last_dir[1])]
            random.shuffle(choices)
            moved = False
            for dx, dy in choices:
                nx, ny = x + dx, y + dy
                if not self._in_bounds(nx, ny):
                    continue
                # Evita “amontonarse”: no pises si ya hay 2+ vecinos ocupados (reduce cruces)
                occ_neighbors = sum((n in self.rooms) for n in self._neighbors(nx, ny))
                if occ_neighbors >= 3:
                    continue
                # Acepta
                x, y = nx, ny
                self._place_room(x, y)
                last_dir = (dx, dy)
                moved = True

                # <<< NUEVO: registra el paso aceptado
                self.main_path.append((x, y))
                break

            if not moved:
                # si no pudimos movernos por restricciones, relaja y prueba cualquier vecino válido
                for dx, dy in DIRS.values():
                    nx, ny = x + dx, y + dy
                    if self._in_bounds(nx, ny):
                        x, y = nx, ny
                        self._place_room(x, y)
                        last_dir = (dx, dy)

                        # <<< NUEVO: registra este fallback
                        self.main_path.append((x, y))
                        break

    def _generate_branches(self, chance: float, min_len: int, max_len: int) -> None:
        # para cada room del camino, hay probabilidad de crear una ramita corta
        anchors = list(self.rooms.keys())
        random.shuffle(anchors)
        for ax, ay in anchors:
            if random.random() > chance:
                continue
            length = random.randint(min_len, max_len)
            x, y = ax, ay
            last_dir: Vec | None = None
            for _ in range(length):
                # preferir direcciones que se alejen del ancla para “ramificarse”
                dirs = list(DIRS.values())
                random.shuffle(dirs)
                moved = False
                for dx, dy in dirs:
                    if last_dir and (dx, dy) == (-last_dir[0], -last_dir[1]):
                        continue
                    nx, ny = x + dx, y + dy
                    if not self._in_bounds(nx, ny):
                        continue
                    if (nx, ny) in self.rooms:
                        # si ya existe, corta la rama aquí para evitar bucles grandes
                        moved = False
                        break
                    # control suave de densidad
                    occ_neighbors = sum((n in self.rooms) for n in self._neighbors(nx, ny))
                    if occ_neighbors >= 3:
                        continue
                    self._place_room(nx, ny)
                    x, y = nx, ny
                    last_dir = (dx, dy)
                    moved = True
                    break
                if not moved:
                    break  # rama termina si no encuentra expansión segura

    def _link_neighbors_and_carve(self) -> None:
        # Define puertas según adyacencia real y talla corredores cortos
        for (x, y), room in self.rooms.items():
            # Puertas según vecinos existentes
            room.doors["N"] = (x, y-1) in self.rooms
            room.doors["S"] = (x, y+1) in self.rooms
            room.doors["W"] = (x-1, y) in self.rooms
            room.doors["E"] = (x+1, y) in self.rooms
            # Corredores visuales
            room.carve_corridors(width_tiles=2, length_tiles=3)
            
    def _build_grafo_y_depth_map(self) -> None:
        """
        Construye el grafo académico de salas y calcula el mapa de profundidades.

        Cada sala del dungeon se añade al Grafo como un nodo con metadata
        (tipo de sala).  Cada puerta entre dos salas adyacentes se añade
        como una arista de peso 1.0.

        El mapa de profundidades se obtiene directamente llamando a
        ``grafo.bfs_con_distancias(inicio)``, eliminando así el BFS manual
        que existía en _build_depth_map().
        """
        self.grafo = Grafo(dirigido=False)

        if self.start not in self.rooms:
            self.depth_map = {}
            return

        # 1) Añadir un nodo por cada sala con su tipo como metadato
        for pos, room in self.rooms.items():
            tipo = getattr(room, "type", "normal")
            es_inicio = (pos == self.start)
            self.grafo.agregar_nodo(pos, tipo=tipo, inicio=es_inicio)

        # 2) Añadir una arista por cada par de salas vecinas conectadas
        #    Recorremos sólo las cuatro direcciones canónicas para evitar
        #    agregar la misma arista dos veces (el Grafo lo maneja, pero
        #    es más claro así).
        visitadas_aristas: Set[Tuple[Tuple[int,int], Tuple[int,int]]] = set()
        for (x, y) in self.rooms:
            for dx, dy in DIRS.values():
                vecino = (x + dx, y + dy)
                if vecino in self.rooms:
                    par = (min((x, y), vecino), max((x, y), vecino))
                    if par not in visitadas_aristas:
                        visitadas_aristas.add(par)
                        self.grafo.agregar_arista((x, y), vecino, peso=1.0)

        # 3) El mapa de profundidades viene directo del BFS del grafo
        self.depth_map = self.grafo.bfs_con_distancias(self.start)

    def _assign_zones(self) -> None:
        """
        Asigna zonas narrativas a cada sala basándose en su profundidad BFS.

        Zona 1: distancia 0-3   (comentarios iniciales)
        Zona 2: distancia 4+    (viralización, incluye sala segura de Mara, el origen y confrontación)

        Los umbrales se pueden ajustar modificando las tuplas de rango aquí.
        """
        zona_ranges = [
            (1, 0, 3),    # (zona, dist_min, dist_max)
            (2, 4, float('inf')),  # Zona 2 llega hasta el final
        ]

        for pos, distancia in self.depth_map.items():
            zona = 1  # por defecto
            for z, d_min, d_max in zona_ranges:
                if d_min <= distancia <= d_max:
                    zona = z
                    break
            self.zones[pos] = zona

        # Log para debugging: contar salas por zona
        zona_counts = {1: 0, 2: 0}
        for zona in self.zones.values():
            zona_counts[zona] += 1

        import sys
        from dev.logger import log_game
        log_game.info(
            f"Zonas asignadas — Zona 1: {zona_counts[1]} salas, "
            f"Zona 2: {zona_counts[2]} salas"
        )

    def _place_shop_room(self) -> None:
        """
        Marca como 'shop' la sala ubicada aproximadamente a mitad del camino principal.
        Guarda también la posición en self.shop_pos para fácil acceso desde Game/Minimap.
        """
        if not self.main_path:
            return

        # Selecciona un punto del camino principal que no sea el inicio.
        # Usa el orden del camino para mantener una ubicación consistente
        # pero evita repetidos (puede haber retrocesos en la generación).
        unique_path: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for step in self.main_path:
            if step == self.start:
                continue
            if step in seen:
                continue
            seen.add(step)
            unique_path.append(step)

        # Si el camino sólo tiene el inicio (poco probable), cae a cualquier otra sala.
        if not unique_path:
            candidates = [pos for pos in self.rooms.keys() if pos != self.start]
            if not candidates:
                return
            sx, sy = random.choice(candidates)
        else:
            quarter_idx = max(0, len(unique_path) // 4)
            sx, sy = unique_path[quarter_idx]

        room = self.rooms.get((sx, sy))
        if not room:
            return

        # Marca de tipo (no rompe si Room no define 'type')
        setattr(room, "type", "shop")     # <<< etiqueta directa en Room
        self.shop_pos = (sx, sy)          # <<< guarda la coordenada para otras clases

    def _place_mara_safe_room(self) -> None:
        """
        Coloca una sala segura con Mara (NPC) en Zona 2.

        La sala segura es un lugar sin combate donde el jugador puede
        conversar con Mara sobre empatía y aislamiento digital.
        """
        if not hasattr(self, "zones"):
            return

        # Buscar salas en Zona 2
        zone2_rooms = [pos for pos in self.rooms.keys()
                       if self.room_zone(pos) == 2]

        # Evitar inicio y tienda
        forbidden = {self.start}
        if hasattr(self, "shop_pos"):
            forbidden.add(self.shop_pos)

        zone2_candidates = [pos for pos in zone2_rooms if pos not in forbidden]

        if not zone2_candidates:
            return

        # Seleccionar una sala aleatoria de Zona 2
        mara_pos = random.choice(zone2_candidates)
        room = self.rooms.get(mara_pos)

        if not room:
            return

        # Marcar como sala segura con Mara
        setattr(room, "type", "safe_mara")
        self.mara_pos = mara_pos

    def _place_treasure_rooms(self, max_rooms: int = 1, base_chance: float = 0.12) -> None:
        """Selecciona algunas salas y las convierte en cuartos del tesoro."""
        if not self.rooms:
            return

        forbidden = {self.start}
        if hasattr(self, "shop_pos"):
            forbidden.add(getattr(self, "shop_pos"))

        # Prioriza el camino principal para que aparezcan "entre" salas de combate
        main_candidates = [pos for pos in self.main_path if pos not in forbidden]
        branch_candidates = [pos for pos in self.rooms.keys() if pos not in forbidden and pos not in main_candidates]

        # Ordena candidatos por profundidad para diversificar
        def depth_of(pos: tuple[int, int]) -> int:
            return self.depth_map.get(pos, 0)

        main_candidates.sort(key=depth_of)
        branch_candidates.sort(key=depth_of)

        chosen: list[tuple[int, int]] = []

        rng = random.random
        for pos in main_candidates + branch_candidates:
            if len(chosen) >= max_rooms:
                break
            depth = depth_of(pos)
            if depth <= 0:
                continue
            chance = base_chance + 0.04 * min(depth, 5)
            if rng() > min(0.55, chance):
                continue
            chosen.append(pos)

        self.treasure_rooms: set[tuple[int, int]] = set()
        for pos in chosen:
            room = self.rooms.get(pos)
            if not room:
                continue
            if hasattr(room, "setup_treasure_room"):
                room.setup_treasure_room(list(self._treasure_loot_table))
                self.treasure_rooms.add(pos)

    def _populate_hostile_obstacles(self) -> None:
        if not self.rooms:
            return

        salt = 0xC0BB1E
        safe_types = {"shop", "treasure", "profesor_ibarra"}

        for pos, room in sorted(self.rooms.items()):
            if pos == self.start:
                continue
            rtype = getattr(room, "type", "normal")
            if rtype in safe_types:
                if hasattr(room, "clear_obstacles"):
                    room.clear_obstacles()
                continue
            if getattr(room, "no_spawn", False) or getattr(room, "safe", False):
                if hasattr(room, "clear_obstacles"):
                    room.clear_obstacles()
                continue
            if not hasattr(room, "generate_obstacles"):
                continue
            seed_value = (pos[0] * 73856093) ^ (pos[1] * 19349663) ^ self.seed ^ salt
            room_rng = random.Random(seed_value & 0xFFFFFFFF)
            room.generate_obstacles(rng=room_rng)
    # Dungeon.py (añade estos métodos)

    def _place_profesor_ibarra_rooms(self) -> None:
        """
        Coloca al Profesor Ibarra en UNA sola sala en Zona 1 (después de profesor).

        El profesor es la ÚNICA tienda del juego. Aparece una sola vez
        en el primer tercio de Zona 1 para enseñanza sobre ciberacoso.
        """
        if not hasattr(self, "zones"):
            return

        forbidden: set[tuple[int, int]] = {self.start}
        for attr in ("shop_pos", "mara_pos"):
            if hasattr(self, attr):
                forbidden.add(getattr(self, attr))

        # Buscar salas en Zona 1 (inicio a mediado)
        z1_candidates = [
            pos for pos in self.rooms
            if self.room_zone(pos) == 1 and pos not in forbidden
        ]

        if not z1_candidates:
            return

        # Ordenar por profundidad y tomar una sala del primer tercio-cuarto de Zona 1
        z1_candidates.sort(key=lambda p: self.depth_map.get(p, 0))
        pick_idx = max(0, min(len(z1_candidates) - 1, len(z1_candidates) // 3))
        profesor_pos = z1_candidates[pick_idx]

        room = self.rooms.get(profesor_pos)
        if room:
            setattr(room, "type", "profesor_ibarra")
            setattr(room, "_ibarra_zona", 1)
            self.ibarra_pos = profesor_pos

    def move_and_enter(self, direction: str, player, cfg, ShopkeeperCls=None) -> bool:
        """
        Mueve si se puede y dispara hooks de rooms.
        Devuelve True si se movió.
        """
        if not self.can_move(direction):
            return False

        # hook de salida
        cur_room = self.current_room
        if hasattr(cur_room, "on_exit"):
            cur_room.on_exit()

        # mover
        self.move(direction)

        # hook de entrada
        new_room = self.current_room
        if hasattr(new_room, "on_enter"):
            new_room.on_enter(player, cfg, ShopkeeperCls=ShopkeeperCls)

        return True

    def enter_initial_room(self, player, cfg, ShopkeeperCls=None):
        """Llama on_enter para la sala inicial (start)."""
        if hasattr(self.current_room, "on_enter"):
            self.current_room.on_enter(player, cfg, ShopkeeperCls=ShopkeeperCls)
            
