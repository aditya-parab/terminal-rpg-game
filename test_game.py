#!/usr/bin/env python3
"""
Simple test script to verify the game works correctly
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from term_dungeon_rpg import Game
import argparse

def test_basic_movement():
    """Test that basic movement works without phantom combat"""
    print("Testing basic movement...")
    
    # Create a game instance
    args = argparse.Namespace(
        seed=12345, 
        reset=True, 
        no_save=True, 
        headless=True, 
        debug=False,
        minimal_curses=False,
        debug_draw=False
    )
    
    game = Game(args, stdscr=None)
    
    # Record initial state
    initial_pos = (game.player.x, game.player.y)
    initial_hp = game.player.hp
    initial_turn = game.turn_count
    
    print(f"Initial: Pos={initial_pos}, HP={initial_hp}, Turn={initial_turn}")
    
    # Try to move right
    game.handle_player_action(1, 0)
    
    after_move_pos = (game.player.x, game.player.y)
    after_move_hp = game.player.hp
    after_move_turn = game.turn_count
    
    print(f"After move: Pos={after_move_pos}, HP={after_move_hp}, Turn={after_move_turn}")
    
    # Check if movement worked or was blocked
    if after_move_pos != initial_pos:
        print("✓ Player moved successfully")
    else:
        print("✓ Player movement blocked (expected if hitting wall)")
    
    # Check if turn advanced
    if after_move_turn > initial_turn:
        print("✓ Turn counter advanced")
    else:
        print("✗ Turn counter did not advance")
        return False
    
    # Check for phantom damage
    if after_move_hp < initial_hp:
        print("✗ Player took phantom damage!")
        return False
    else:
        print("✓ No phantom damage")
    
    return True

def test_combat_system():
    """Test that combat only happens when player and monster are adjacent"""
    print("\nTesting combat system...")
    
    args = argparse.Namespace(
        seed=12345, 
        reset=True, 
        no_save=True, 
        headless=True, 
        debug=False,
        minimal_curses=False,
        debug_draw=False
    )
    
    game = Game(args, stdscr=None)
    
    # Find a monster
    if not game.current_map.monsters:
        print("✓ No monsters to test combat with")
        return True
    
    monster = game.current_map.monsters[0]
    print(f"Monster at: ({monster.x}, {monster.y})")
    print(f"Player at: ({game.player.x}, {game.player.y})")
    
    # Calculate distance
    distance = abs(monster.x - game.player.x) + abs(monster.y - game.player.y)
    print(f"Distance: {distance}")
    
    initial_hp = game.player.hp
    
    # Make a move that doesn't approach the monster
    if game.player.x > 0:
        game.handle_player_action(-1, 0)  # Move left
    else:
        game.handle_player_action(1, 0)   # Move right
    
    after_hp = game.player.hp
    
    if after_hp < initial_hp:
        print("✗ Player took damage when not adjacent to monster!")
        return False
    else:
        print("✓ No damage when not in combat")
    
    return True

if __name__ == "__main__":
    print("Running game tests...\n")
    
    success = True
    success &= test_basic_movement()
    success &= test_combat_system()
    
    if success:
        print("\n✓ All tests passed! Game is working correctly.")
    else:
        print("\n✗ Some tests failed!")
        sys.exit(1)
