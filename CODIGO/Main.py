"""
CODIGO/Main.py — Punto de entrada del juego Echoes.

Uso normal:
    python Main.py

Modo desarrollo (salta el menú):
    python Main.py --seed 42
    python Main.py --room 5,3
    python Main.py --seed 42 --room 5,3 --debug
    python Main.py --skip-menu --debug

Flags disponibles:
    --seed N          Seed para la generación del dungeon (entero)
    --room I,J        Sala inicial como "i,j" — omite el menú de inicio
    --debug           Activa el modo debug (consola F1 disponible desde el inicio)
    --skip-menu       Inicia directamente sin pasar por el menú
"""
from __future__ import annotations

import argparse
import sys

from Config import CFG
from Game import Game
from dev.logger import log_game


# ---------------------------------------------------------------------------
# Parseo de argumentos
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="echoes",
        description="Echoes — Aventura narrativa sobre ciberacoso (EDD 2, UniNorte)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python Main.py                        # inicio normal con menú\n"
            "  python Main.py --seed 1234            # seed fija, con menú\n"
            "  python Main.py --skip-menu            # seed aleatoria, sin menú\n"
            "  python Main.py --seed 1234 --room 5,3 # seed + sala específica\n"
            "  python Main.py --debug                # activa consola F1\n"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="N",
        help="Seed para la generación procedural del dungeon",
    )
    parser.add_argument(
        "--room",
        type=str,
        default=None,
        metavar="I,J",
        help="Sala inicial como 'i,j' (implica --skip-menu)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Activa el modo debug: consola F1 disponible",
    )
    parser.add_argument(
        "--skip-menu",
        dest="skip_menu",
        action="store_true",
        help="Salta el menú principal e inicia directamente con seed aleatoria",
    )
    return parser


def _parse_room(room_str: str | None) -> tuple[int, int] | None:
    """
    Convierte el string 'i,j' en una tupla (i, j).

    Retorna None si el argumento es None o tiene formato inválido,
    imprimiendo un aviso en ese caso.
    """
    if room_str is None:
        return None
    try:
        parts = room_str.split(",")
        if len(parts) != 2:
            raise ValueError
        return int(parts[0].strip()), int(parts[1].strip())
    except (ValueError, AttributeError):
        log_game.error(
            f"--room debe tener formato 'i,j' (ej: '5,3'). Recibido: '{room_str}'"
        )
        return None


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args       = _build_parser().parse_args()
    start_room = _parse_room(args.room)

    # Crear instancia del juego con el modo debug si se solicitó
    game = Game(CFG, debug_mode=args.debug)

    # Decidir si saltar el menú
    skip_menu = args.skip_menu or (start_room is not None) or (args.seed is not None)

    if skip_menu:
        log_game.info(
            f"Inicio rápido — seed={args.seed}  sala={start_room}  debug={args.debug}"
        )
        game.quick_start(seed=args.seed, start_room=start_room)
    else:
        game.run()
