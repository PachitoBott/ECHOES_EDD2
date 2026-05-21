"""
Gestor de tilesets con caché y soporte para múltiples tilesets por zona.
Cada tileset se carga una sola vez y se reutiliza.
"""

import os
import pygame
from typing import Dict, Optional
from Config import CFG
from core.Tileset import Tileset


# Mapeo de zona → ruta de tileset
ZONE_TILESETS = {
    1: "assets/tileset_temporal.png",   # Zona 1
    2: "assets/tileset_temporal2.png",  # Zona 2
    3: "assets/tileset_temporal2.png",  # Zona 3 (mismo que Zona 2)
}


class TilesetManager:
    """
    Gestor centralizado de tilesets.
    Carga cada tileset una sola vez y mantiene un caché.
    """

    def __init__(self):
        """Inicializa el gestor con caché vacío."""
        self._cache: Dict[str, Tileset] = {}
        self._current_zone: int = 1
        self._current_tileset: Optional[Tileset] = None
        # Cargar tileset por defecto de Zona 1
        self._load_and_cache_default()

    def _load_and_cache_default(self) -> None:
        """Carga y cachea el tileset por defecto de Zona 1."""
        default_path = ZONE_TILESETS[1]
        if default_path not in self._cache:
            tileset = self._load_tileset(default_path)
            self._cache[default_path] = tileset
            self._current_tileset = tileset

    def get_tileset_for_zone(self, zone: int) -> Tileset:
        """
        Obtiene el tileset para una zona específica.
        Si el archivo no existe, devuelve el tileset de Zona 1 (fallback).

        Args:
            zone: número de zona (1, 2, 3, etc.)

        Returns:
            Tileset cargado para esa zona
        """
        # Obtener ruta del tileset para esta zona
        tileset_path = ZONE_TILESETS.get(zone, ZONE_TILESETS[1])

        # Si ya está en caché, devolverlo
        if tileset_path in self._cache:
            return self._cache[tileset_path]

        # Cargar nuevo tileset
        tileset = self._load_tileset(tileset_path)

        # Si falló, usar fallback de Zona 1
        if not tileset.surface and zone != 1:
            print(f"[TilesetManager] {tileset_path} no cargado, usando fallback de Zona 1")
            return self.get_tileset_for_zone(1)

        # Guardar en caché
        self._cache[tileset_path] = tileset
        return tileset

    def set_zone(self, zone: int) -> None:
        """
        Cambia la zona actual y obtiene el tileset correspondiente.

        Args:
            zone: número de zona nueva
        """
        if zone == self._current_zone:
            return  # Sin cambios

        self._current_zone = zone
        self._current_tileset = self.get_tileset_for_zone(zone)

    def get_current_tileset(self) -> Tileset:
        """
        Devuelve el tileset actual (debe llamarse después de set_zone).

        Returns:
            Tileset actual
        """
        if self._current_tileset is None:
            self._current_tileset = self.get_tileset_for_zone(self._current_zone)

        return self._current_tileset

    def _load_tileset(self, path: str) -> Tileset:
        """
        Carga un tileset desde una ruta específica.
        Crea una instancia de Tileset con la ruta dada.

        Args:
            path: ruta al archivo de tileset

        Returns:
            Tileset cargado (puede no tener surface si el archivo no existe)
        """
        if not os.path.exists(path):
            print(f"[TilesetManager] Archivo no encontrado: {path}")
            # Devolver un tileset vacío
            tileset = Tileset()
            return tileset

        # Crear un tileset manualmente con la ruta específica
        tileset = Tileset.__new__(Tileset)
        tileset.surface = None
        tileset.rects = {}

        try:
            img = pygame.image.load(path).convert_alpha()

            # Detectar tamaño original del tileset
            tileset_height = img.get_height()
            tileset_width = img.get_width()
            tile_size_original = tileset_height
            num_tiles = 9  # piso, pared_superior, pared_inferior, etc.

            # Validar formato: 9 tiles en fila horizontal
            expected_width = tile_size_original * num_tiles
            if tileset_width == expected_width:
                # Nuevo tileset detectado (128x128 o similar en fila)
                tile_size_logico = CFG.TILE_SIZE  # 32px

                # Si el tamaño es diferente, escalar la imagen
                if tile_size_original != tile_size_logico:
                    scale_factor = tile_size_logico / tile_size_original
                    new_width = int(tileset_width * scale_factor)
                    new_height = int(tileset_height * scale_factor)
                    img = pygame.transform.scale(img, (new_width, new_height))
                    tile_size_original = tile_size_logico
            else:
                # Tileset antiguo o formato desconocido
                tile_size_original = CFG.TILE_SIZE

            # Mapeo de tile ID -> (col, row) en el spritesheet
            tile_defs = {
                CFG.FLOOR: (0, 0),
                CFG.WALL: (1, 0),
                CFG.WALL_TOP: (1, 0),
                CFG.WALL_BOTTOM: (2, 0),
                CFG.WALL_LEFT: (3, 0),
                CFG.WALL_RIGHT: (4, 0),
                CFG.WALL_CORNER_NW: (5, 0),
                CFG.WALL_CORNER_NE: (6, 0),
                CFG.WALL_CORNER_SW: (7, 0),
                CFG.WALL_CORNER_SE: (8, 0),
            }

            # Construir rects para cada tile
            width, height = img.get_width(), img.get_height()
            for tile_id, (col, row) in tile_defs.items():
                x = col * tile_size_original
                y = row * tile_size_original
                if x + tile_size_original <= width and y + tile_size_original <= height:
                    tileset.rects[tile_id] = pygame.Rect(
                        x, y, tile_size_original, tile_size_original
                    )

            if tileset.rects:
                tileset.surface = img

        except Exception as e:
            print(f"[TilesetManager] Error cargando {path}: {e}")
            tileset.surface = None
            tileset.rects = {}

        return tileset

    def get_cache_stats(self) -> Dict:
        """
        Devuelve estadísticas del caché para debugging.

        Returns:
            Diccionario con información del caché
        """
        return {
            "cached_tilesets": len(self._cache),
            "current_zone": self._current_zone,
            "cached_paths": list(self._cache.keys()),
        }
