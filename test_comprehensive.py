#!/usr/bin/env python3
"""
Comprehensive test suite for Terminal Dungeon RPG
Tests all major game functionality including edge cases
"""

import unittest
import sys
import os
import tempfile
import json
import random
from pathlib import Path

# Add the current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from term_dungeon_rpg import (
    Entity, Player, Monster, Item, GameMap, Persistence, Game,
    TILE_WALL, TILE_FLOOR, TILE_PLAYER, TILE_STAIRS_DOWN,
    MAP_WIDTH, MAP_HEIGHT, INVENTORY_SIZE,
    CHECKPOINT_FILE, SCOREBOARD_FILE
)
import argparse

class TestEntity(unittest.TestCase):
    """Test the base Entity class"""
    
    def setUp(self):
        self.entity = Entity(5, 10, '@', 1, "Test Entity", 20, 5, 2)
    
    def test_entity_initialization(self):
        """Test entity is created with correct attributes"""
        self.assertEqual(self.entity.x, 5)
        self.assertEqual(self.entity.y, 10)
        self.assertEqual(self.entity.char, '@')
        self.assertEqual(self.entity.color_pair, 1)
        self.assertEqual(self.entity.name, "Test Entity")
        self.assertEqual(self.entity.hp, 20)
        self.assertEqual(self.entity.max_hp, 20)
        self.assertEqual(self.entity.atk, 5)
        self.assertEqual(self.entity.def_val, 2)
    
    def test_entity_movement_valid(self):
        """Test entity can move to valid positions"""
        # Create a simple map with floor tiles
        game_map = GameMap(20, 20, 123)
        game_map.tiles = [[TILE_FLOOR for _ in range(20)] for _ in range(20)]
        
        # Test moving right
        result = self.entity.move(1, 0, game_map)
        self.assertTrue(result)
        self.assertEqual(self.entity.x, 6)
        self.assertEqual(self.entity.y, 10)
    
    def test_entity_movement_blocked_by_wall(self):
        """Test entity cannot move into walls"""
        game_map = GameMap(20, 20, 123)
        game_map.tiles = [[TILE_WALL for _ in range(20)] for _ in range(20)]
        
        original_x, original_y = self.entity.x, self.entity.y
        result = self.entity.move(1, 0, game_map)
        self.assertFalse(result)
        self.assertEqual(self.entity.x, original_x)
        self.assertEqual(self.entity.y, original_y)
    
    def test_entity_movement_out_of_bounds(self):
        """Test entity cannot move out of map bounds"""
        game_map = GameMap(10, 10, 123)
        game_map.tiles = [[TILE_FLOOR for _ in range(10)] for _ in range(10)]
        
        # Move entity to edge
        self.entity.x, self.entity.y = 9, 9
        
        # Try to move out of bounds
        result = self.entity.move(1, 0, game_map)
        self.assertFalse(result)
        self.assertEqual(self.entity.x, 9)
        
        result = self.entity.move(0, 1, game_map)
        self.assertFalse(result)
        self.assertEqual(self.entity.y, 9)
    
    def test_take_damage(self):
        """Test damage system"""
        initial_hp = self.entity.hp
        
        # Take non-fatal damage
        result = self.entity.take_damage(5)
        self.assertFalse(result)  # Should return False (not dead)
        self.assertEqual(self.entity.hp, initial_hp - 5)
        
        # Take fatal damage
        result = self.entity.take_damage(20)
        self.assertTrue(result)  # Should return True (dead)
        self.assertEqual(self.entity.hp, 0)
    
    def test_is_alive(self):
        """Test alive status"""
        self.assertTrue(self.entity.is_alive())
        
        self.entity.hp = 0
        self.assertFalse(self.entity.is_alive())
    
    def test_to_dict_serialization(self):
        """Test entity serialization"""
        data = self.entity.to_dict()
        expected_keys = {'x', 'y', 'char', 'color_pair', 'name', 'hp', 'max_hp', 'atk', 'def_val'}
        self.assertEqual(set(data.keys()), expected_keys)
        self.assertEqual(data['x'], 5)
        self.assertEqual(data['name'], "Test Entity")

class TestPlayer(unittest.TestCase):
    """Test the Player class"""
    
    def setUp(self):
        self.player = Player(10, 15)
    
    def test_player_initialization(self):
        """Test player is created with correct default values"""
        self.assertEqual(self.player.x, 10)
        self.assertEqual(self.player.y, 15)
        self.assertEqual(self.player.char, TILE_PLAYER)
        self.assertEqual(self.player.name, "Adventurer")
        self.assertEqual(self.player.hp, 30)
        self.assertEqual(self.player.max_hp, 30)
        self.assertEqual(self.player.atk, 4)
        self.assertEqual(self.player.def_val, 1)
        self.assertEqual(len(self.player.inventory), 0)
        self.assertEqual(self.player.depth_reached, 1)
        self.assertEqual(self.player.monsters_killed, 0)
        self.assertEqual(self.player.items_collected, 0)
        self.assertIsNone(self.player.equipped_weapon)
        self.assertIsNone(self.player.equipped_armor)
    
    def test_add_item_to_inventory(self):
        """Test adding items to inventory"""
        item = Item(0, 0, "potion")
        
        # Add item successfully
        result = self.player.add_item(item)
        self.assertTrue(result)
        self.assertEqual(len(self.player.inventory), 1)
        self.assertEqual(self.player.items_collected, 1)
    
    def test_inventory_full(self):
        """Test inventory capacity limit"""
        # Fill inventory to capacity
        for i in range(INVENTORY_SIZE):
            item = Item(0, 0, "sword")  # Non-stackable items
            self.player.add_item(item)
        
        # Try to add one more item
        extra_item = Item(0, 0, "shield")
        result = self.player.add_item(extra_item)
        self.assertFalse(result)
        self.assertEqual(len(self.player.inventory), INVENTORY_SIZE)
    
    def test_stackable_items(self):
        """Test stackable item behavior"""
        potion1 = Item(0, 0, "potion", 1)
        potion2 = Item(0, 0, "potion", 2)
        
        self.player.add_item(potion1)
        self.player.add_item(potion2)
        
        # Should have only one item in inventory but with quantity 3
        self.assertEqual(len(self.player.inventory), 1)
        self.assertEqual(self.player.inventory[0].qty, 3)
        self.assertEqual(self.player.items_collected, 3)
    
    def test_remove_item(self):
        """Test removing items from inventory"""
        item = Item(0, 0, "potion", 3)
        self.player.add_item(item)
        
        # Remove partial quantity
        self.player.remove_item(item, 1)
        self.assertEqual(item.qty, 2)
        self.assertEqual(len(self.player.inventory), 1)
        
        # Remove remaining quantity
        self.player.remove_item(item, 2)
        self.assertEqual(len(self.player.inventory), 0)
    
    def test_equipment_stats(self):
        """Test equipment affects stats"""
        base_atk = self.player.get_attack()
        base_def = self.player.get_defense()
        
        # Equip weapon
        weapon = Item(0, 0, "sword")
        weapon.power = 5
        self.player.equipped_weapon = weapon
        self.assertEqual(self.player.get_attack(), base_atk + 5)
        
        # Equip armor
        armor = Item(0, 0, "shield")
        armor.power = 3
        self.player.equipped_armor = armor
        self.assertEqual(self.player.get_defense(), base_def + 3)
    
    def test_player_serialization(self):
        """Test player serialization and deserialization"""
        # Add some items and equipment
        item = Item(0, 0, "potion")
        self.player.add_item(item)
        self.player.monsters_killed = 5
        
        # Serialize
        data = self.player.to_dict()
        
        # Deserialize
        new_player = Player.from_dict(data)
        
        self.assertEqual(new_player.x, self.player.x)
        self.assertEqual(new_player.monsters_killed, 5)
        self.assertEqual(len(new_player.inventory), 1)


class TestMonster(unittest.TestCase):
    """Test the Monster class"""
    
    def setUp(self):
        self.goblin = Monster(5, 5, "goblin", 1)
        self.orc = Monster(10, 10, "orc", 2)
    
    def test_monster_initialization(self):
        """Test monster creation with different types"""
        # Test goblin
        self.assertEqual(self.goblin.monster_id, "goblin")
        self.assertEqual(self.goblin.name, "Goblin")
        self.assertEqual(self.goblin.char, 'g')
        
        # Test orc with depth scaling
        self.assertEqual(self.orc.monster_id, "orc")
        self.assertEqual(self.orc.name, "Orc")
        self.assertEqual(self.orc.hp, 12)  # 10 base + 2 depth
        self.assertEqual(self.orc.atk, 5)   # 4 base + 1 (depth//2)
    
    def test_monster_ai_chasing(self):
        """Test monster AI when chasing player"""
        player = Player(7, 5)  # Close to goblin
        game_map = GameMap(20, 20, 123)
        game_map.tiles = [[TILE_FLOOR for _ in range(20)] for _ in range(20)]
        rng = random.Random(42)
        
        old_x, old_y = self.goblin.x, self.goblin.y
        self.goblin.take_turn(player, game_map, rng)
        
        # Goblin should move towards player
        self.assertNotEqual((self.goblin.x, self.goblin.y), (old_x, old_y))
        # Should be closer to player
        old_distance = abs(old_x - player.x) + abs(old_y - player.y)
        new_distance = abs(self.goblin.x - player.x) + abs(self.goblin.y - player.y)
        self.assertLessEqual(new_distance, old_distance)
    
    def test_monster_ai_wandering(self):
        """Test monster AI when player is far away"""
        player = Player(50, 50)  # Far from goblin
        game_map = GameMap(60, 60, 123)
        game_map.tiles = [[TILE_FLOOR for _ in range(60)] for _ in range(60)]
        rng = random.Random(42)
        
        old_x, old_y = self.goblin.x, self.goblin.y
        self.goblin.take_turn(player, game_map, rng)
        
        # Goblin should move randomly (may or may not move depending on RNG)
        # Just verify it doesn't crash and stays in bounds
        self.assertGreaterEqual(self.goblin.x, 0)
        self.assertGreaterEqual(self.goblin.y, 0)
    
    def test_monster_serialization(self):
        """Test monster serialization"""
        data = self.goblin.to_dict()
        new_monster = Monster.from_dict(data)
        
        self.assertEqual(new_monster.monster_id, self.goblin.monster_id)
        self.assertEqual(new_monster.x, self.goblin.x)
        self.assertEqual(new_monster.hp, self.goblin.hp)


class TestItem(unittest.TestCase):
    """Test the Item class"""
    
    def setUp(self):
        self.potion = Item(3, 4, "potion")
        self.sword = Item(5, 6, "sword")
        self.shield = Item(7, 8, "shield")
    
    def test_item_initialization(self):
        """Test item creation with different types"""
        # Test potion (stackable)
        self.assertEqual(self.potion.item_id, "potion")
        self.assertEqual(self.potion.name, "Health Potion")
        self.assertTrue(self.potion.stackable)
        self.assertEqual(self.potion.power, 10)
        
        # Test sword (non-stackable)
        self.assertEqual(self.sword.item_id, "sword")
        self.assertEqual(self.sword.name, "Iron Sword")
        self.assertFalse(self.sword.stackable)
        self.assertEqual(self.sword.power, 2)
    
    def test_potion_use(self):
        """Test using health potions"""
        # Create a mock game and player
        args = argparse.Namespace(seed=123, reset=True, no_save=True, headless=True, 
                                debug=False, minimal_curses=False, debug_draw=False)
        game = Game(args, stdscr=None)
        
        # Damage player
        game.player.hp = 20
        
        # Use potion
        result = self.potion.use(game.player, game)
        self.assertTrue(result)
        self.assertEqual(game.player.hp, 30)  # Should heal to max
    
    def test_potion_use_at_full_health(self):
        """Test potion use when at full health"""
        args = argparse.Namespace(seed=123, reset=True, no_save=True, headless=True, 
                                debug=False, minimal_curses=False, debug_draw=False)
        game = Game(args, stdscr=None)
        
        # Player at full health
        result = self.potion.use(game.player, game)
        self.assertFalse(result)  # Should not use potion
    
    def test_weapon_equip(self):
        """Test equipping weapons"""
        args = argparse.Namespace(seed=123, reset=True, no_save=True, headless=True, 
                                debug=False, minimal_curses=False, debug_draw=False)
        game = Game(args, stdscr=None)
        game.player.add_item(self.sword)
        
        old_attack = game.player.get_attack()
        result = self.sword.use(game.player, game)
        
        self.assertTrue(result)
        self.assertIsNotNone(game.player.equipped_weapon)
        self.assertGreater(game.player.get_attack(), old_attack)
    
    def test_armor_equip(self):
        """Test equipping armor"""
        args = argparse.Namespace(seed=123, reset=True, no_save=True, headless=True, 
                                debug=False, minimal_curses=False, debug_draw=False)
        game = Game(args, stdscr=None)
        game.player.add_item(self.shield)
        
        old_defense = game.player.get_defense()
        result = self.shield.use(game.player, game)
        
        self.assertTrue(result)
        self.assertIsNotNone(game.player.equipped_armor)
        self.assertGreater(game.player.get_defense(), old_defense)
    
    def test_item_serialization(self):
        """Test item serialization"""
        data = self.potion.to_dict()
        new_item = Item.from_dict(data)
        
        self.assertEqual(new_item.item_id, self.potion.item_id)
        self.assertEqual(new_item.x, self.potion.x)
        self.assertEqual(new_item.qty, self.potion.qty)


class TestGameMap(unittest.TestCase):
    """Test the GameMap class"""
    
    def setUp(self):
        self.game_map = GameMap(MAP_WIDTH, MAP_HEIGHT, 12345)
    
    def test_map_initialization(self):
        """Test map is created with correct dimensions"""
        self.assertEqual(self.game_map.width, MAP_WIDTH)
        self.assertEqual(self.game_map.height, MAP_HEIGHT)
        self.assertEqual(self.game_map.seed, 12345)
        self.assertEqual(len(self.game_map.tiles), MAP_HEIGHT)
        self.assertEqual(len(self.game_map.tiles[0]), MAP_WIDTH)
    
    def test_map_generation(self):
        """Test map generation creates valid layout"""
        self.game_map.generate_map(1)
        
        # Should have player start position
        self.assertIsNotNone(self.game_map.player_start_pos)
        start_x, start_y = self.game_map.player_start_pos
        self.assertGreaterEqual(start_x, 0)
        self.assertLess(start_x, MAP_WIDTH)
        self.assertGreaterEqual(start_y, 0)
        self.assertLess(start_y, MAP_HEIGHT)
        
        # Should have stairs
        self.assertIsNotNone(self.game_map.stairs_down_pos)
        
        # Should have some floor tiles
        floor_count = sum(row.count(TILE_FLOOR) for row in self.game_map.tiles)
        self.assertGreater(floor_count, 0)
        
        # Should have some monsters and items
        self.assertGreater(len(self.game_map.monsters), 0)
        self.assertGreater(len(self.game_map.items), 0)
    
    def test_map_generation_deterministic(self):
        """Test map generation is deterministic with same seed"""
        map1 = GameMap(20, 20, 999)
        map1.generate_map(1)
        
        map2 = GameMap(20, 20, 999)
        map2.generate_map(1)
        
        # Should generate identical maps
        self.assertEqual(map1.tiles, map2.tiles)
        self.assertEqual(map1.player_start_pos, map2.player_start_pos)
        self.assertEqual(map1.stairs_down_pos, map2.stairs_down_pos)
    
    def test_get_tile(self):
        """Test tile access with bounds checking"""
        self.game_map.generate_map(1)
        
        # Valid coordinates
        tile = self.game_map.get_tile(5, 5)
        self.assertIn(tile, [TILE_WALL, TILE_FLOOR, TILE_STAIRS_DOWN])
        
        # Out of bounds should return wall
        self.assertEqual(self.game_map.get_tile(-1, 5), TILE_WALL)
        self.assertEqual(self.game_map.get_tile(5, -1), TILE_WALL)
        self.assertEqual(self.game_map.get_tile(MAP_WIDTH, 5), TILE_WALL)
        self.assertEqual(self.game_map.get_tile(5, MAP_HEIGHT), TILE_WALL)
    
    def test_map_serialization(self):
        """Test map serialization"""
        self.game_map.generate_map(1)
        data = self.game_map.to_dict()
        new_map = GameMap.from_dict(data)
        
        self.assertEqual(new_map.seed, self.game_map.seed)
        self.assertEqual(len(new_map.monsters), len(self.game_map.monsters))
        self.assertEqual(len(new_map.items), len(self.game_map.items))


class TestGame(unittest.TestCase):
    """Test the main Game class"""
    
    def setUp(self):
        self.args = argparse.Namespace(
            seed=12345, reset=True, no_save=True, headless=True, 
            debug=False, minimal_curses=False, debug_draw=False
        )
        self.game = Game(self.args, stdscr=None)
    
    def test_game_initialization(self):
        """Test game initializes correctly"""
        self.assertIsNotNone(self.game.player)
        self.assertIsNotNone(self.game.current_map)
        self.assertEqual(self.game.dungeon_depth, 1)
        self.assertEqual(self.game.turn_count, 0)
        self.assertFalse(self.game.game_over)
        self.assertTrue(self.game.game_running)
    
    def test_new_game(self):
        """Test starting a new game"""
        # Modify some state
        self.game.dungeon_depth = 5
        self.game.turn_count = 100
        self.game.game_over = True
        
        # Start new game
        self.game.new_game()
        
        self.assertEqual(self.game.dungeon_depth, 1)
        self.assertEqual(self.game.turn_count, 0)
        self.assertFalse(self.game.game_over)
        self.assertIsNotNone(self.game.player)
        self.assertEqual(self.game.player.hp, self.game.player.max_hp)
    
    def test_player_movement_valid(self):
        """Test valid player movement"""
        old_pos = (self.game.player.x, self.game.player.y)
        old_turn = self.game.turn_count
        
        # Find a valid move direction
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            new_x = self.game.player.x + dx
            new_y = self.game.player.y + dy
            if (0 <= new_x < MAP_WIDTH and 0 <= new_y < MAP_HEIGHT and 
                self.game.current_map.tiles[new_y][new_x] == TILE_FLOOR):
                self.game.handle_player_action(dx, dy)
                break
        
        # Turn should advance
        self.assertGreater(self.game.turn_count, old_turn)
    
    def test_player_movement_blocked(self):
        """Test blocked player movement"""
        old_turn = self.game.turn_count
        
        # Try to move into a wall (find a wall direction)
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            new_x = self.game.player.x + dx
            new_y = self.game.player.y + dy
            if (new_x < 0 or new_x >= MAP_WIDTH or new_y < 0 or new_y >= MAP_HEIGHT or
                self.game.current_map.tiles[new_y][new_x] == TILE_WALL):
                self.game.handle_player_action(dx, dy)
                break
        
        # Turn should not advance for blocked movement
        self.assertEqual(self.game.turn_count, old_turn)
    
    def test_combat_system(self):
        """Test combat mechanics"""
        # Create a test monster
        monster = Monster(0, 0, "goblin", 1)
        player = self.game.player
        
        initial_player_hp = player.hp
        initial_monster_hp = monster.hp
        
        # Player attacks monster
        self.game.combat(player, monster)
        self.assertLess(monster.hp, initial_monster_hp)
        
        # Monster attacks player
        self.game.combat(monster, player)
        self.assertLess(player.hp, initial_player_hp)
    
    def test_combat_death(self):
        """Test combat death mechanics"""
        # Create a weak monster
        monster = Monster(0, 0, "goblin", 1)
        monster.hp = 1
        
        # Player kills monster
        self.game.combat(self.game.player, monster)
        self.assertEqual(monster.hp, 0)
        self.assertFalse(monster.is_alive())
    
    def test_player_death_triggers_game_over(self):
        """Test player death sets game over flag"""
        # Damage player to near death
        self.game.player.hp = 1
        
        # Create strong monster
        monster = Monster(0, 0, "orc", 5)
        
        # Monster kills player
        self.game.combat(monster, self.game.player)
        self.assertEqual(self.game.player.hp, 0)
        self.assertTrue(self.game.game_over)
    
    def test_item_pickup(self):
        """Test picking up items"""
        # Place item at player position
        item = Item(self.game.player.x, self.game.player.y, "potion")
        self.game.current_map.items.append(item)
        
        initial_inventory_size = len(self.game.player.inventory)
        
        # Move player (should pick up item)
        self.game.handle_player_action(0, 0)  # Move in place
        
        # Item should be picked up
        self.assertEqual(len(self.game.player.inventory), initial_inventory_size + 1)
        self.assertNotIn(item, self.game.current_map.items)
    
    def test_stairs_descent(self):
        """Test descending stairs"""
        # Move player to stairs
        stairs_x, stairs_y = self.game.current_map.stairs_down_pos
        self.game.player.x, self.game.player.y = stairs_x, stairs_y
        
        old_depth = self.game.dungeon_depth
        
        # Trigger stairs
        self.game.handle_player_action(0, 0)  # Move in place
        
        # Should descend to next level
        self.assertEqual(self.game.dungeon_depth, old_depth + 1)
        self.assertEqual(self.game.player.depth_reached, old_depth + 1)
    
    def test_turn_system(self):
        """Test turn advancement and monster AI"""
        initial_turn = self.game.turn_count
        initial_monster_positions = [(m.x, m.y) for m in self.game.current_map.monsters]
        
        # Make a valid move
        self.game.handle_player_action(1, 0)
        
        # Turn should advance
        self.assertGreater(self.game.turn_count, initial_turn)
        
        # Monsters should have had a chance to move
        # (They may or may not actually move depending on AI and obstacles)
    
    def test_message_system(self):
        """Test game message logging"""
        initial_message_count = len(self.game.message_log)
        
        self.game.add_message("Test message")
        
        self.assertEqual(len(self.game.message_log), initial_message_count + 1)
        self.assertIn("Test message", self.game.message_log)


class TestPersistence(unittest.TestCase):
    """Test the save/load system"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.persistence = Persistence(no_save=False)
        
        # Override save paths to use temp directory
        import term_dungeon_rpg
        self.old_checkpoint = term_dungeon_rpg.CHECKPOINT_FILE
        self.old_scoreboard = term_dungeon_rpg.SCOREBOARD_FILE
        term_dungeon_rpg.CHECKPOINT_FILE = Path(self.temp_dir) / "test_checkpoint.json.gz"
        term_dungeon_rpg.SCOREBOARD_FILE = Path(self.temp_dir) / "test_scoreboard.json"
    
    def tearDown(self):
        # Restore original paths
        import term_dungeon_rpg
        term_dungeon_rpg.CHECKPOINT_FILE = self.old_checkpoint
        term_dungeon_rpg.SCOREBOARD_FILE = self.old_scoreboard
        
        # Clean up temp files
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_save_load_game_state(self):
        """Test saving and loading game state"""
        # Create test game state
        test_state = {
            "player": {"x": 5, "y": 10, "hp": 25},
            "dungeon_depth": 3,
            "turn_count": 50
        }
        
        # Save state
        self.persistence.save_game(test_state)
        import term_dungeon_rpg
        self.assertTrue(term_dungeon_rpg.CHECKPOINT_FILE.exists())
        
        # Load state
        loaded_state = self.persistence.load_game()
        self.assertEqual(loaded_state["dungeon_depth"], 3)
        self.assertEqual(loaded_state["turn_count"], 50)
    
    def test_save_load_scoreboard(self):
        """Test saving and loading scoreboard"""
        test_scores = [
            {"depth": 5, "monsters": 10, "turns": 100},
            {"depth": 3, "monsters": 5, "turns": 50}
        ]
        
        # Save scoreboard
        self.persistence.save_scoreboard(test_scores)
        import term_dungeon_rpg
        self.assertTrue(term_dungeon_rpg.SCOREBOARD_FILE.exists())
        
        # Load scoreboard
        loaded_scores = self.persistence.load_scoreboard()
        self.assertEqual(len(loaded_scores), 2)
        self.assertEqual(loaded_scores[0]["depth"], 5)
    
    def test_no_save_mode(self):
        """Test no-save mode doesn't create files"""
        no_save_persistence = Persistence(no_save=True)
        
        test_state = {"test": "data"}
        no_save_persistence.save_game(test_state)
        
        # File should not be created
        import term_dungeon_rpg
        self.assertFalse(term_dungeon_rpg.CHECKPOINT_FILE.exists())


class TestIntegration(unittest.TestCase):
    """Integration tests for complete game scenarios"""
    
    def setUp(self):
        self.args = argparse.Namespace(
            seed=99999, reset=True, no_save=True, headless=True, 
            debug=False, minimal_curses=False, debug_draw=False
        )
    
    def test_complete_game_flow(self):
        """Test a complete game scenario"""
        game = Game(self.args, stdscr=None)
        
        # Verify initial state
        self.assertEqual(game.dungeon_depth, 1)
        self.assertFalse(game.game_over)
        
        # Make several moves
        for _ in range(5):
            if game.game_over:
                break
            # Try to move in a valid direction
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                new_x = game.player.x + dx
                new_y = game.player.y + dy
                if (0 <= new_x < MAP_WIDTH and 0 <= new_y < MAP_HEIGHT and 
                    game.current_map.tiles[new_y][new_x] != TILE_WALL):
                    game.handle_player_action(dx, dy)
                    break
        
        # Game should still be running (unless player died)
        if not game.game_over:
            self.assertTrue(game.game_running)
            self.assertGreater(game.turn_count, 0)
    
    def test_equipment_and_combat_integration(self):
        """Test equipment affects combat outcomes"""
        game = Game(self.args, stdscr=None)
        
        # Give player equipment
        weapon = Item(0, 0, "sword")
        armor = Item(0, 0, "shield")
        game.player.add_item(weapon)
        game.player.add_item(armor)
        
        # Equip items
        weapon.use(game.player, game)
        armor.use(game.player, game)
        
        # Verify equipment is equipped and affects stats
        self.assertIsNotNone(game.player.equipped_weapon)
        self.assertIsNotNone(game.player.equipped_armor)
        self.assertGreater(game.player.get_attack(), 4)  # Base attack + weapon
        self.assertGreater(game.player.get_defense(), 1)  # Base defense + armor
    
    def test_inventory_management(self):
        """Test complete inventory operations"""
        game = Game(self.args, stdscr=None)
        
        # Add various items
        potion1 = Item(0, 0, "potion", 2)
        potion2 = Item(0, 0, "potion", 3)
        sword = Item(0, 0, "sword")
        
        game.player.add_item(potion1)
        game.player.add_item(potion2)
        game.player.add_item(sword)
        
        # Should have 2 items (potions stacked)
        self.assertEqual(len(game.player.inventory), 2)
        
        # Find and use potion
        potion = next(item for item in game.player.inventory if item.item_id == "potion")
        self.assertEqual(potion.qty, 5)  # Should be stacked
        
        # Damage player and use potion
        game.player.hp = 20
        potion.use(game.player, game)
        self.assertEqual(game.player.hp, 30)  # Should heal to max
        self.assertEqual(potion.qty, 4)  # Should decrease quantity


if __name__ == '__main__':
    # Run all tests
    unittest.main(verbosity=2)
