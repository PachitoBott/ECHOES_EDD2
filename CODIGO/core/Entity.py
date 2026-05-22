import pygame, math
from Config import CFG

class Entity:
    def __init__(self, x: float, y: float, w: int, h: int, speed: float) -> None:
        self.x, self.y, self.w, self.h, self.speed = x, y, w, h, speed
        self._proximity_threshold = 2.0  # distancia en píxeles para detectar proximidad

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def _get_proximity_distance_to_obstacles(self, room) -> tuple[float, str]:
        """
        Retorna la distancia mínima a obstáculos y la dirección.
        Retorna (distancia, dirección) donde dirección es 'x', 'y', o 'none'
        """
        if not hasattr(room, 'obstacles') or not room.obstacles:
            return (float('inf'), 'none')

        rect = self.rect()
        min_dist = float('inf')
        closest_axis = 'none'

        for obstacle in room.obstacles:
            obs_rect = obstacle["rect"]

            # Calcular distancia en X
            if rect.bottom > obs_rect.top and rect.top < obs_rect.bottom:
                dist_x = min(abs(rect.right - obs_rect.left), abs(rect.left - obs_rect.right))
                if dist_x < min_dist:
                    min_dist = dist_x
                    closest_axis = 'x'

            # Calcular distancia en Y
            if rect.right > obs_rect.left and rect.left < obs_rect.right:
                dist_y = min(abs(rect.bottom - obs_rect.top), abs(rect.top - obs_rect.bottom))
                if dist_y < min_dist:
                    min_dist = dist_y
                    closest_axis = 'y'

        return (min_dist, closest_axis)

    def move(self, dx: float, dy: float, dt: float, room) -> None:
        step_x = dx * self.speed * dt
        step_y = dy * self.speed * dt
        if step_x != 0:
            self.x += step_x
            if self._collides(room):
                self.x = self._resolve_axis(room, 'x', step_x > 0)
        if step_y != 0:
            self.y += step_y
            if self._collides(room):
                self.y = self._resolve_axis(room, 'y', step_y > 0)

    def _collides(self, room) -> bool:
        r = self.rect()
        x0, y0 = r.left // CFG.TILE_SIZE, r.top // CFG.TILE_SIZE
        x1, y1 = (r.right - 1) // CFG.TILE_SIZE, (r.bottom - 1) // CFG.TILE_SIZE
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                if room.is_blocked(tx, ty): return True
        return False

    def _resolve_axis(self, room, axis: str, positive: bool) -> float:
        r = self.rect()
        x0, y0 = r.left // CFG.TILE_SIZE, r.top // CFG.TILE_SIZE
        x1, y1 = (r.right - 1) // CFG.TILE_SIZE, (r.bottom - 1) // CFG.TILE_SIZE
        if axis == 'x':
            if positive:
                min_tx = None
                for ty in range(y0, y1 + 1):
                    for tx in range(x0, x1 + 1):
                        if room.is_blocked(tx, ty): min_tx = tx if min_tx is None else min(min_tx, tx)
                return self.x if min_tx is None else float(min_tx * CFG.TILE_SIZE - self.w)
            else:
                max_tx = None
                for ty in range(y0, y1 + 1):
                    for tx in range(x0, x1 + 1):
                        if room.is_blocked(tx, ty): max_tx = tx if max_tx is None else max(max_tx, tx)
                return self.x if max_tx is None else float((max_tx + 1) * CFG.TILE_SIZE)
        else:
            if positive:
                min_ty = None
                for ty in range(y0, y1 + 1):
                    for tx in range(x0, x1 + 1):
                        if room.is_blocked(tx, ty): min_ty = ty if min_ty is None else min(min_ty, ty)
                return self.y if min_ty is None else float(min_ty * CFG.TILE_SIZE - self.h)
            else:
                max_ty = None
                for ty in range(y0, y1 + 1):
                    for tx in range(x0, x1 + 1):
                        if room.is_blocked(tx, ty): max_ty = ty if max_ty is None else max(max_ty, ty)
                return self.y if max_ty is None else float((max_ty + 1) * CFG.TILE_SIZE)

    def draw(self, surf: pygame.Surface, color) -> None:
        pygame.draw.rect(surf, color, self.rect(), border_radius=2)
