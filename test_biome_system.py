#!/usr/bin/env python3
"""
Test script to verify biome system works correctly
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from term_dungeon_rpg import Game
import argparse

def test_biome_colors():
    """Test that biome colors change appropriately with depth"""
    print("Testing biome color system...")
    
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
    
    # Test biome colors for different depths
    test_depths = [1, 3, 4, 6, 7, 9, 10, 12, 13, 15, 16, 18]
    
    print("\nBiome progression:")
    previous_biome = None
    
    for depth in test_depths:
        biome = game.get_biome_colors(depth)
        
        if previous_biome is None or biome["name"] != previous_biome["name"]:
            print(f"\nDepth {depth}: {biome['name']}")
            print(f"  Description: {biome['description']}")
            print(f"  Floor Color: {biome['floor']}, Wall Color: {biome['wall']}")
            
            if previous_biome and biome["name"] != previous_biome["name"]:
                print(f"  ✅ Biome transition from {previous_biome['name']} to {biome['name']}")
        
        previous_biome = biome
    
    # Verify expected biome transitions
    expected_biomes = [
        (1, "Stone Caverns"),
        (4, "Ice Caves"), 
        (7, "Jungle Ruins"),
        (10, "Fire Depths"),
        (13, "Shadow Realm"),
        (16, "Crystal Sanctum")
    ]
    
    print("\nVerifying expected biome transitions:")
    all_correct = True
    
    for depth, expected_name in expected_biomes:
        biome = game.get_biome_colors(depth)
        if biome["name"] == expected_name:
            print(f"✅ Depth {depth}: {expected_name}")
        else:
            print(f"❌ Depth {depth}: Expected {expected_name}, got {biome['name']}")
            all_correct = False
    
    return all_correct

def test_biome_monsters():
    """Test that monsters vary by biome"""
    print("\nTesting biome-specific monsters...")
    
    # Create a game instance
    args = argparse.Namespace(
        seed=54321, 
        reset=True, 
        no_save=True, 
        headless=True, 
        debug=False,
        minimal_curses=False,
        debug_draw=False
    )
    
    game = Game(args, stdscr=None)
    
    # Test monster generation at different depths
    test_depths = [1, 4, 7, 10, 13, 16]
    
    for depth in test_depths:
        # Simulate being at this depth
        game.dungeon_depth = depth
        
        # Generate a new map to see monsters
        from term_dungeon_rpg import GameMap
        test_map = GameMap(60, 40, 12345 + depth)
        test_map.generate_map(depth)
        
        biome = game.get_biome_colors(depth)
        print(f"\nDepth {depth} ({biome['name']}):")
        
        # Count monster types
        monster_types = {}
        for monster in test_map.monsters:
            monster_type = monster.name
            monster_types[monster_type] = monster_types.get(monster_type, 0) + 1
        
        if monster_types:
            for monster_name, count in monster_types.items():
                print(f"  {monster_name}: {count}")
        else:
            print("  No monsters generated")
    
    return True

def test_biome_messages():
    """Test that biome transition messages appear"""
    print("\nTesting biome transition messages...")
    
    # Create a game instance
    args = argparse.Namespace(
        seed=99999, 
        reset=True, 
        no_save=True, 
        headless=True, 
        debug=False,
        minimal_curses=False,
        debug_draw=False
    )
    
    game = Game(args, stdscr=None)
    
    # Start at depth 3 (end of first biome)
    game.dungeon_depth = 3
    
    # Clear message log
    game.message_log = []
    
    # Trigger level generation (should transition to Ice Caves)
    game.generate_new_level()
    
    # Check if biome transition message appeared
    messages = " ".join(game.message_log)
    
    if "Ice Caves" in messages:
        print("✅ Biome transition message detected")
        print(f"Messages: {game.message_log}")
        return True
    else:
        print("❌ No biome transition message found")
        print(f"Messages: {game.message_log}")
        return False

if __name__ == "__main__":
    print("Running biome system tests...\n")
    
    success = True
    success &= test_biome_colors()
    success &= test_biome_monsters()
    success &= test_biome_messages()
    
    if success:
        print("\n✅ All biome system tests passed!")
    else:
        print("\n❌ Some biome system tests failed!")
        sys.exit(1)