"""Utilities to resolve project asset directories regardless of CWD."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# ---------------------------------------------------------------------------
# Directorios de assets
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def project_root() -> Path:
    """
    Retorna la ruta absoluta a la raíz del repositorio.

    La jerarquía es:
        <repo_root>/CODIGO/core/asset_paths.py
                     ↑ parent ↑ parent ↑ parent = repo_root
    """
    return Path(__file__).resolve().parent.parent.parent


@lru_cache(maxsize=None)
def assets_dir(*extra: str | Path) -> Path:
    """Return the absolute path to the ``assets`` directory (optionally joined).

    Parameters
    ----------
    *extra:
        Optional path components to append to the base ``assets`` directory.
    """

    base = project_root() / "assets"
    if extra:
        return base.joinpath(*extra)
    return base


# ---------------------------------------------------------------------------
# Rutas de sprites para armas
# ---------------------------------------------------------------------------

# Mapeo explícito de ``weapon_id`` -> nombre de archivo esperado dentro de
# ``assets/weapons``.  Mantén esta lista sincronizada con las armas
# registradas en ``Weapons.WeaponFactory``.
WEAPON_SPRITE_FILENAMES: dict[str, str] = {
    "bloqueo": "bloqueo.png",
    "reportar": "reportar.png",
    "apoyo_amigo": "apoyo_amigo.png",
    "pausa_digital": "pausa_digital.png",
    "autoestima": "autoestima.png",
    "evidencia": "evidencia.png",
    "modo_incognito": "modo_incognito.png",
}


def weapon_sprite_path(weapon_id: str) -> Path:
    """Devuelve la ruta absoluta al sprite del arma indicada.

    Si el arma no está registrada, asumirá ``<weapon_id>.png`` como nombre de
    archivo para permitir añadir nuevos sprites sin romper el flujo.
    """

    filename = WEAPON_SPRITE_FILENAMES.get(weapon_id, f"{weapon_id}.png")
    return assets_dir("weapons", filename)
