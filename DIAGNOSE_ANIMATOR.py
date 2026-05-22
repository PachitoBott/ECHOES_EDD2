#!/usr/bin/env python3
"""
Script para diagnosticar problemas con el animator de enemigos.
Verifica que los assets y frames existen para todos los estados.
"""

import os
from pathlib import Path

def check_animator_assets():
    """Verifica que existan assets para todas las animaciones de enemigos."""

    code_dir = Path(__file__).parent / "CODIGO"
    assets_dir = code_dir / "assets" / "enemies"

    print("=" * 70)
    print("DIAGNOSTICO DE ASSETS DEL ANIMATOR")
    print("=" * 70)

    if not assets_dir.exists():
        print(f"[ERROR] ERROR: Directorio de assets no existe: {assets_dir}")
        return False

    print(f"\n[OK] Encontrado directorio: {assets_dir}")

    # Tipos de enemigos
    enemy_types = ["Caster", "Skeleton", "Zombie"]
    required_states = ["idle", "run", "attack", "shoot", "hit"]

    all_good = True

    for enemy_type in enemy_types:
        enemy_dir = assets_dir / enemy_type
        if not enemy_dir.exists():
            print(f"\n[WARN] Tipo de enemigo '{enemy_type}' no tiene directorio")
            continue

        print(f"\n[DIR] {enemy_type}/")

        for state in required_states:
            state_dir = enemy_dir / state

            if not state_dir.exists():
                print(f"   [MISSING] FALTA: {state}/")
                all_good = False
                continue

            # Contar imágenes en el directorio
            images = list(state_dir.glob("*.png"))
            if not images:
                print(f"   [WARN] {state}/ existe pero NO tiene imágenes PNG")
                all_good = False
            else:
                print(f"   [OK] {state}/ ({len(images)} frames)")

    print("\n" + "=" * 70)

    # Verificar el Animator.py para ver cómo maneja los estados
    print("\nVERIFICANDO ANIMATOR.PY")
    print("=" * 70)

    animator_path = code_dir / "animator" / "Animator.py"
    if not animator_path.exists():
        print(f"[ERROR] Animator.py no encontrado en {animator_path}")
        return False

    with open(animator_path, 'r') as f:
        content = f.read()

    # Buscar definiciones de estados
    if "def trigger_shoot" in content:
        print("[OK] trigger_shoot() existe")
    else:
        print("[MISSING] trigger_shoot() NO EXISTE")
        all_good = False

    if "def trigger_attack" in content:
        print("[OK] trigger_attack() existe")
    else:
        print("[MISSING] trigger_attack() NO EXISTE")
        all_good = False

    if "def set_base_state" in content:
        print("[OK] set_base_state() existe")
    else:
        print("[MISSING] set_base_state() NO EXISTE")
        all_good = False

    if "def current_surface" in content:
        print("[OK] current_surface() existe")
    else:
        print("[MISSING] current_surface() NO EXISTE")
        all_good = False

    # Buscar si hay protección contra oneshot infinito
    if "oneshot_state" in content:
        print("[OK] oneshot_state management existe")
    else:
        print("[WARN] No se encontro oneshot_state management")

    print("\n" + "=" * 70)
    print("\nRESULTADO")
    print("=" * 70)

    if all_good:
        print("[SUCCESS] TODO OK - Los assets y el animator parecen estar bien configurados")
        print("\nSi los enemigos aun desaparecen, el problema es de sincronizacion")
        print("de estado, no de assets faltantes.")
    else:
        print("[ERROR] HAY PROBLEMAS - Ver detalles arriba")

    return all_good


if __name__ == "__main__":
    check_animator_assets()
