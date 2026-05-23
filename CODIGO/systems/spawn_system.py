"""
Sistema de spawn de enemigos por zona con probabilidades ponderadas.

Implementa la lógica de selección de enemigos según:
- Zona de la sala (1 o 2)
- Posición dentro de la zona (índice y total)
- Probabilidades dinámicas para transiciones suaves

Estructura de zonas:
- Zona 1: tank, green_chaser, yellow_shooter (enemigos rojos)
- Zona 2: emoji, telefono, faker (enemigos morados)
"""

import random
from typing import List


def calcular_prob_enemigo(tipo_enemigo: str,
                          zona_sala: int,
                          idx_en_zona: int,
                          total_salas_zona: int) -> float:
    """
    Calcula la probabilidad de spawn de un enemigo según la zona de la sala
    y su posición dentro de esa zona.

    Args:
        tipo_enemigo: nombre del enemigo
        zona_sala: zona de la sala (1 o 2)
        idx_en_zona: índice de la sala en su zona (0 = primera sala)
        total_salas_zona: total de salas en esa zona

    Returns:
        Float entre 0.0 y 1.0 (probabilidad de aparición)
    """

    # Mapeo: qué zona pertenece cada tipo de enemigo
    ZONA_ENEMIGO = {
        "BasicEnemy": 1,
        "FastChaserEnemy": 1,
        "ShooterEnemy": 1,
        "TankEnemy": 1,
        "EmojiEnemy": 2,
        "TelefonoEnemy": 2,
        "FakerEnemy": 2,
    }

    zona_nativa = ZONA_ENEMIGO.get(tipo_enemigo, 1)

    # Progreso dentro de la zona actual (0.0 = primera, 1.0 = última)
    if total_salas_zona > 1:
        progreso = idx_en_zona / (total_salas_zona - 1)
    else:
        progreso = 0.0

    # ─────────────────────────────────────────
    # CASO 1: Enemigo en su zona nativa
    # Siempre aparece — probabilidad 1.0
    # ─────────────────────────────────────────
    if zona_sala == zona_nativa:
        return 1.0

    # ─────────────────────────────────────────
    # CASO 2: Enemigo ROJO en ZONA 2
    # Probabilidad baja y decreciente
    # Primeras salas de zona 2: hasta 25%
    # Últimas salas de zona 2: ~5%
    # ─────────────────────────────────────────
    if zona_nativa == 1 and zona_sala == 2:
        prob_max = 0.25
        prob_min = 0.05
        prob = prob_max - (prob_max - prob_min) * progreso
        return round(prob, 3)

    # ─────────────────────────────────────────
    # CASO 3: Enemigo MORADO en ZONA 1
    # Probabilidad pequeña y creciente
    # Primera mitad de zona 1: 0%
    # Segunda mitad: hasta 20%
    # ─────────────────────────────────────────
    if zona_nativa == 2 and zona_sala == 1:
        if progreso < 0.5:
            return 0.0
        # Escalar de 0% a 20% en la segunda mitad
        progreso_segunda_mitad = (progreso - 0.5) / 0.5
        prob = 0.20 * progreso_segunda_mitad
        return round(prob, 3)

    # Por defecto: no aparece
    return 0.0


def seleccionar_enemigos_para_sala(zona_sala: int,
                                   idx_en_zona: int,
                                   total_salas_zona: int,
                                   n_enemigos: int = None) -> List[str]:
    """
    Devuelve una lista de tipos de enemigos a spawnear en una sala.

    Usa probabilidades ponderadas para seleccionar enemigos, permitiendo
    mezclas naturales en zonas de transición.

    Args:
        zona_sala: zona de la sala (1 o 2)
        idx_en_zona: índice dentro de la zona (0-indexed)
        total_salas_zona: total de salas en esa zona
        n_enemigos: cuántos enemigos spawnear (None = valor por defecto)

    Returns:
        Lista de strings con nombres de clases de enemigos
        ej: ["TankEnemy", "FastChaserEnemy", "EmojiEnemy"]
    """

    # Todos los tipos de enemigos disponibles
    TODOS_LOS_TIPOS = [
        "BasicEnemy",
        "FastChaserEnemy",
        "ShooterEnemy",
        "TankEnemy",
        "EmojiEnemy",
        "TelefonoEnemy",
        "FakerEnemy",
    ]

    # Número de enemigos por sala según zona
    if n_enemigos is None:
        if zona_sala == 1:
            n_enemigos = random.randint(2, 4)
        elif zona_sala == 2:
            n_enemigos = random.randint(3, 5)
        else:
            n_enemigos = random.randint(2, 4)

    # Calcular probabilidad de cada tipo
    pesos = {}
    for tipo in TODOS_LOS_TIPOS:
        pesos[tipo] = calcular_prob_enemigo(
            tipo,
            zona_sala,
            idx_en_zona,
            total_salas_zona
        )

    # Filtrar tipos con probabilidad > 0
    tipos_disponibles = [
        t for t in TODOS_LOS_TIPOS
        if pesos[t] > 0
    ]

    if not tipos_disponibles:
        # Fallback: usar enemigos de la zona nativa
        if zona_sala == 1:
            tipos_disponibles = [
                "BasicEnemy", "FastChaserEnemy", "ShooterEnemy", "TankEnemy"
            ]
        else:
            tipos_disponibles = [
                "EmojiEnemy", "TelefonoEnemy", "FakerEnemy"
            ]

    # Selección ponderada por probabilidad
    lista_tipos = list(tipos_disponibles)
    lista_pesos = [pesos[t] for t in lista_tipos]

    enemigos_sala = []
    for _ in range(n_enemigos):
        elegido = random.choices(
            lista_tipos,
            weights=lista_pesos,
            k=1
        )[0]
        enemigos_sala.append(elegido)

    # Log de debug
    from dev.logger import log_game
    log_game.info(
        f"[SPAWN ZONE] Zona {zona_sala} sala {idx_en_zona}/{total_salas_zona-1}: "
        f"{enemigos_sala}"
    )

    return enemigos_sala


def calcular_indices_zona(salas_por_zona: dict) -> None:
    """
    Asigna index_in_zone y total_in_zone a cada sala según su zona.

    Debe llamarse después de generar el mapa de dungeon.

    Args:
        salas_por_zona: dict con estructura {zona: [salas]}
                       ej: {1: [Room, Room, ...], 2: [Room, ...]}
    """
    from dev.logger import log_game

    for zona, lista_salas in salas_por_zona.items():
        total = len(lista_salas)
        for idx, sala in enumerate(lista_salas):
            sala.index_in_zone = idx
            sala.total_in_zone = total

            log_game.debug(
                f"[ZONA IDX] Sala zona={zona} index={idx} total={total}"
            )
