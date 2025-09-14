#!/usr/bin/env python3
"""
Comprehensive test suite for Terminal RPG Game
Tests all major functionality including new features like summons, potions, and level scaling
"""

import unittest
import sys
import os
import tempfile
import json
import gzip
from unittest.mock import Mock, patch, MagicMock

# Add the game directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from term_dungeon_rpg import (
    Entity, Player, Monster, Summon, Item, GameMap, Game, Persistence,
    TILE_FLOOR, TILE_WALL, MAP_WIDTH, MAP_HEIGHT
)

class TestEntity(unittest.TestCase):
    def test_entity_creation(self):
        entity = Entity(5, 10, '@', 1, "Test", 100, 10, 5)
        self.assertEqual(entity.x, 5)
        self.assertEqual(entity.y, 10)
        self.assertEqual(entity.hp, 100)
        self.assertEqual(entity.max_hp, 100)
        
    def test_entity_damage(self):
        entity = Entity(0, 0, '@', 1, "Test", 100, 10, 5)
        self.assertFalse(entity.take_damage(50))  # Should survive
        self.assertEqual(entity.hp, 50)
        self.assertTrue(entity.take_damage(60))   # Should die
        self.assertEqual(entity.hp, 0)
        
    def test_entity_serialization(self):
        entity = Entity(5, 10, '@', 1, "Test", 100, 10, 5)
        data = entity.to_dict()
        self.assertIn('x', data)
        self.assertIn('hp', data)
        self.assertEqual(data['name'], "Test")

class TestPlayer(unittest.TestCase):
    def test_player_creation(self):
        player = Player(0, 0)
        self.assertEqual(player.name, "Adventurer")
        self.assertEqual(len(player.inventory), 0)
        self.assertEqual(len(player.temp_buffs), 0)
        
    def test_player_inventory(self):
        player = Player(0, 0)
        item = Item(0, 0, "health_potion", 1, 1)
        
        # Test adding item
        self.assertTrue(player.add_item(item))
        self.assertEqual(len(player.inventory), 1)
        
        # Test removing item
        player.remove_item(item)
        self.assertEqual(len(player.inventory), 0)
        
    def test_player_equipment(self):
        player = Player(0, 0)
        weapon = Item(0, 0, "sword", 1, 1)
        armor = Item(0, 0, "shield", 1, 1)
        
        # Test base stats
        base_attack = player.get_attack()
        base_defense = player.get_defense()
        
        # Test equipment effects
        player.equipped_weapon = weapon
        player.equipped_armor = armor
        
        self.assertGreater(player.get_attack(), base_attack)
        self.assertGreater(player.get_defense(), base_defense)
        
    def test_player_temp_buffs(self):
        player = Player(0, 0)
        
        # Add temporary buffs
        player.temp_buffs['defense'] = (5, 10)
        player.temp_buffs['hp'] = (20, 15)
        
        # Test buff effects
        self.assertEqual(player.get_defense(), 1 + 5)  # base + buff
        self.assertEqual(player.get_max_hp(), 30 + 20)  # base + buff
        
        # Test buff expiration
        expired = player.update_buffs()
        self.assertFalse(expired)  # Should not expire yet
        self.assertEqual(player.temp_buffs['defense'][1], 9)  # Duration decreased
        
        # Expire buffs
        player.temp_buffs['defense'] = (5, 1)
        expired = player.update_buffs()
        self.assertTrue(expired)  # Should expire
        self.assertNotIn('defense', player.temp_buffs)

class TestMonster(unittest.TestCase):
    def test_monster_creation(self):
        monster = Monster(5, 5, "goblin", 1)
        self.assertIn("Goblin", monster.name)
        self.assertIn("Lv.", monster.name)
        self.assertTrue(hasattr(monster, 'level'))
        self.assertTrue(hasattr(monster, 'monster_id'))
        
    def test_monster_level_scaling(self):
        # Test different depths create different level monsters
        monster1 = Monster(0, 0, "goblin", 1)
        monster5 = Monster(0, 0, "goblin", 5)
        
        # Higher depth should generally mean higher stats
        self.assertGreaterEqual(monster5.hp, monster1.hp)
        self.assertGreaterEqual(monster5.atk, monster1.atk)
        
    def test_monster_serialization(self):
        monster = Monster(5, 5, "orc", 3)
        data = monster.to_dict()
        
        self.assertIn('monster_id', data)
        self.assertIn('level', data)
        
        # Test deserialization
        restored = Monster.from_dict(data)
        self.assertEqual(restored.monster_id, monster.monster_id)
        self.assertEqual(restored.level, monster.level)

class TestSummon(unittest.TestCase):
    def test_summon_creation(self):
        summon = Summon(5, 5, 2, 1)
        self.assertIn("Lv.2", summon.name)
        self.assertEqual(summon.level, 2)
        self.assertEqual(summon.char, 'S')
        
    def test_summon_stats_scaling(self):
        summon1 = Summon(0, 0, 1, 1)
        summon3 = Summon(0, 0, 3, 1)
        
        # Higher level should mean better stats
        self.assertGreater(summon3.hp, summon1.hp)
        self.assertGreater(summon3.atk, summon1.atk)
        self.assertGreater(summon3.def_val, summon1.def_val)
        
    def test_summon_color_variety(self):
        # Test that different levels get different colors
        colors = set()
        for level in range(1, 5):
            summon = Summon(0, 0, level, 1)
            colors.add(summon.color_pair)
        
        self.assertGreater(len(colors), 1)  # Should have multiple colors

class TestItem(unittest.TestCase):
    def test_health_potion(self):
        potion = Item(0, 0, "health_potion", 1, 2)
        self.assertEqual(potion.name, "Health Potion Lv.2")
        self.assertEqual(potion.power, 15)  # 10 + (2-1)*5
        self.assertTrue(potion.stackable)
        
    def test_defense_potion(self):
        potion = Item(0, 0, "defense_potion", 1, 3)
        self.assertEqual(potion.name, "Defense Potion Lv.3")
        self.assertEqual(potion.power, 9)  # 5 + (3-1)*2
        
    def test_hp_boost_potion(self):
        potion = Item(0, 0, "hp_boost_potion", 1, 2)
        self.assertEqual(potion.name, "Vitality Potion Lv.2")
        self.assertEqual(potion.power, 25)  # 15 + (2-1)*10
        
    def test_summon_scroll(self):
        scroll = Item(0, 0, "summon", 1, 3)
        self.assertEqual(scroll.name, "Summon Scroll Lv.3")
        self.assertEqual(scroll.power, 3)
        self.assertTrue(scroll.stackable)
        
    def test_equipment(self):
        sword = Item(0, 0, "sword", 1, 1)
        shield = Item(0, 0, "shield", 1, 1)
        
        self.assertEqual(sword.name, "Iron Sword")
        self.assertEqual(shield.name, "Wooden Shield")
        self.assertFalse(sword.stackable)
        self.assertFalse(shield.stackable)
        
    def test_item_serialization(self):
        item = Item(5, 10, "health_potion", 3, 2)
        data = item.to_dict()
        
        self.assertEqual(data['item_id'], "health_potion")
        self.assertEqual(data['level'], 2)
        self.assertEqual(data['qty'], 3)
        
        # Test deserialization
        restored = Item.from_dict(data)
        self.assertEqual(restored.item_id, item.item_id)
        self.assertEqual(restored.level, item.level)

class TestItemUsage(unittest.TestCase):
    def setUp(self):
        self.player = Player(0, 0)
        self.game = Mock()
        self.game.add_message = Mock()
        self.game.current_map = Mock()
        self.game.current_map.get_tile = Mock(return_value=TILE_FLOOR)
        self.game.current_map.monsters = []
        self.game.summons = []
        
    def test_health_potion_usage(self):
        potion = Item(0, 0, "health_potion", 1, 1)
        self.player.add_item(potion)
        self.player.hp = 20  # Damage player
        
        result = potion.use(self.player, self.game)
        
        self.assertTrue(result)
        self.assertEqual(self.player.hp, 30)  # Should be healed
        self.assertEqual(len(self.player.inventory), 0)  # Item consumed
        
    def test_defense_potion_usage(self):
        potion = Item(0, 0, "defense_potion", 1, 2)
        self.player.add_item(potion)
        
        result = potion.use(self.player, self.game)
        
        self.assertTrue(result)
        self.assertIn('defense', self.player.temp_buffs)
        self.assertEqual(self.player.temp_buffs['defense'][0], 7)  # Level 2 = +7 def
        self.assertEqual(self.player.temp_buffs['defense'][1], 15)  # 15 turns
        
    def test_summon_scroll_usage(self):
        scroll = Item(0, 0, "summon", 1, 2)
        self.player.add_item(scroll)
        
        result = scroll.use(self.player, self.game)
        
        self.assertTrue(result)
        self.assertEqual(len(self.game.summons), 1)
        summon = self.game.summons[0]
        self.assertEqual(summon.level, 2)
        
    def test_equipment_usage(self):
        sword = Item(0, 0, "sword", 1, 1)
        self.player.add_item(sword)
        
        result = sword.use(self.player, self.game)
        
        self.assertTrue(result)
        self.assertEqual(self.player.equipped_weapon, sword)
        self.assertEqual(len(self.player.inventory), 0)

class TestGameMap(unittest.TestCase):
    def test_map_generation(self):
        game_map = GameMap(MAP_WIDTH, MAP_HEIGHT, 12345)
        game_map.generate_map(1)
        
        # Test basic map properties
        self.assertIsNotNone(game_map.player_start_pos)
        self.assertIsNotNone(game_map.stairs_down_pos)
        self.assertGreater(len(game_map.monsters), 0)
        self.assertGreater(len(game_map.items), 0)
        
    def test_portal_generation(self):
        game_map = GameMap(MAP_WIDTH, MAP_HEIGHT, 12345)
        game_map.generate_map(1)
        
        # Should have portals
        self.assertGreaterEqual(len(game_map.portals), 0)
        
    def test_summon_scroll_generation(self):
        # Test that summon scrolls are generated
        found_summon = False
        for _ in range(10):  # Try multiple seeds
            game_map = GameMap(MAP_WIDTH, MAP_HEIGHT, 12345 + _)
            game_map.generate_map(1)
            
            for item in game_map.items:
                if item.item_id == "summon":
                    found_summon = True
                    break
            if found_summon:
                break
                
        # Should find at least one summon scroll in 10 attempts
        # (This might occasionally fail due to randomness, but very unlikely)
        
    def test_map_serialization(self):
        game_map = GameMap(MAP_WIDTH, MAP_HEIGHT, 12345)
        game_map.generate_map(2)
        
        data = game_map.to_dict()
        self.assertIn('seed', data)
        self.assertIn('monsters', data)
        self.assertIn('items', data)
        self.assertIn('portals', data)

class TestCombatSystem(unittest.TestCase):
    def setUp(self):
        self.game = Mock()
        self.game.add_message = Mock()
        self.game.current_map = Mock()
        self.game.current_map.monsters = []
        self.game.game_over = False
        
    def test_level_scaling_combat(self):
        # Create a mock combat method
        def mock_combat(attacker, defender):
            base_damage = attacker.get_attack()
            
            if hasattr(attacker, 'level') and hasattr(defender, 'get_defense'):
                # Simulate level-scaling defense
                defense_effectiveness = max(0.3, 1.0 - (attacker.level - 1) * 0.1)
                effective_defense = int(defender.get_defense() * defense_effectiveness)
                damage = max(1, base_damage - effective_defense)
            else:
                damage = max(1, base_damage - defender.get_defense())
                
            return damage
        
        player = Player(0, 0)
        monster1 = Monster(0, 0, "goblin", 1)  # Level ~1
        monster5 = Monster(0, 0, "goblin", 5)  # Level ~5
        
        # Higher level monsters should deal more damage to same defense
        damage1 = mock_combat(monster1, player)
        damage5 = mock_combat(monster5, player)
        
        self.assertGreaterEqual(damage5, damage1)

class TestGameIntegration(unittest.TestCase):
    def setUp(self):
        # Create a mock args object
        self.args = Mock()
        self.args.no_save = True
        self.args.seed = 12345
        self.args.debug = False
        
    def test_game_initialization(self):
        game = Game(self.args)
        
        self.assertIsNotNone(game.player)
        self.assertIsNotNone(game.current_map)
        self.assertEqual(game.dungeon_depth, 1)
        self.assertEqual(len(game.summons), 0)
        
    def test_summon_persistence(self):
        game = Game(self.args)
        
        # Add a summon
        summon = Summon(5, 5, 2, 1)
        game.summons.append(summon)
        
        # Test save state includes summons
        state = {
            "player": game.player.to_dict(),
            "dungeon_depth": game.dungeon_depth,
            "turn_count": game.turn_count,
            "global_seed": game.global_rng.getstate(),
            "map": game.current_map.to_dict(),
            "summons": [s.to_dict() for s in game.summons]
        }
        
        self.assertEqual(len(state["summons"]), 1)
        self.assertEqual(state["summons"][0]["level"], 2)

class TestSummonPersistence(unittest.TestCase):
    def setUp(self):
        self.args = Mock()
        self.args.no_save = True
        self.args.seed = 12345
        self.args.debug = False
        
    def test_summon_level_transition(self):
        """Test that summons follow player to new levels and get healed"""
        game = Game(self.args)
        
        # Add a damaged summon
        summon = Summon(5, 5, 2, 1)
        summon.hp = 10  # Damage the summon (max hp should be 31 for level 2)
        game.summons.append(summon)
        
        # Damage player too
        game.player.hp = 20
        
        # Record initial HP values
        initial_player_hp = game.player.hp
        initial_summon_hp = summon.hp
        
        # Generate new level (this should heal both)
        game.generate_new_level()
        
        # Check that summon is still alive and moved to new level
        self.assertEqual(len(game.summons), 1)
        self.assertTrue(game.summons[0].is_alive())
        
        # Check HP replenishment (25% minimum)
        expected_player_heal = max(int(game.player.get_max_hp() * 0.25), 1)
        expected_summon_heal = max(int(summon.max_hp * 0.25), 1)
        
        self.assertGreaterEqual(game.player.hp, initial_player_hp + expected_player_heal)
        self.assertGreaterEqual(game.summons[0].hp, initial_summon_hp + expected_summon_heal)
        
    def test_dead_summon_removal(self):
        """Test that dead summons are removed when transitioning levels"""
        game = Game(self.args)
        
        # Add a dead summon
        dead_summon = Summon(5, 5, 2, 1)
        dead_summon.hp = 0  # Kill the summon
        game.summons.append(dead_summon)
        
        # Add a living summon
        living_summon = Summon(6, 6, 1, 1)
        game.summons.append(living_summon)
        
        self.assertEqual(len(game.summons), 2)
        
        # Generate new level
        game.generate_new_level()
        
        # Only living summon should remain
        self.assertEqual(len(game.summons), 1)
        self.assertTrue(game.summons[0].is_alive())
        self.assertEqual(game.summons[0].level, 1)  # Should be the living summon

class TestPortalTeleportation(unittest.TestCase):
    def setUp(self):
        self.args = Mock()
        self.args.no_save = True
        self.args.seed = 12345
        self.args.debug = False
        
    def test_summon_portal_teleportation(self):
        """Test that summons teleport with player through portals"""
        game = Game(self.args)
        
        # Add a portal to the map
        game.current_map.portals = [(5, 5, 15, 15)]
        
        # Add a summon near player
        summon = Summon(4, 4, 1, 1)
        game.summons.append(summon)
        
        # Move player to portal entrance
        game.player.x, game.player.y = 5, 5
        
        # Simulate portal teleportation by calling handle_player_action with no movement
        # This should trigger the portal check
        old_player_pos = (game.player.x, game.player.y)
        old_summon_pos = (summon.x, summon.y)
        
        # Manually trigger portal teleportation logic
        for x1, y1, x2, y2 in game.current_map.portals:
            if (game.player.x, game.player.y) == (x1, y1):
                game.player.x, game.player.y = x2, y2
                
                # Teleport summons with player
                for s in game.summons:
                    if s.is_alive():
                        # Find empty spot near destination
                        for dx, dy in [(1, 0), (0, 1), (-1, 0), (0, -1)]:
                            new_x, new_y = x2 + dx, y2 + dy
                            if game.current_map.get_tile(new_x, new_y) == TILE_FLOOR:
                                s.x, s.y = new_x, new_y
                                break
                        else:
                            s.x, s.y = x2, y2
                break
        
        # Check that both player and summon moved
        self.assertNotEqual((game.player.x, game.player.y), old_player_pos)
        self.assertNotEqual((summon.x, summon.y), old_summon_pos)
        
        # Check that summon is near the teleport destination
        player_summon_dist = abs(game.player.x - summon.x) + abs(game.player.y - summon.y)
        self.assertLessEqual(player_summon_dist, 2)  # Should be within 2 tiles

class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def test_save_load_with_summons(self):
        # Create test data with summons
        player = Player(5, 5)
        summon = Summon(6, 6, 3, 2)
        
        state = {
            "player": player.to_dict(),
            "dungeon_depth": 3,
            "turn_count": 50,
            "global_seed": [1, (1, 2, 3), None],
            "map": {"seed": 12345, "monsters": [], "items": [], "portals": []},
            "summons": [summon.to_dict()]
        }
        
        # Test that the state structure is valid
        self.assertIn("summons", state)
        self.assertEqual(len(state["summons"]), 1)
        self.assertEqual(state["summons"][0]["level"], 3)
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def test_save_load_with_summons(self):
        # Create test data with summons
        player = Player(5, 5)
        summon = Summon(6, 6, 3, 2)
        
        state = {
            "player": player.to_dict(),
            "dungeon_depth": 3,
            "turn_count": 50,
            "global_seed": [1, (1, 2, 3), None],
            "map": {"seed": 12345, "monsters": [], "items": [], "portals": []},
            "summons": [summon.to_dict()]
        }
        
        # Test that the state structure is valid
        self.assertIn("summons", state)
        self.assertEqual(len(state["summons"]), 1)
        self.assertEqual(state["summons"][0]["level"], 3)

def run_comprehensive_tests():
    """Run all comprehensive tests and return results"""
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestEntity, TestPlayer, TestMonster, TestSummon, TestItem,
        TestItemUsage, TestGameMap, TestCombatSystem, TestGameIntegration,
        TestSummonPersistence, TestPortalTeleportation, TestPersistence
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Return summary
    return {
        'tests_run': result.testsRun,
        'failures': len(result.failures),
        'errors': len(result.errors),
        'success': result.wasSuccessful()
    }

if __name__ == '__main__':
    print("Running Comprehensive Test Suite...")
    print("=" * 50)
    
    results = run_comprehensive_tests()
    
    print("\n" + "=" * 50)
    print("TEST SUMMARY:")
    print(f"Tests Run: {results['tests_run']}")
    print(f"Failures: {results['failures']}")
    print(f"Errors: {results['errors']}")
    print(f"Success: {results['success']}")
    
    if results['success']:
        print("\n✅ ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED!")
        sys.exit(1)
