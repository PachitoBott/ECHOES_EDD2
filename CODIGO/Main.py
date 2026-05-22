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
            "  python Main.py                           # inicio normal con menú\n"
            "  python Main.py --seed 1234               # seed fija, con menú\n"
            "  python Main.py --skip-menu               # seed aleatoria, sin menú\n"
            "  python Main.py --skip-intro              # menú + juego (sin cinemática intro)\n"
            "  python Main.py --seed 1234 --room 5,3    # seed + sala específica\n"
            "  python Main.py --debug                   # activa consola F1\n"
            "\n"
            "Multijugador (Cliente-Servidor):\n"
            "  python Main.py --server --port 5555 --skip-menu\n"
            "  python Main.py --client --host 127.0.0.1 --port 5555 --role victim --skip-menu\n"
            "  python Main.py --client --host 127.0.0.1 --port 5555 --role ally --skip-menu\n"
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
    parser.add_argument(
        "--skip-intro",
        dest="skip_intro",
        action="store_true",
        help="Salta la cinemática de intro pero mantiene el menú (para presentación)",
    )
    # --- Networking ---
    parser.add_argument(
        "--server",
        action="store_true",
        help="Modo servidor: hospeda la sesión multijugador",
    )
    parser.add_argument(
        "--client",
        action="store_true",
        help="Modo cliente: se conecta a un servidor",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        metavar="ADDR",
        help="IP/hostname del servidor (solo con --client, default 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5555,
        metavar="PORT",
        help="Puerto TCP para servidor o cliente (default 5555)",
    )
    parser.add_argument(
        "--role",
        type=str,
        default="victima",
        choices=["victim", "ally", "victima", "aliado"],
        metavar="ROLE",
        help="Rol del cliente: 'victim'/'victima' (controla) o 'ally'/'aliado' (soporte)",
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

    # Traducir roles: "victim"/"ally" (inglés) → "victima"/"aliado" (español)
    role_map = {"victim": "victima", "ally": "aliado"}
    role_normalizado = role_map.get(args.role, args.role)

    # Determinar modo de red
    net_mode = "offline"
    net_params = {}
    if args.server:
        net_mode = "server"
        net_params = {"port": args.port}
        log_game.info(f"Modo servidor: puerto {args.port}")
    elif args.client:
        net_mode = "client"
        net_params = {"host": args.host, "port": args.port, "role": role_normalizado}
        log_game.info(f"Modo cliente: {role_normalizado} @ {args.host}:{args.port}")

    # Crear instancia del juego con el modo de red
    game = Game(CFG, debug_mode=args.debug, mode=net_mode, skip_intro=args.skip_intro, **net_params)

    # Decidir si saltar el menú
    # CAMBIO: Permitir menú incluso con --server/--client (útil para presentaciones)
    # Solo saltar menú si se especifica explícitamente --skip-menu, o si se especifica sala/seed
    skip_menu = args.skip_menu or (start_room is not None) or (args.seed is not None)

    if skip_menu:
        # Si es cliente, esperar a que obtenga la seed del servidor
        seed_a_usar = args.seed
        if args.client and game.net and hasattr(game.net, '_cliente'):
            # Esperar a que el cliente se conecte y obtenga la seed del servidor
            import time as time_module
            max_wait = 10.0  # 10 segundos máximo
            start = time_module.time()
            log_game.info("Esperando seed del servidor...")
            while game.net._cliente.seed is None and (time_module.time() - start) < max_wait:
                time_module.sleep(0.2)
            if game.net._cliente.seed is not None:
                seed_a_usar = game.net._cliente.seed
                log_game.info(f"[OK] Usando seed del servidor: {seed_a_usar}")
            else:
                log_game.warning(f"[WARNING] No se recibió seed del servidor, usando seed aleatoria")

        log_game.info(
            f"Inicio rápido — seed={seed_a_usar}  sala={start_room}  debug={args.debug}  modo={net_mode}"
        )
        game.quick_start(seed=seed_a_usar, start_room=start_room)
    else:
        game.run()
