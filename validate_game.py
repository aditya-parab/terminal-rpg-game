#!/usr/bin/env python3
"""
Final validation script to ensure the game is working correctly
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from term_dungeon_rpg import Game
import argparse

def validate_game():
    """Run comprehensive validation of game functionality"""
    print("🎮 Terminal Dungeon RPG - Final Validation")
    print("=" * 50)
    
    # Test 1: Game initialization
    print("✅ Testing game initialization...")
    args = argparse.Namespace(
        seed=12345, reset=True, no_save=True, headless=True, 
        debug=False, minimal_curses=False, debug_draw=False
    )
    game = Game(args, stdscr=None)
    assert game.player.hp == 30, "Player should start with 30 HP"
    assert game.dungeon_depth == 1, "Should start at depth 1"
    print("   ✓ Game initializes correctly")
    
    # Test 2: Movement without phantom combat
    print("✅ Testing movement system...")
    initial_hp = game.player.hp
    for i in range(10):
        # Record monster positions before move
        monster_distances_before = [
            abs(m.x - game.player.x) + abs(m.y - game.player.y) 
            for m in game.current_map.monsters if m.is_alive()
        ]
        
        # Try to move in different directions
        moved = False
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            new_x = game.player.x + dx
            new_y = game.player.y + dy
            if (0 <= new_x < 60 and 0 <= new_y < 40 and 
                game.current_map.tiles[new_y][new_x] != '#'):
                game.handle_player_action(dx, dy)
                moved = True
                break
        
        if not moved:
            continue
            
        # Check if damage was legitimate (monster became adjacent)
        if game.player.hp < initial_hp:
            adjacent_monsters = [
                m for m in game.current_map.monsters if m.is_alive() and
                ((abs(m.x - game.player.x) == 1 and abs(m.y - game.player.y) == 0) or
                 (abs(m.x - game.player.x) == 0 and abs(m.y - game.player.y) == 1))
            ]
            
            if not adjacent_monsters:
                print(f"   ❌ PHANTOM DAMAGE DETECTED on move {i+1}!")
                return False
            else:
                print(f"   ✓ Legitimate combat with {adjacent_monsters[0].name}")
                initial_hp = game.player.hp  # Update for next check
    
    print("   ✓ Combat system working correctly - no phantom damage")
    
    # Test 3: Equipment system
    print("✅ Testing equipment system...")
    base_atk = game.player.get_attack()
    base_def = game.player.get_defense()
    
    # Add and equip items
    from term_dungeon_rpg import Item
    sword = Item(0, 0, "sword")
    shield = Item(0, 0, "shield")
    
    game.player.add_item(sword)
    game.player.add_item(shield)
    
    sword.use(game.player, game)
    shield.use(game.player, game)
    
    assert game.player.get_attack() > base_atk, "Weapon should increase attack"
    assert game.player.get_defense() > base_def, "Armor should increase defense"
    print(f"   ✓ Equipment working: ATK {base_atk}→{game.player.get_attack()}, DEF {base_def}→{game.player.get_defense()}")
    
    # Test 4: Inventory system
    print("✅ Testing inventory system...")
    from term_dungeon_rpg import Item
    potion = Item(0, 0, "potion", 3)
    game.player.add_item(potion)
    
    # Damage player and use potion
    game.player.hp = 20
    potion.use(game.player, game)
    assert game.player.hp == 30, "Potion should heal to full HP"
    assert potion.qty == 2, "Potion quantity should decrease"
    print("   ✓ Inventory and item usage working correctly")
    
    # Test 5: Combat system
    print("✅ Testing combat system...")
    from term_dungeon_rpg import Monster
    monster = Monster(0, 0, "goblin", 1)
    initial_monster_hp = monster.hp
    
    game.combat(game.player, monster)
    assert monster.hp < initial_monster_hp, "Combat should damage monster"
    print("   ✓ Combat system working correctly")
    
    # Test 6: Game over system
    print("✅ Testing game over system...")
    game.player.hp = 1
    strong_monster = Monster(0, 0, "orc", 10)
    game.combat(strong_monster, game.player)
    assert game.player.hp == 0, "Player should die"
    assert game.game_over == True, "Game over flag should be set"
    print("   ✓ Game over system working correctly")
    
    print("\n🎉 ALL VALIDATIONS PASSED!")
    print("The game is ready to play!")
    return True

if __name__ == "__main__":
    try:
        validate_game()
        print("\n🚀 You can now run: python3 term_dungeon_rpg.py")
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        sys.exit(1)
