#!/usr/bin/env python3
"""
Test script to verify that boss room never has north access across multiple seeds.
"""
import sys
from world.Dungeon import Dungeon

def test_boss_access(seed: int) -> bool:
    """
    Test if a given seed has valid boss access (no north-only entrance).

    Returns True if VALID (no north access)
    Returns False if INVALID (has north access)
    """
    print(f"\n{'='*80}")
    print(f"Testing seed: {seed}")
    print(f"{'='*80}")

    try:
        dungeon = Dungeon(seed=seed)
    except Exception as e:
        print(f"[ERROR] Failed to generate dungeon: {e}")
        return False

    if not hasattr(dungeon, "boss_pos"):
        print("[ERROR] Dungeon has no boss_pos attribute")
        return False

    boss_x, boss_y = dungeon.boss_pos
    boss_room = dungeon.rooms.get(dungeon.boss_pos)

    if boss_room is None:
        print("[ERROR] Boss room not found in dungeon.rooms")
        return False

    print(f"Boss position: {dungeon.boss_pos}")
    print(f"Boss room doors: N={boss_room.doors.get('N', False)}, "
          f"S={boss_room.doors.get('S', False)}, "
          f"E={boss_room.doors.get('E', False)}, "
          f"W={boss_room.doors.get('W', False)}")

    # Check 1: Is there a room to the north?
    room_north = dungeon.rooms.get((boss_x, boss_y - 1))
    if room_north is not None:
        print(f"[FAIL] Room exists to the north: {(boss_x, boss_y - 1)}")
        print(f"       This allows NORTH access to boss room!")
        return False

    print(f"[OK] No room to the north")

    # Check 2: Has at least one non-north door?
    has_south = boss_room.doors.get("S", False)
    has_east = boss_room.doors.get("E", False)
    has_west = boss_room.doors.get("W", False)

    non_north_doors = sum([has_south, has_east, has_west])

    if non_north_doors > 0:
        print(f"[OK] Has {non_north_doors} non-north entrance(s)")
        return True
    else:
        print(f"[FAIL] NO non-north entrances available!")
        return False

def main():
    # Test seeds
    test_seeds = [
        910797483,  # The seed that was reported as broken
        1,
        42,
        12345,
        999999,
        123456789,
        987654321,
        500000000,
        100000000,
        200000000,
        300000000,
    ]

    results = {}
    passed = 0
    failed = 0

    for seed in test_seeds:
        is_valid = test_boss_access(seed)
        results[seed] = is_valid
        if is_valid:
            passed += 1
            print(f"[PASS] Seed {seed}")
        else:
            failed += 1
            print(f"[FAIL] Seed {seed}")

    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Tested seeds: {len(test_seeds)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed > 0:
        print(f"\nFailed seeds:")
        for seed, is_valid in results.items():
            if not is_valid:
                print(f"  - {seed}")
        return 1
    else:
        print(f"\nAll seeds passed! Boss room access is valid for all tested seeds.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
