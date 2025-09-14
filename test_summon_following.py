#!/usr/bin/env python3
"""
Test script to verify summons follow player through portals and stairs
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from term_dungeon_rpg import Game, Summon
import argparse

def test_summon_portal_following():
    """Test that summons follow player through portals"""
    print("Testing summon portal following...")
    
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
    
    # Add a test summon
    test_summon = Summon(game.player.x + 1, game.player.y, 2, 1)
    test_summon.name = "Test Companion"
    test_summon.char = 'T'
    test_summon.color_pair = 3
    game.summons.append(test_summon)
    
    # Add a portal to the map manually for testing
    if not game.current_map.portals:
        # Create a test portal
        portal_x1, portal_y1 = game.player.x + 2, game.player.y
        portal_x2, portal_y2 = game.player.x + 10, game.player.y + 10
        
        # Make sure portal locations are valid floor tiles
        if (game.current_map.get_tile(portal_x1, portal_y1) == '.' and 
            game.current_map.get_tile(portal_x2, portal_y2) == '.'):
            game.current_map.portals.append((portal_x1, portal_y1, portal_x2, portal_y2))
            game.current_map.tiles[portal_y1][portal_x1] = 'O'
            game.current_map.tiles[portal_y2][portal_x2] = 'O'
            print(f"Created test portal: ({portal_x1},{portal_y1}) <-> ({portal_x2},{portal_y2})")
        else:
            print("Could not create test portal - invalid locations")
            return False
    
    if not game.current_map.portals:
        print("No portals available for testing")
        return False
    
    # Record initial positions
    initial_player_pos = (game.player.x, game.player.y)
    initial_summon_pos = (test_summon.x, test_summon.y)
    
    print(f"Initial - Player: {initial_player_pos}, Summon: {initial_summon_pos}")
    
    # Move player to portal entrance
    portal_x1, portal_y1, portal_x2, portal_y2 = game.current_map.portals[0]
    game.player.x, game.player.y = portal_x1, portal_y1
    
    print(f"Moved player to portal at ({portal_x1},{portal_y1})")
    
    # Trigger portal teleportation by moving in place
    game.handle_player_action(0, 0)
    
    # Check results
    final_player_pos = (game.player.x, game.player.y)
    final_summon_pos = (test_summon.x, test_summon.y)
    
    print(f"Final - Player: {final_player_pos}, Summon: {final_summon_pos}")
    
    # Verify player teleported
    if final_player_pos == (portal_x2, portal_y2):
        print("✅ Player successfully teleported through portal")
    else:
        print(f"❌ Player teleportation failed. Expected: ({portal_x2},{portal_y2}), Got: {final_player_pos}")
        return False
    
    # Verify summon followed
    if final_summon_pos != initial_summon_pos:
        print("✅ Summon followed player through portal")
        
        # Check summon is near player (within reasonable distance)
        distance = abs(final_summon_pos[0] - final_player_pos[0]) + abs(final_summon_pos[1] - final_player_pos[1])
        if distance <= 3:
            print(f"✅ Summon positioned appropriately near player (distance: {distance})")
        else:
            print(f"⚠️  Summon is far from player (distance: {distance})")
        
        # Check no overlap
        if final_summon_pos != final_player_pos:
            print("✅ No overlap between player and summon")
        else:
            print("❌ Player and summon are overlapping!")
            return False
            
    else:
        print("❌ Summon did not follow player through portal")
        return False
    
    return True

def test_summon_stairs_following():
    """Test that summons follow player through stairs"""
    print("\nTesting summon stairs following...")
    
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
    
    # Add a test summon
    test_summon = Summon(game.player.x + 1, game.player.y, 2, 1)
    test_summon.name = "Stair Companion"
    test_summon.char = 'S'
    test_summon.color_pair = 4
    game.summons.append(test_summon)
    
    # Record initial state
    initial_depth = game.dungeon_depth
    initial_summon_count = len(game.summons)
    initial_summon_name = test_summon.name
    
    print(f"Initial - Depth: {initial_depth}, Summons: {initial_summon_count}")
    print(f"Summon: {initial_summon_name} at ({test_summon.x},{test_summon.y})")
    
    # Move player to stairs
    stairs_pos = game.current_map.stairs_down_pos
    if stairs_pos:
        game.player.x, game.player.y = stairs_pos
        print(f"Moved player to stairs at {stairs_pos}")
        
        # Trigger stairs descent
        game.handle_player_action(0, 0)
        
        # Check results
        final_depth = game.dungeon_depth
        final_summon_count = len(game.summons)
        
        print(f"Final - Depth: {final_depth}, Summons: {final_summon_count}")
        
        # Verify depth increased
        if final_depth == initial_depth + 1:
            print("✅ Player successfully descended stairs")
        else:
            print(f"❌ Stairs descent failed. Expected depth: {initial_depth + 1}, Got: {final_depth}")
            return False
        
        # Verify summon followed
        if final_summon_count == initial_summon_count:
            print("✅ Summon count preserved through stairs")
            
            # Check summon positioning
            if game.summons:
                final_summon = game.summons[0]
                final_summon_pos = (final_summon.x, final_summon.y)
                final_player_pos = (game.player.x, game.player.y)
                
                print(f"Final positions - Player: {final_player_pos}, Summon: {final_summon_pos}")
                
                # Check no overlap
                if final_summon_pos != final_player_pos:
                    print("✅ No overlap between player and summon after stairs")
                else:
                    print("❌ Player and summon are overlapping after stairs!")
                    return False
                
                # Check reasonable distance
                distance = abs(final_summon_pos[0] - final_player_pos[0]) + abs(final_summon_pos[1] - final_player_pos[1])
                if distance <= 3:
                    print(f"✅ Summon positioned appropriately near player (distance: {distance})")
                else:
                    print(f"⚠️  Summon is far from player (distance: {distance})")
            else:
                print("❌ No summons found after stairs descent")
                return False
        else:
            print(f"❌ Summon count changed. Expected: {initial_summon_count}, Got: {final_summon_count}")
            return False
    else:
        print("❌ No stairs found on map")
        return False
    
    return True

if __name__ == "__main__":
    print("Running summon following tests...\n")
    
    success = True
    success &= test_summon_portal_following()
    success &= test_summon_stairs_following()
    
    if success:
        print("\n✅ All summon following tests passed!")
    else:
        print("\n❌ Some summon following tests failed!")
        sys.exit(1)