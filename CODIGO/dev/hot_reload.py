"""
hot_reload.py — Recarga en caliente de assets y datos sin reiniciar el juego.

Monitorea archivos individuales (o directorios completos) por tiempo de
modificación (mtime). Cuando detecta un cambio, invoca el callback
registrado para ese path.

Uso básico:
    watcher = AssetWatcher()
    watcher.watch(path_png, mi_callback_recarga)
    watcher.watch_dir(assets_dir / "weapons", "*.png", reload_weapons)

    # En el game loop, una vez por frame:
    watcher.tick()

    # Para recargar todo de forma manual (desde la consola de debug):
    watcher.reload_all()
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from dev.logger import log_asset


# Tipo de callback: recibe el Path del archivo que cambió.
ReloadCallback = Callable[[Path], None]


class AssetWatcher:
    """
    Vigila archivos por mtime y llama callbacks cuando detecta cambios.

    No usa hilos ni inotify — es un polling ligero pensado para
    ejecutarse una vez por frame durante el desarrollo. En producción
    se puede deshabilitar simplemente no creando la instancia o no
    llamando a tick().
    """

    def __init__(self, check_interval: float = 0.5) -> None:
        """
        Parámetros
        ----------
        check_interval:
            Segundos mínimos entre escaneos. Evita stat() cada frame.
            0.5 segundos es suficiente para uso interactivo.
        """
        self._check_interval: float = check_interval
        self._last_check:     float = 0.0
        # path -> (mtime registrado, callback)
        self._watched: dict[Path, tuple[float, ReloadCallback]] = {}

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #

    def watch(self, path: Path | str, callback: ReloadCallback) -> None:
        """
        Registra un archivo para vigilar.

        Si el archivo no existe todavía, se registra con mtime=0 y se
        disparará el callback en cuanto aparezca.

        Parámetros
        ----------
        path:
            Ruta al archivo a vigilar.
        callback:
            Función que se llama con el Path del archivo al detectar cambio.
        """
        p = Path(path)
        try:
            mtime = p.stat().st_mtime
        except FileNotFoundError:
            mtime = 0.0
        self._watched[p] = (mtime, callback)
        log_asset.debug(f"Vigilando: {p.name}")

    def watch_dir(
        self,
        directory: Path | str,
        pattern: str,
        callback: ReloadCallback,
    ) -> int:
        """
        Vigila todos los archivos que coincidan con el patrón en el directorio.

        Parámetros
        ----------
        directory:
            Directorio donde buscar archivos.
        pattern:
            Glob pattern relativo al directorio (e.g., "*.png", "**/*.json").
        callback:
            Callback que se llama con el Path del archivo que cambió.

        Retorna
        -------
        int
            Número de archivos registrados.
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            log_asset.warning(f"Directorio no encontrado para vigilar: {dir_path}")
            return 0

        count = 0
        for file_path in dir_path.glob(pattern):
            self.watch(file_path, callback)
            count += 1

        log_asset.debug(f"Vigilando {count} archivos en {dir_path.name}/ ('{pattern}')")
        return count

    def unwatch(self, path: Path | str) -> None:
        """Elimina un archivo del monitoreo."""
        self._watched.pop(Path(path), None)

    def tick(self) -> int:
        """
        Verifica cambios en todos los archivos vigilados.

        Llama a sus callbacks si detecta modificaciones.
        Debe ejecutarse una vez por frame en el game loop.

        Retorna
        -------
        int
            Número de archivos recargados en este tick.
        """
        now = time.monotonic()
        if now - self._last_check < self._check_interval:
            return 0
        self._last_check = now

        reloaded = 0
        for path, (last_mtime, callback) in list(self._watched.items()):
            try:
                current_mtime = path.stat().st_mtime
            except FileNotFoundError:
                continue   # archivo borrado; ignorar silenciosamente

            if current_mtime == last_mtime:
                continue

            # Actualizar mtime antes de llamar al callback para no re-disparar
            # si el callback tarda más de check_interval.
            self._watched[path] = (current_mtime, callback)
            log_asset.info(f"Cambio detectado en '{path.name}' — recargando...")

            try:
                callback(path)
                reloaded += 1
            except Exception as exc:
                log_asset.error(f"Error en callback de recarga para '{path.name}': {exc}")

        return reloaded

    def reload_all(self) -> int:
        """
        Fuerza la recarga de todos los archivos vigilados, sin importar
        si cambiaron o no. Útil para el comando 'reload' de la consola.

        Retorna
        -------
        int
            Número de archivos en los que se intentó recargar.
        """
        if not self._watched:
            log_asset.warning("No hay archivos registrados para recargar.")
            return 0

        log_asset.info(f"Recarga forzada de {len(self._watched)} archivos...")
        count = 0
        for path, (_, callback) in list(self._watched.items()):
            try:
                callback(path)
                # Actualizar mtime para no re-disparar en el siguiente tick
                try:
                    current_mtime = path.stat().st_mtime
                except FileNotFoundError:
                    current_mtime = 0.0
                self._watched[path] = (current_mtime, callback)
                count += 1
            except Exception as exc:
                log_asset.error(f"Error recargando '{path.name}': {exc}")

        log_asset.info(f"Recarga manual completada ({count}/{len(self._watched)} OK).")
        return count

    def watched_count(self) -> int:
        """Retorna el número de archivos actualmente vigilados."""
        return len(self._watched)
