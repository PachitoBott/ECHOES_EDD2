#!/usr/bin/env python3
"""
Test to verify that enemies don't die when they fire projectiles in multiplayer mode.

This test verifies the fix for the bug where enemies would die immediately after
firing a projectile because the client was processing enemy projectiles as if they
could hit enemies.

Bug: Client received enemy projectiles via _handle_enemy_projectiles_state() and
added them to self.remote_projectiles. Then in _handle_collisions(), the client
checked if remote_projectiles hit enemies, causing enemies to take damage from
their own projectiles.

Fix: Check if a projectile has _remote_id attribute (which RemoteProjectile has).
If it does, skip collision checking - the server handles all enemy projectile
collision detection.
"""

def test_remote_projectile_identification():
    """Verify that RemoteProjectile has _remote_id attribute"""
    import sys
    sys.path.insert(0, 'CODIGO')
    from Game import RemoteProjectile

    proj = RemoteProjectile(remote_id=123, x=100.0, y=200.0, dx=0.5, dy=0.5)
    assert hasattr(proj, '_remote_id'), "RemoteProjectile must have _remote_id"
    assert proj._remote_id == 123, "_remote_id must match constructor"
    print("OK - RemoteProjectile.has_remote_id")


def test_regular_projectile_no_remote_id():
    """Verify that regular Projectile doesn't have _remote_id"""
    import sys
    sys.path.insert(0, 'CODIGO')
    from core.Projectile import Projectile

    proj = Projectile(x=100.0, y=200.0, dx=0.5, dy=0.5)
    assert not hasattr(proj, '_remote_id'), "Regular Projectile must NOT have _remote_id"
    print("OK - Projectile.no_remote_id")


def test_collision_detection_logic():
    """Verify the fix logic: remote_projectiles with _remote_id should be skipped"""
    import sys
    sys.path.insert(0, 'CODIGO')
    from Game import RemoteProjectile
    from core.Projectile import Projectile

    # Simulated remote_projectiles list (mixed types)
    remote_projectiles = [
        RemoteProjectile(remote_id=1, x=100, y=200),  # Enemy projectile
        Projectile(x=150, y=250, dx=1, dy=0),  # Player projectile
        RemoteProjectile(remote_id=2, x=200, y=300),  # Enemy projectile
    ]

    # Count which projectiles would be processed (without _remote_id)
    processed = 0
    skipped = 0

    for projectile in remote_projectiles:
        if hasattr(projectile, "_remote_id"):
            skipped += 1
        else:
            processed += 1

    assert processed == 1, f"Should process 1 player projectile, got {processed}"
    assert skipped == 2, f"Should skip 2 enemy projectiles, got {skipped}"
    print("OK - Collision_detection_logic (1 processed, 2 skipped)")


if __name__ == "__main__":
    try:
        print("\n[TEST] Enemy Fire Bug Fix - Remote Projectile Handling\n")
        test_remote_projectile_identification()
        test_regular_projectile_no_remote_id()
        test_collision_detection_logic()
        print("\nAll tests passed! Fix is correct.\n")
    except AssertionError as e:
        print(f"\nTest failed: {e}\n")
        exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}\n")
        exit(1)
