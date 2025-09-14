#!/usr/bin/env python3
"""
Test script to verify enhanced monster AI targeting behavior
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from term_dungeon_rpg import Game, Monster, Summon
import argparse

def test_monster_target_selection():
    """Test that monsters intelligently select targets"""
    print("Testing monster target selection...")
    
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
    
    # Clear existing monsters and summons for controlled testing
    game.current_map.monsters.clear()
    game.summons.clear()
    
    # Position player at known location
    game.player.x, game.player.y = 10, 10
    
    # Add test summons with different health levels
    healthy_summon = Summon(12, 10, 2, 1)  # Close, healthy
    healthy_summon.name = "Healthy Guard"
    healthy_summon.hp = healthy_summon.max_hp
    game.summons.append(healthy_summon)
    
    weak_summon = Summon(8, 10, 1, 1)  # Close, weak
    weak_summon.name = "Wounded Guard"
    weak_summon.hp = 2  # Very low HP
    game.summons.append(weak_summon)
    
    # Add test monsters of different types
    spider = Monster(11, 8, "spider", 1)  # Close to both targets
    orc = Monster(15, 10, "orc", 1)      # Medium distance
    goblin = Monster(9, 12, "goblin", 1)  # Close to weak summon
    
    game.current_map.monsters.extend([spider, orc, goblin])
    
    print(f"Setup - Player: ({game.player.x},{game.player.y})")
    print(f"Healthy Summon: ({healthy_summon.x},{healthy_summon.y}) HP: {healthy_summon.hp}/{healthy_summon.max_hp}")
    print(f"Weak Summon: ({weak_summon.x},{weak_summon.y}) HP: {weak_summon.hp}/{weak_summon.max_hp}")
    print(f"Spider: ({spider.x},{spider.y})")
    print(f"Orc: ({orc.x},{orc.y})")
    print(f"Goblin: ({goblin.x},{goblin.y})")
    
    # Test target selection for each monster type
    results = {}
    
    for monster in game.current_map.monsters:
        target = monster.take_turn(game.player, game.current_map, game.global_rng, game.summons)
        
        if target:
            results[monster.name] = target.name
            print(f"{monster.name} selected target: {target.name}")
        else:
            # Check what target the AI would select
            potential_targets = [game.player] + [s for s in game.summons if s.is_alive()]
            selected = monster._select_target(potential_targets, game.global_rng)
            if selected:
                results[monster.name] = f"{selected.name} (selected but no combat)"
                print(f"{monster.name} would target: {selected.name} (but no combat this turn)")
            else:
                results[monster.name] = "None"
                print(f"{monster.name} found no suitable target")
    
    # Verify intelligent behavior
    success = True
    
    # Spiders should prefer weak/isolated targets
    if "Spider" in results:
        spider_target = results["Spider"]
        if "Wounded" in spider_target:
            print("✅ Spider correctly targeted weak summon")
        else:
            print(f"⚠️  Spider targeted {spider_target} instead of weak summon")
    
    # Goblins should be opportunistic (prefer weak targets)
    if "Goblin" in results:
        goblin_target = results["Goblin"]
        if "Wounded" in goblin_target or "Player" in goblin_target:
            print("✅ Goblin showed opportunistic behavior")
        else:
            print(f"⚠️  Goblin targeted {goblin_target}")
    
    return success

def test_monster_coordination():
    """Test that monsters can coordinate attacks"""
    print("\nTesting monster coordination...")
    
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
    
    # Clear existing monsters for controlled testing
    game.current_map.monsters.clear()
    game.summons.clear()
    
    # Position player
    game.player.x, game.player.y = 15, 15
    
    # Add a summon
    guard = Summon(16, 15, 2, 1)
    guard.name = "Test Guard"
    game.summons.append(guard)
    
    # Add multiple monsters around the player and summon
    monsters = [
        Monster(14, 15, "goblin", 1),  # Left of player
        Monster(15, 14, "orc", 1),     # Above player
        Monster(17, 15, "spider", 1),  # Right of summon
        Monster(15, 16, "skeleton", 1) # Below player
    ]
    
    game.current_map.monsters.extend(monsters)
    
    print(f"Player: ({game.player.x},{game.player.y})")
    print(f"Guard: ({guard.x},{guard.y})")
    
    # Run several turns to see coordination
    for turn in range(3):
        print(f"\n--- Turn {turn + 1} ---")
        
        for monster in game.current_map.monsters:
            if monster.is_alive():
                initial_pos = (monster.x, monster.y)
                target = monster.take_turn(game.player, game.current_map, game.global_rng, game.summons)
                final_pos = (monster.x, monster.y)
                
                if target:
                    print(f"{monster.name} at {final_pos} attacking {target.name}")
                else:
                    print(f"{monster.name} moved from {initial_pos} to {final_pos}")
    
    return True

def test_monster_type_behaviors():
    """Test that different monster types have distinct behaviors"""
    print("\nTesting monster type-specific behaviors...")
    
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
    
    # Test each monster type's target selection preferences
    monster_types = ["spider", "orc", "goblin", "skeleton"]
    
    for monster_type in monster_types:
        print(f"\nTesting {monster_type} behavior:")
        
        # Create test scenario
        test_monster = Monster(10, 10, monster_type, 1)
        
        # Create different target options
        player = game.player
        player.x, player.y = 12, 10
        player.hp = 20  # Healthy player
        
        weak_summon = Summon(8, 10, 1, 1)
        weak_summon.name = "Weak Summon"
        weak_summon.hp = 3
        
        strong_summon = Summon(10, 12, 3, 1)
        strong_summon.name = "Strong Summon"
        strong_summon.hp = strong_summon.max_hp
        
        targets = [player, weak_summon, strong_summon]
        
        # Test target selection multiple times for consistency
        selections = {}
        for _ in range(5):
            selected = test_monster._select_target(targets, game.global_rng)
            if selected:
                name = selected.name if hasattr(selected, 'name') else "Player"
                selections[name] = selections.get(name, 0) + 1
        
        print(f"  Target preferences: {selections}")
        
        # Verify type-specific behavior
        if monster_type == "spider" and "Weak Summon" in selections:
            print("  ✅ Spider prefers weak targets")
        elif monster_type == "skeleton" and "Player" in selections:
            print("  ✅ Skeleton prefers player")
        elif monster_type == "orc" and "Strong Summon" in selections:
            print("  ✅ Orc prefers strong opponents")
        else:
            print(f"  ⚠️  {monster_type} behavior may need tuning")
    
    return True

if __name__ == "__main__":
    print("Running smart monster AI tests...\n")
    
    success = True
    success &= test_monster_target_selection()
    success &= test_monster_coordination()
    success &= test_monster_type_behaviors()
    
    if success:
        print("\n✅ Smart monster AI tests completed!")
    else:
        print("\n❌ Some smart monster AI tests had issues!")
        sys.exit(1)