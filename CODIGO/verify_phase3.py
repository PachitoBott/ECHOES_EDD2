#!/usr/bin/env python3
"""
Verify Phase 3 enemy synchronization implementation
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_protocol():
    """Test protocol message"""
    print("[1/5] Testing protocol message...")
    try:
        from network.protocol import msg_enemigo_muerto, TipoMensaje
        msg = msg_enemigo_muerto(100.0, 200.0, "BasicEnemy", (1, 2))
        assert msg.tipo == TipoMensaje.EVENTO
        assert msg.datos["tipo"] == "enemigo_muerto"
        assert msg.datos["pos_x"] == 100.0
        assert msg.datos["pos_y"] == 200.0
        assert msg.datos["enemy_type"] == "BasicEnemy"
        assert msg.datos["sala"] == (1, 2)
        print("  OK - msg_enemigo_muerto() works correctly")
        return True
    except Exception as e:
        print(f"  FAIL - {e}")
        return False

def test_serialization():
    """Test message serialization"""
    print("[2/5] Testing message serialization...")
    try:
        from network.protocol import msg_enemigo_muerto
        msg = msg_enemigo_muerto(50.0, 75.0, "TankEnemy", (3, 4))
        serialized = msg.serializar()
        assert isinstance(serialized, bytes)
        assert b"enemigo_muerto" in serialized
        assert b"50.0" in serialized or b"50" in serialized
        print("  OK - Serialization works")
        return True
    except Exception as e:
        print(f"  FAIL - {e}")
        return False

def test_network_manager():
    """Test NetworkManager.enviar()"""
    print("[3/5] Testing NetworkManager.enviar()...")
    try:
        from network.manager import NetworkManager
        from network.protocol import msg_enemigo_muerto
        
        nm = NetworkManager.como_cliente("127.0.0.1", 5555, "victima")
        assert hasattr(nm, "enviar")
        assert callable(nm.enviar)
        
        # Test that it accepts Mensaje objects
        msg = msg_enemigo_muerto(10.0, 20.0, "BasicEnemy", (0, 0))
        # Don't actually send (no server), just verify method exists
        print("  OK - NetworkManager.enviar() method exists and is callable")
        return True
    except Exception as e:
        print(f"  FAIL - {e}")
        return False

def test_game_methods():
    """Test Game.py methods exist"""
    print("[4/5] Testing Game.py methods...")
    try:
        from Game import Game
        assert hasattr(Game, "_handle_remote_enemy_death")
        assert callable(getattr(Game, "_handle_remote_enemy_death"))
        print("  OK - Game._handle_remote_enemy_death() exists")
        return True
    except Exception as e:
        print(f"  FAIL - {e}")
        return False

def test_imports():
    """Test all imports work together"""
    print("[5/5] Testing combined imports...")
    try:
        from network.protocol import msg_enemigo_muerto
        from network.manager import NetworkManager
        from Game import Game
        print("  OK - All components import successfully")
        return True
    except Exception as e:
        print(f"  FAIL - {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("PHASE 3 VERIFICATION - ENEMY SYNCHRONIZATION")
    print("="*60)
    
    tests = [
        test_protocol,
        test_serialization,
        test_network_manager,
        test_game_methods,
        test_imports,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            results.append(False)
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("\nPHASE 3 IMPLEMENTATION VERIFIED!")
        print("\nNext: Run the 3-terminal test from PHASE3_ENEMY_SYNC_TEST.md")
        sys.exit(0)
    else:
        print("\nSome tests failed. Check output above.")
        sys.exit(1)
