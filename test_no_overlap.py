#!/usr/bin/env python3
"""
Test script to verify no entity overlaps occur
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from term_dungeon_rpg import Game
import argparse

def test_no_entity_overlaps():
    """Test that no entities share the same tile"""
    print("Testing entity overlap prevention...")
    
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
    
    # Check initial positions
    all_positions = []
    
    # Player position
    player_pos = (game.player.x, game.player.y)
    all_positions.append(("Player", player_pos))
    print(f"Player at: {player_pos}")
    
    # Summon positions
    for i, summon in enumerate(game.summons):
        summon_pos = (summon.x, summon.y)
        all_positions.append((f"Summon-{i}", summon_pos))
        print(f"Summon {i} ({summon.name}) at: {summon_pos}")
    
    # Monster positions
    for i, monster in enumerate(game.current_map.monsters):
        monster_pos = (monster.x, monster.y)
        all_positions.append((f"Monster-{i}", monster_pos))
        print(f"Monster {i} ({monster.name}) at: {monster_pos}")
    
    # Check for overlaps
    position_counts = {}
    for entity_name, pos in all_positions:
        if pos in position_counts:
            position_counts[pos].append(entity_name)
        else:
            position_counts[pos] = [entity_name]
    
    overlaps_found = False
    for pos, entities in position_counts.items():
        if len(entities) > 1:
            print(f"❌ OVERLAP at {pos}: {', '.join(entities)}")
            overlaps_found = True
    
    if not overlaps_found:
        print("✅ No overlaps found in initial positions")
    
    # Test movement doesn't create overlaps
    print("\nTesting movement collision prevention...")
    
    # Try to move player in various directions
    for dx, dy in [(1, 0), (0, 1), (-1, 0), (0, -1)]:
        initial_pos = (game.player.x, game.player.y)
        game.handle_player_action(dx, dy)
        new_pos = (game.player.x, game.player.y)
        
        # Check if player moved into any summon
        for summon in game.summons:
            if (summon.x, summon.y) == new_pos and new_pos != initial_pos:
                print(f"❌ Player moved into summon at {new_pos}")
                overlaps_found = True
        
        print(f"Player move ({dx},{dy}): {initial_pos} -> {new_pos}")
    
    # Test summon movement
    print("\nTesting summon AI collision prevention...")
    
    for i in range(3):  # Test a few turns
        print(f"\n--- Turn {i+1} ---")
        
        # Process summon turns
        for j, summon in enumerate(game.summons):
            if summon.is_alive():
                initial_pos = (summon.x, summon.y)
                target = summon.take_turn(game.player, game.current_map, game.current_map.monsters, game.global_rng, game.summons)
                new_pos = (summon.x, summon.y)
                
                # Check if summon moved into player
                if new_pos == (game.player.x, game.player.y) and new_pos != initial_pos:
                    print(f"❌ Summon {j} moved into player at {new_pos}")
                    overlaps_found = True
                
                # Check if summon moved into another summon
                for k, other_summon in enumerate(game.summons):
                    if k != j and other_summon.is_alive() and (other_summon.x, other_summon.y) == new_pos and new_pos != initial_pos:
                        print(f"❌ Summon {j} moved into summon {k} at {new_pos}")
                        overlaps_found = True
                
                print(f"Summon {j} move: {initial_pos} -> {new_pos}")
    
    return not overlaps_found

if __name__ == "__main__":
    print("Running entity overlap prevention tests...\n")
    
    success = test_no_entity_overlaps()
    
    if success:
        print("\n✅ All overlap prevention tests passed!")
    else:
        print("\n❌ Some overlap prevention tests failed!")
        sys.exit(1)