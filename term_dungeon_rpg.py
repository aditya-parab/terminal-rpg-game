# term_dungeon_rpg.py
# A lightweight, tile-based roguelike terminal RPG.

import argparse
import curses
import os
import sys
import json
import gzip
import random
import datetime
import logging
import signal
from pathlib import Path
from functools import partial

# --- Configuration and Constants ---

MIN_TERM_WIDTH, MIN_TERM_HEIGHT = 80, 24
MAP_WIDTH, MAP_HEIGHT = 60, 40
MAP_VIEW_WIDTH = 60
MESSAGE_LOG_HEIGHT = 3

COLOR_BLACK, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_BLUE, COLOR_MAGENTA, COLOR_CYAN, COLOR_WHITE = range(8)

TILE_WALL, TILE_FLOOR, TILE_PLAYER, TILE_STAIRS_DOWN = '#', '.', '@', '>'
TILE_POTION, TILE_WEAPON, TILE_ARMOR = '!', '/', '['
TILE_PORTAL = 'O'
TILE_SUMMON = '*'

KEY_MOVE_N = [curses.KEY_UP, ord('w'), ord('W')]
KEY_MOVE_S = [curses.KEY_DOWN, ord('s'), ord('S')]
KEY_MOVE_E = [curses.KEY_RIGHT, ord('d'), ord('D')]
KEY_MOVE_W = [curses.KEY_LEFT, ord('a'), ord('A')]
KEY_INVENTORY = [ord('i'), ord('I')]
KEY_HELP = [ord('?'), curses.KEY_F1]
KEY_RESET_GAME = [ord('r'), ord('R')]
KEY_HIGH_SCORES = [ord('h'), ord('H')]
KEY_QUIT_ALT = [ord('q'), ord('Q')]
KEY_CONFIRM = [curses.KEY_ENTER, ord('\n'), ord('\r')]

AUTOSAVE_INTERVAL_TURNS = 20
INVENTORY_SIZE = 10
MAX_HIGH_SCORES = 5

LOG_FILE = "term_dungeon_rpg.log"
DEBUG_LOG_FILE = "term_dungeon_rpg_debug.log"

logger = logging.getLogger(__name__)
debug_logger = logging.getLogger('debug_logger')

# --- Persistence Paths ---
def get_save_dir():
    if sys.platform == "win32": path = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin": path = Path.home() / "Library" / "Application Support"
    else: path = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    save_dir = path / "term_dungeon_rpg"
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir

SAVE_DIR = get_save_dir()
CHECKPOINT_FILE = SAVE_DIR / "checkpoint.json.gz"
SCOREBOARD_FILE = SAVE_DIR / "scoreboard.json"

# --- Utility Functions ---
def setup_logging(debug_mode):
    # Main logger setup
    level = logging.DEBUG if debug_mode else logging.INFO
    logging.basicConfig(filename=LOG_FILE, filemode='w', level=level, format='%(asctime)s - %(levelname)s - %(message)s')

    # Debug logger setup
    debug_logger.setLevel(logging.DEBUG)
    debug_handler = logging.FileHandler(DEBUG_LOG_FILE, mode='w')
    debug_formatter = logging.Formatter('%(asctime)s - %(message)s')
    debug_handler.setFormatter(debug_formatter)
    debug_logger.addHandler(debug_handler)
    debug_logger.propagate = False # Prevent debug logs from going to main log

# --- Game Classes ---

class Entity:
    def __init__(self, x, y, char, color_pair, name, hp, atk, def_val):
        self.x, self.y, self.char, self.color_pair = x, y, char, color_pair
        self.name, self.hp, self.max_hp, self.atk, self.def_val = name, hp, hp, atk, def_val

    def move(self, dx, dy, game_map, all_entities=None):
        new_x, new_y = self.x + dx, self.y + dy
        
        # Check bounds and walls
        if not (0 <= new_x < game_map.width and 0 <= new_y < game_map.height and game_map.tiles[new_y][new_x] != TILE_WALL):
            debug_logger.debug(f"  -> {self.name} tried to move to ({new_x},{new_y}) but was blocked by wall/bounds.")
            return False
        
        # Check collision with other entities
        if all_entities:
            for entity in all_entities:
                if entity != self and entity.is_alive() and entity.x == new_x and entity.y == new_y:
                    debug_logger.debug(f"  -> {self.name} tried to move to ({new_x},{new_y}) but blocked by {entity.name}.")
                    return False
        
        self.x, self.y = new_x, new_y
        debug_logger.debug(f"  -> {self.name} moved to ({self.x},{self.y})")
        return True

    def take_damage(self, damage):
        self.hp -= damage
        if self.hp < 0: self.hp = 0
        debug_logger.debug(f"  -> {self.name} took {damage} damage. HP: {self.hp}/{self.max_hp}")
        return self.hp == 0

    def is_alive(self): return self.hp > 0
    def get_attack(self): return self.atk
    def get_defense(self): return self.def_val

    def to_dict(self):
        return {"x": self.x, "y": self.y, "char": self.char, "color_pair": self.color_pair, "name": self.name,
                "hp": self.hp, "max_hp": self.max_hp, "atk": self.atk, "def_val": self.def_val}

class Player(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, TILE_PLAYER, 1, "Adventurer", 30, 4, 1)
        self.inventory = []
        self.depth_reached = 1
        self.monsters_killed = 0
        self.items_collected = 0
        self.equipped_weapon = None
        self.equipped_armor = None
        # Temporary buffs: {buff_type: (amount, remaining_steps)}
        self.temp_buffs = {}

    def add_item(self, item):
        if len(self.inventory) >= INVENTORY_SIZE: 
            debug_logger.debug(f"  -> Inventory full. Cannot pick up {item.name}.")
            return False
        for inv_item in self.inventory:
            if inv_item.item_id == item.item_id and inv_item.stackable:
                inv_item.qty += item.qty; self.items_collected += item.qty; 
                debug_logger.debug(f"  -> Picked up {item.name} (stacked). Total: {inv_item.qty}")
                return True
        self.inventory.append(item); self.items_collected += item.qty; 
        debug_logger.debug(f"  -> Picked up {item.name} (new slot).")
        return True

    def remove_item(self, item, qty=1):
        if item.stackable:
            item.qty -= qty
            if item.qty <= 0 and item in self.inventory: self.inventory.remove(item)
            debug_logger.debug(f"  -> Removed {qty} of {item.name}. Remaining: {item.qty}")
        elif item in self.inventory: 
            self.inventory.remove(item)
            debug_logger.debug(f"  -> Removed {item.name}.")

    def get_attack(self): 
        base_atk = self.atk + (self.equipped_weapon.power if self.equipped_weapon else 0)
        return base_atk + self.temp_buffs.get('attack', (0, 0))[0]
    
    def get_defense(self): 
        base_def = self.def_val + (self.equipped_armor.power if self.equipped_armor else 0)
        return base_def + self.temp_buffs.get('defense', (0, 0))[0]
    
    def get_max_hp(self):
        return self.max_hp + self.temp_buffs.get('hp', (0, 0))[0]
    
    def update_buffs(self):
        """Decrease buff durations and remove expired buffs"""
        expired = []
        for buff_type, (amount, steps) in self.temp_buffs.items():
            steps -= 1
            if steps <= 0:
                expired.append(buff_type)
            else:
                self.temp_buffs[buff_type] = (amount, steps)
        
        for buff_type in expired:
            del self.temp_buffs[buff_type]
        
        return len(expired) > 0  # Return True if any buffs expired

    def to_dict(self):
        data = super().to_dict()
        data.update({"inventory": [item.to_dict() for item in self.inventory], "depth_reached": self.depth_reached,
                     "monsters_killed": self.monsters_killed, "items_collected": self.items_collected,
                     "equipped_weapon": self.equipped_weapon.to_dict() if self.equipped_weapon else None,
                     "equipped_armor": self.equipped_armor.to_dict() if self.equipped_armor else None,
                     "temp_buffs": self.temp_buffs})
        return data

    @classmethod
    def from_dict(cls, data):
        player = cls(data["x"], data["y"]); player.__dict__.update(data)
        player.inventory = [Item.from_dict(item_data) for item_data in data["inventory"]]
        if data.get("equipped_weapon"): player.equipped_weapon = Item.from_dict(data["equipped_weapon"])
        if data.get("equipped_armor"): player.equipped_armor = Item.from_dict(data["equipped_armor"])
        player.temp_buffs = data.get("temp_buffs", {})
        return player

class Summon(Entity):
    def __init__(self, x, y, level, player_level):
        import random
        names = ["Sam the Warrior", "Jane the Valkyrie", "Bob the Guardian", "Alice the Protector", 
                "Tom the Knight", "Sarah the Defender", "Mike the Paladin", "Emma the Champion",
                "Jack the Sentinel", "Lisa the Shield-Bearer", "Dave the Crusader", "Anna the Warden"]
        
        name = random.choice(names)
        # Stats scale with summon level
        hp = 15 + level * 8
        attack = 3 + level * 2
        defense = 1 + level
        
        # Different colors for visual variety: green, cyan, yellow, blue, magenta, red
        colors = [2, 6, 3, 4, 5, 1]  # Green, Cyan, Yellow, Blue, Magenta, Red
        # Use a combination of level and a hash of the name for unique colors
        color_index = (level + hash(name)) % len(colors)
        color = colors[color_index]
        
        super().__init__(x, y, 'S', color, f"{name} (Lv.{level})", hp, attack, defense)
        self.level = level
        self.player_level = player_level

    def take_turn(self, player, game_map, monsters, rng, all_summons=None):
        # Calculate distance to player
        player_dist = abs(self.x - player.x) + abs(self.y - player.y)
        
        # Find closest enemy within sight range (8 tiles)
        closest_enemy = None
        min_dist = float('inf')
        for monster in monsters:
            if monster.is_alive():
                dist = abs(self.x - monster.x) + abs(self.y - monster.y)
                if dist <= 8 and dist < min_dist:  # Within sight range
                    min_dist = dist
                    closest_enemy = monster
        
        # AGGRESSIVE BEHAVIOR: If enemy is adjacent, attack immediately
        if closest_enemy:
            # Check if truly adjacent (including diagonals)
            dx = abs(self.x - closest_enemy.x)
            dy = abs(self.y - closest_enemy.y)
            if dx <= 1 and dy <= 1 and (dx + dy) > 0:  # Adjacent but not same tile
                debug_logger.debug(f"  -> {self.name} found adjacent enemy {closest_enemy.name}")
                return closest_enemy  # Signal combat
        
        # Create entities list for collision detection
        all_entities = [player] + monsters + ([s for s in all_summons if s != self] if all_summons else [])
        
        # PRIORITY 1: If player is far away (>6 tiles), follow player
        if player_dist > 6:
            self._smart_move_toward(player.x, player.y, game_map, all_entities)
            return None
        
        # PRIORITY 2: If enemy in sight, aggressively pursue and attack
        if closest_enemy and min_dist <= 8:
            self._smart_move_toward(closest_enemy.x, closest_enemy.y, game_map, all_entities)
            return None
        
        # PRIORITY 3: Stay close to player (within 3 tiles)
        if player_dist > 3:
            self._smart_move_toward(player.x, player.y, game_map, all_entities)
        
        return None
    
    def _smart_move_toward(self, target_x, target_y, game_map, all_entities=None):
        """Smart movement that tries multiple directions to navigate around obstacles"""
        dx = 1 if target_x > self.x else -1 if target_x < self.x else 0
        dy = 1 if target_y > self.y else -1 if target_y < self.y else 0
        
        # Try direct movement first
        if self.move(dx, dy, game_map, all_entities):
            return True
        
        # If blocked, try all 8 directions in order of preference
        moves = []
        if dx != 0 and dy != 0:  # Diagonal movement blocked
            moves = [(dx, 0), (0, dy), (-dx, dy), (dx, -dy), (-dx, 0), (0, -dy), (-dx, -dy)]
        elif dx != 0:  # Horizontal movement blocked
            moves = [(0, 1), (0, -1), (dx, 1), (dx, -1), (-dx, 0), (-dx, 1), (-dx, -1)]
        elif dy != 0:  # Vertical movement blocked
            moves = [(1, 0), (-1, 0), (1, dy), (-1, dy), (0, -dy), (1, -dy), (-1, -dy)]
        else:  # No preferred direction, try all
            moves = [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]
        
        # Try alternative moves
        for alt_dx, alt_dy in moves:
            if self.move(alt_dx, alt_dy, game_map, all_entities):
                return True
        
        return False

    def to_dict(self):
        data = super().to_dict()
        data.update({"level": self.level, "player_level": self.player_level})
        return data

    @classmethod
    def from_dict(cls, data):
        summon = cls(data["x"], data["y"], data["level"], data["player_level"])
        summon.__dict__.update(data)
        return summon

class Monster(Entity):
    def __init__(self, x, y, monster_id, depth):
        # Base templates: char, color, name, hp, atk, def_val, sight
        base_templates = {
            "goblin": ('g', 2, "Goblin", 5, 2, 0, 5), 
            "orc": ('o', 3, "Orc", 10, 4, 1, 7), 
            "skeleton": ('k', 7, "Skeleton", 8, 3, 1, 6), 
            "spider": ('x', 1, "Spider", 4, 3, 0, 4)
        }
        
        # Get base template
        char, base_color, base_name, hp, atk, def_val, sight = base_templates.get(monster_id, base_templates["goblin"])
        
        # Biome-specific variations
        biome_index = (depth - 1) // 3
        if biome_index == 1:  # Ice Caves (4-6) - cyan/blue tints
            color_map = {"goblin": 6, "orc": 6, "skeleton": 6, "spider": 4}
            name_prefix = {"goblin": "Frost", "orc": "Ice", "skeleton": "Frozen", "spider": "Crystal"}
        elif biome_index == 2:  # Jungle Ruins (7-9) - green tints
            color_map = {"goblin": 2, "orc": 2, "skeleton": 2, "spider": 2}
            name_prefix = {"goblin": "Jungle", "orc": "Vine", "skeleton": "Moss", "spider": "Leaf"}
        elif biome_index == 3:  # Fire Depths (10-12) - red/yellow tints
            color_map = {"goblin": 1, "orc": 3, "skeleton": 1, "spider": 3}
            name_prefix = {"goblin": "Fire", "orc": "Lava", "skeleton": "Burning", "spider": "Ember"}
        elif biome_index == 4:  # Shadow Realm (13-15) - magenta/dark
            color_map = {"goblin": 5, "orc": 5, "skeleton": 5, "spider": 5}
            name_prefix = {"goblin": "Shadow", "orc": "Dark", "skeleton": "Void", "spider": "Phantom"}
        elif biome_index >= 5:  # Crystal Sanctum (16+) - bright cycling colors
            color_map = {"goblin": 6, "orc": 3, "skeleton": 5, "spider": 2}
            name_prefix = {"goblin": "Crystal", "orc": "Prism", "skeleton": "Radiant", "spider": "Gem"}
        else:  # Stone Caverns (1-3) - default colors
            color_map = {"goblin": 2, "orc": 3, "skeleton": 7, "spider": 1}
            name_prefix = {"goblin": "", "orc": "", "skeleton": "", "spider": ""}
        
        # Apply biome modifications
        color = color_map.get(monster_id, base_color)
        prefix = name_prefix.get(monster_id, "")
        name = f"{prefix} {base_name}" if prefix else base_name
        
        # Level scaling: monsters get stronger with depth
        self.level = max(1, depth + random.randint(-1, 2))  # Level varies around depth
        level_bonus = self.level - 1
        
        super().__init__(x, y, char, color, f"{name} (Lv.{self.level})", 
                        hp + level_bonus * 2, atk + level_bonus, def_val + level_bonus // 2)
        self.monster_id = monster_id

    def take_turn(self, player, game_map, rng, summons=None):
        debug_logger.debug(f"  -> {self.name} ({self.monster_id}) taking turn.")
        
        if summons is None:
            summons = []
        
        # Get all potential targets (player + living summons)
        potential_targets = [player] + [s for s in summons if s.is_alive()]
        
        # Find the best target using smart AI
        target = self._select_target(potential_targets, rng)
        
        if target:
            target_distance = abs(self.x - target.x) + abs(self.y - target.y)
            
            # Different behavior based on monster type and situation
            if target_distance <= 8:  # Within sight range
                # Check if adjacent to target - attack!
                if target_distance == 1:
                    debug_logger.debug(f"    -> {self.name} is adjacent to {target.name}, ready to attack!")
                    return target  # Signal combat with this target
                
                # Move toward target using smart pathfinding
                if self._smart_move_toward_target(target, game_map, [player] + [m for m in game_map.monsters if m != self] + summons, rng):
                    debug_logger.debug(f"    -> {self.name} moved toward {target.name}")
                else:
                    debug_logger.debug(f"    -> {self.name} couldn't move toward {target.name}")
            else:
                # Target too far, wander but stay alert
                self._wander_intelligently(game_map, [player] + [m for m in game_map.monsters if m != self] + summons, rng)
        else:
            # No targets in range, wander
            self._wander_intelligently(game_map, [player] + [m for m in game_map.monsters if m != self] + summons, rng)
        
        return None  # No combat this turn
    
    def _select_target(self, potential_targets, rng):
        """Smart target selection based on monster type and tactical considerations"""
        if not potential_targets:
            return None
        
        # Calculate threat scores for each target
        target_scores = []
        
        for target in potential_targets:
            distance = abs(self.x - target.x) + abs(self.y - target.y)
            
            # Base score factors
            proximity_score = max(0, 10 - distance)  # Closer = higher score
            health_score = 10 - (target.hp / target.max_hp * 10)  # Lower HP = higher score
            
            # Monster-type specific targeting
            if self.monster_id == "spider":
                # Spiders prefer weak/isolated targets
                isolation_bonus = 5 if distance <= 3 else 0
                weakness_bonus = health_score * 1.5
                total_score = proximity_score + weakness_bonus + isolation_bonus
            elif self.monster_id == "orc":
                # Orcs prefer direct confrontation with strongest target
                strength_bonus = (target.get_attack() / 10) * 3
                total_score = proximity_score + strength_bonus
            elif self.monster_id == "skeleton":
                # Skeletons prefer player over summons (undead hatred)
                player_bonus = 8 if hasattr(target, 'inventory') else 0  # Player has inventory
                total_score = proximity_score + health_score + player_bonus
            else:  # goblin or default
                # Goblins are opportunistic - prefer easy targets
                total_score = proximity_score + health_score * 1.2
            
            # Add some randomness for unpredictability
            total_score += rng.uniform(-2, 2)
            
            target_scores.append((target, total_score, distance))
        
        # Filter to only targets within reasonable range (8 tiles)
        valid_targets = [(t, s, d) for t, s, d in target_scores if d <= 8]
        
        if not valid_targets:
            return None
        
        # Select target with highest score
        best_target = max(valid_targets, key=lambda x: x[1])
        debug_logger.debug(f"    -> {self.name} selected target: {best_target[0].name} (score: {best_target[1]:.1f})")
        
        return best_target[0]
    
    def _smart_move_toward_target(self, target, game_map, all_entities, rng):
        """Intelligent movement toward target with obstacle avoidance"""
        dx = 1 if target.x > self.x else -1 if target.x < self.x else 0
        dy = 1 if target.y > self.y else -1 if target.y < self.y else 0
        
        # Try direct movement first
        if self.move(dx, dy, game_map, all_entities):
            return True
        
        # If blocked, try smart alternatives based on monster type
        if self.monster_id == "spider":
            # Spiders try to flank around obstacles
            moves = [(dy, dx), (-dy, -dx), (dx, 0), (0, dy), (-dx, 0), (0, -dy)]
        elif self.monster_id == "orc":
            # Orcs try to break through obstacles more directly
            moves = [(dx, 0), (0, dy), (dx, dy), (-dx, dy), (dx, -dy)]
        else:
            # Default pathfinding - try perpendicular moves first
            moves = [(dx, 0), (0, dy), (-dx, dy), (dx, -dy), (-dx, 0), (0, -dy)]
        
        # Try alternative moves
        for alt_dx, alt_dy in moves:
            if self.move(alt_dx, alt_dy, game_map, all_entities):
                return True
        
        return False
    
    def _wander_intelligently(self, game_map, all_entities, rng):
        """Intelligent wandering that avoids getting stuck"""
        # Try to move toward center of map or away from walls
        center_x, center_y = game_map.width // 2, game_map.height // 2
        
        # Bias toward center with some randomness
        if rng.random() < 0.3:  # 30% chance to move toward center
            dx = 1 if center_x > self.x else -1 if center_x < self.x else 0
            dy = 1 if center_y > self.y else -1 if center_y < self.y else 0
        else:
            # Random movement
            dx, dy = rng.choice([(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)])
        
        if not self.move(dx, dy, game_map, all_entities):
            # If can't move in chosen direction, try any valid direction
            for alt_dx, alt_dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                if self.move(alt_dx, alt_dy, game_map, all_entities):
                    break

    def to_dict(self):
        data = super().to_dict(); data.update({"monster_id": self.monster_id, "level": self.level}); return data

    @classmethod
    def from_dict(cls, data):
        monster = cls(data["x"], data["y"], data["monster_id"], 1); monster.__dict__.update(data); return monster

class Item:
    def __init__(self, x, y, item_id, qty=1, level=1):
        self.x, self.y, self.item_id, self.qty, self.level = x, y, item_id, qty, level
        
        if item_id == "health_potion":
            self.name = f"Health Potion Lv.{level}"
            self.char, self.color_pair, self.stackable = TILE_POTION, 5, True
            self.power = 10 + (level - 1) * 5  # Lv1=10hp, Lv2=15hp, etc
            self.effect = self._use_health_potion
        elif item_id == "defense_potion":
            self.name = f"Defense Potion Lv.{level}"
            self.char, self.color_pair, self.stackable = TILE_POTION, 3, True
            self.power = 5 + (level - 1) * 2  # Lv1=+5def, Lv2=+7def, etc
            self.effect = self._use_defense_potion
        elif item_id == "hp_boost_potion":
            self.name = f"Vitality Potion Lv.{level}"
            self.char, self.color_pair, self.stackable = TILE_POTION, 2, True
            self.power = 15 + (level - 1) * 10  # Lv1=+15maxhp, Lv2=+25maxhp, etc
            self.effect = self._use_hp_boost_potion
        elif item_id == "summon":
            self.name = f"Summon Scroll Lv.{level}"
            self.char, self.color_pair, self.stackable = TILE_SUMMON, 6, True
            self.power = level
            self.effect = self._use_summon
        elif item_id == "sword":
            self.name = "Iron Sword"
            self.char, self.color_pair, self.stackable = TILE_WEAPON, 6, False
            self.power = 2
            self.effect = self._equip_weapon
        elif item_id == "shield":
            self.name = "Wooden Shield"
            self.char, self.color_pair, self.stackable = TILE_ARMOR, 4, False
            self.power = 1
            self.effect = self._equip_armor
        else:
            self.name, self.char, self.color_pair, self.stackable, self.power, self.effect = "Unknown", '?', 7, False, 0, None

    def _use_health_potion(self, player, game):
        if player.hp >= player.max_hp: 
            game.add_message("You are already at full health."); return False
        player.hp = min(player.max_hp, player.hp + self.power)
        game.add_message(f"You used a {self.name} and healed {self.power} HP!")
        player.remove_item(self); return True

    def _use_defense_potion(self, player, game):
        duration = 15
        player.temp_buffs['defense'] = (self.power, duration)
        game.add_message(f"You used a {self.name}! Defense +{self.power} for {duration} steps.")
        player.remove_item(self); return True

    def _use_hp_boost_potion(self, player, game):
        duration = 15
        player.temp_buffs['hp'] = (self.power, duration)
        # Also heal the player by the boost amount
        player.hp = min(player.get_max_hp(), player.hp + self.power)
        game.add_message(f"You used a {self.name}! Max HP +{self.power} for {duration} steps.")
        player.remove_item(self); return True

    def _use_summon(self, player, game):
        # Find empty adjacent spot
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
            new_x, new_y = player.x + dx, player.y + dy
            if (game.current_map.get_tile(new_x, new_y) == TILE_FLOOR and
                not any(m.x == new_x and m.y == new_y for m in game.current_map.monsters) and
                not any(s.x == new_x and s.y == new_y for s in game.summons)):
                
                summon = Summon(new_x, new_y, self.level, game.dungeon_depth)
                game.summons.append(summon)
                game.add_message(f"You summoned {summon.name}!")
                player.remove_item(self)
                return True
        
        game.add_message("No space to summon!")
        return False

    def _equip_weapon(self, player, game):
        if player.equipped_weapon: player.inventory.append(player.equipped_weapon)
        player.equipped_weapon = self; player.remove_item(self)
        game.add_message(f"You equipped the {self.name}."); return True

    def _equip_armor(self, player, game):
        if player.equipped_armor: player.inventory.append(player.equipped_armor)
        player.equipped_armor = self; player.remove_item(self)
        game.add_message(f"You equipped the {self.name}."); return True
    
    def use(self, player, game): 
        return self.effect(player, game) if self.effect else False
    
    def to_dict(self): 
        return {"x": self.x, "y": self.y, "item_id": self.item_id, "qty": self.qty, "level": self.level}
    
    @classmethod
    def from_dict(cls, data): 
        return cls(data["x"], data["y"], data["item_id"], data["qty"], data.get("level", 1))

class GameMap:
    def __init__(self, width, height, seed):
        self.width, self.height, self.seed = width, height, seed
        self.tiles = [[TILE_WALL for _ in range(width)] for _ in range(height)]
        self.monsters, self.items = [], []
        self.stairs_down_pos, self.player_start_pos = None, None
        self.portals = []  # List of (x1, y1, x2, y2) portal pairs
        self.rng = random.Random(seed)

    def generate_map(self, depth, retry_count=0):
        """Generate dungeons using Binary Space Partitioning (BSP) - industry standard"""
        debug_logger.debug(f"Generating BSP dungeon for depth {depth}")
        
        # Reset tiles to all walls
        self.tiles = [[TILE_WALL for _ in range(self.width)] for _ in range(self.height)]
        
        # Create BSP tree by recursively subdividing the space
        root_node = {'x': 2, 'y': 2, 'w': self.width - 4, 'h': self.height - 4, 'room': None, 'children': []}
        self._split_node(root_node, 0, 4)  # Split 4 levels deep
        
        # Create rooms in leaf nodes
        rooms = []
        self._create_rooms_in_leaves(root_node, rooms)
        
        # Connect rooms through BSP tree structure
        self._connect_bsp_rooms(root_node)
        
        if len(rooms) < 2:
            debug_logger.warning("BSP failed to generate enough rooms, using fallback")
            self._create_fallback_map(depth)
            return
        
        # Place player and stairs
        self._place_player_and_stairs(rooms)
        
        # Generate monsters and items
        self._generate_monsters(rooms, depth)
        self._generate_items(rooms, depth)
        
        # Generate portals between distant rooms
        self._generate_portals(rooms)
    
    def _split_node(self, node, depth, max_depth):
        """Recursively split BSP node into two children"""
        if depth >= max_depth or node['w'] < 8 or node['h'] < 6:
            return  # Stop splitting - this becomes a leaf node
        
        # Decide split direction - prefer splitting along longer dimension
        split_horizontal = node['w'] < node['h']
        if node['w'] > node['h'] * 1.25:
            split_horizontal = False
        elif node['h'] > node['w'] * 1.25:
            split_horizontal = True
        else:
            split_horizontal = self.rng.random() < 0.5
        
        if split_horizontal:
            # Split horizontally
            split_pos = self.rng.randint(node['h'] // 3, 2 * node['h'] // 3)
            child1 = {'x': node['x'], 'y': node['y'], 'w': node['w'], 'h': split_pos, 'room': None, 'children': []}
            child2 = {'x': node['x'], 'y': node['y'] + split_pos, 'w': node['w'], 'h': node['h'] - split_pos, 'room': None, 'children': []}
        else:
            # Split vertically
            split_pos = self.rng.randint(node['w'] // 3, 2 * node['w'] // 3)
            child1 = {'x': node['x'], 'y': node['y'], 'w': split_pos, 'h': node['h'], 'room': None, 'children': []}
            child2 = {'x': node['x'] + split_pos, 'y': node['y'], 'w': node['w'] - split_pos, 'h': node['h'], 'room': None, 'children': []}
        
        node['children'] = [child1, child2]
        
        # Recursively split children
        self._split_node(child1, depth + 1, max_depth)
        self._split_node(child2, depth + 1, max_depth)
    
    def _create_rooms_in_leaves(self, node, rooms):
        """Create rooms in leaf nodes of BSP tree"""
        if not node['children']:  # Leaf node
            # Create room with some padding from node boundaries
            padding = 1
            room_w = self.rng.randint(node['w'] // 2, node['w'] - padding * 2)
            room_h = self.rng.randint(node['h'] // 2, node['h'] - padding * 2)
            room_x = node['x'] + self.rng.randint(padding, node['w'] - room_w - padding)
            room_y = node['y'] + self.rng.randint(padding, node['h'] - room_h - padding)
            
            room = {'x1': room_x, 'y1': room_y, 'x2': room_x + room_w, 'y2': room_y + room_h}
            node['room'] = room
            rooms.append(room)
            
            # Carve out the room
            for y in range(room['y1'], room['y2']):
                for x in range(room['x1'], room['x2']):
                    if 0 <= x < self.width and 0 <= y < self.height:
                        self.tiles[y][x] = TILE_FLOOR
        else:
            # Recurse into children
            for child in node['children']:
                self._create_rooms_in_leaves(child, rooms)
    
    def _connect_bsp_rooms(self, node):
        """Connect rooms through BSP tree structure"""
        if not node['children']:
            return  # Leaf node, nothing to connect
        
        # Recursively connect children first
        for child in node['children']:
            self._connect_bsp_rooms(child)
        
        # Connect the two child subtrees
        if len(node['children']) == 2:
            room1 = self._get_random_room_from_subtree(node['children'][0])
            room2 = self._get_random_room_from_subtree(node['children'][1])
            
            if room1 and room2:
                self._create_corridor_between_rooms(room1, room2)
    
    def _get_random_room_from_subtree(self, node):
        """Get a random room from BSP subtree"""
        if node['room']:
            return node['room']
        
        if node['children']:
            # Randomly pick a child and recurse
            child = self.rng.choice(node['children'])
            return self._get_random_room_from_subtree(child)
        
        return None
    
    def _create_corridor_between_rooms(self, room1, room2):
        """Create L-shaped corridor between two rooms"""
        # Get random points in each room
        x1 = self.rng.randint(room1['x1'], room1['x2'] - 1)
        y1 = self.rng.randint(room1['y1'], room1['y2'] - 1)
        x2 = self.rng.randint(room2['x1'], room2['x2'] - 1)
        y2 = self.rng.randint(room2['y1'], room2['y2'] - 1)
        
        # Create L-shaped path
        if self.rng.random() < 0.5:
            # Horizontal then vertical
            for x in range(min(x1, x2), max(x1, x2) + 1):
                if 0 <= x < self.width and 0 <= y1 < self.height:
                    self.tiles[y1][x] = TILE_FLOOR
            for y in range(min(y1, y2), max(y1, y2) + 1):
                if 0 <= x2 < self.width and 0 <= y < self.height:
                    self.tiles[y][x2] = TILE_FLOOR
        else:
            # Vertical then horizontal
            for y in range(min(y1, y2), max(y1, y2) + 1):
                if 0 <= x1 < self.width and 0 <= y < self.height:
                    self.tiles[y][x1] = TILE_FLOOR
            for x in range(min(x1, x2), max(x1, x2) + 1):
                if 0 <= x < self.width and 0 <= y2 < self.height:
                    self.tiles[y2][x] = TILE_FLOOR

    def _connect_room_to_corridor(self, room, mid_x, mid_y):
        """Connect a room to the nearest main corridor with guaranteed path"""
        room_center_x = (room['x1'] + room['x2']) // 2
        room_center_y = (room['y1'] + room['y2']) // 2
        
        # Find the nearest point on main corridors
        # Distance to horizontal corridor at mid_y
        dist_to_h_corridor = abs(room_center_y - mid_y)
        # Distance to vertical corridor at mid_x  
        dist_to_v_corridor = abs(room_center_x - mid_x)
        
        if dist_to_h_corridor <= dist_to_v_corridor:
            # Connect to horizontal corridor
            # Create vertical path from room to horizontal corridor
            start_y = min(room_center_y, mid_y)
            end_y = max(room_center_y, mid_y)
            for y in range(start_y, end_y + 1):
                if 0 <= room_center_x < self.width and 0 <= y < self.height:
                    self.tiles[y][room_center_x] = TILE_FLOOR
        else:
            # Connect to vertical corridor
            # Create horizontal path from room to vertical corridor
            start_x = min(room_center_x, mid_x)
            end_x = max(room_center_x, mid_x)
            for x in range(start_x, end_x + 1):
                if 0 <= x < self.width and 0 <= room_center_y < self.height:
                    self.tiles[room_center_y][x] = TILE_FLOOR

    def _can_reach_stairs(self, tiles):
        """Simple flood fill to check if stairs are reachable from player start"""
        if not self.player_start_pos or not self.stairs_down_pos:
            return True
            
        visited = set()
        queue = [self.player_start_pos]
        
        while queue:
            x, y = queue.pop(0)
            if (x, y) == self.stairs_down_pos:
                return True
            if (x, y) in visited:
                continue
            visited.add((x, y))
            
            # Check adjacent tiles
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if (0 <= nx < self.width and 0 <= ny < self.height and
                    tiles[ny][nx] in [TILE_FLOOR, TILE_PORTAL] and (nx, ny) not in visited):
                    queue.append((nx, ny))
        
        return False

    def _create_fallback_map(self, depth):
        """Create a simple guaranteed-connected map as fallback"""
        # Create a simple cross-shaped map that's always connected
        mid_x, mid_y = self.width // 2, self.height // 2
        
        # Horizontal corridor
        for x in range(5, self.width - 5):
            self.tiles[mid_y][x] = TILE_FLOOR
        
        # Vertical corridor  
        for y in range(5, self.height - 5):
            self.tiles[y][mid_x] = TILE_FLOOR
            
        # Add some rooms
        rooms = [
            {'x1': 5, 'y1': 5, 'x2': 15, 'y2': 12},
            {'x1': self.width - 15, 'y1': self.height - 12, 'x2': self.width - 5, 'y2': self.height - 5}
        ]
        
        for room in rooms:
            for y in range(room['y1'], room['y2']):
                for x in range(room['x1'], room['x2']):
                    self.tiles[y][x] = TILE_FLOOR
        
        self.player_start_pos = (7, 7)
        self.stairs_down_pos = (self.width - 7, self.height - 7)
        # Don't set TILE_STAIRS_DOWN in tiles array - let rendering handle it
    def _create_l_corridor(self, room1, room2):
        """Create L-shaped corridor between two rooms"""
        # Get center points of each room for better connections
        x1 = (room1['x1'] + room1['x2']) // 2
        y1 = (room1['y1'] + room1['y2']) // 2
        x2 = (room2['x1'] + room2['x2']) // 2
        y2 = (room2['y1'] + room2['y2']) // 2
        
        # Create L-shaped path (horizontal then vertical, or vice versa)
        if self.rng.random() < 0.5:
            # Horizontal first, then vertical
            for x in range(min(x1, x2), max(x1, x2) + 1):
                if 0 <= x < self.width and 0 <= y1 < self.height:
                    self.tiles[y1][x] = TILE_FLOOR
            for y in range(min(y1, y2), max(y1, y2) + 1):
                if 0 <= x2 < self.width and 0 <= y < self.height:
                    self.tiles[y][x2] = TILE_FLOOR
        else:
            # Vertical first, then horizontal
            for y in range(min(y1, y2), max(y1, y2) + 1):
                if 0 <= x1 < self.width and 0 <= y < self.height:
                    self.tiles[y][x1] = TILE_FLOOR
            for x in range(min(x1, x2), max(x1, x2) + 1):
                if 0 <= x < self.width and 0 <= y2 < self.height:
                    self.tiles[y2][x] = TILE_FLOOR

    def _place_player_and_stairs(self, rooms):
        """Place player and stairs with proper validation"""
        # Place player in first room
        for _ in range(100):  # Try many times
            px = self.rng.randint(rooms[0]['x1'], rooms[0]['x2'] - 1)
            py = self.rng.randint(rooms[0]['y1'], rooms[0]['y2'] - 1)
            if (self.tiles[py][px] == TILE_FLOOR and 
                any(self.tiles[py + dy][px + dx] == TILE_FLOOR 
                    for dx, dy in [(0,1), (1,0), (0,-1), (-1,0)] 
                    if 0 <= px + dx < self.width and 0 <= py + dy < self.height)):
                self.player_start_pos = (px, py)
                break
        
        # Place stairs in last room
        for _ in range(100):
            sx = self.rng.randint(rooms[-1]['x1'], rooms[-1]['x2'] - 1)
            sy = self.rng.randint(rooms[-1]['y1'], rooms[-1]['y2'] - 1)
            if self.tiles[sy][sx] == TILE_FLOOR:
                self.stairs_down_pos = (sx, sy)
                # Don't set TILE_STAIRS_DOWN in tiles array - let rendering handle it
                break

    def _generate_monsters(self, rooms, depth):
        """Generate monsters in rooms"""
        self.monsters = []
        monster_count = self.rng.randint(depth + 2, depth * 2 + 5)  # More monsters
        
        for _ in range(monster_count):
            room = self.rng.choice(rooms)
            for _ in range(20):  # Try to place monster
                mx = self.rng.randint(room['x1'], room['x2'] - 1)
                my = self.rng.randint(room['y1'], room['y2'] - 1)
                
                if (self.tiles[my][mx] == TILE_FLOOR and 
                    (mx, my) != self.player_start_pos and 
                    (mx, my) != self.stairs_down_pos and
                    not any(m.x == mx and m.y == my for m in self.monsters)):
                    
                    # Biome-specific monster selection
                    biome_index = (depth - 1) // 3
                    if biome_index == 0:  # Stone Caverns (1-3)
                        monster_type = self.rng.choice(["goblin", "spider", "skeleton"])
                    elif biome_index == 1:  # Ice Caves (4-6)
                        monster_type = self.rng.choice(["skeleton", "spider", "orc"])
                    elif biome_index == 2:  # Jungle Ruins (7-9)
                        monster_type = self.rng.choice(["spider", "orc", "goblin"])
                    elif biome_index == 3:  # Fire Depths (10-12)
                        monster_type = self.rng.choice(["orc", "skeleton", "goblin"])
                    elif biome_index == 4:  # Shadow Realm (13-15)
                        monster_type = self.rng.choice(["skeleton", "spider", "orc"])
                    else:  # Crystal Sanctum (16+)
                        monster_type = self.rng.choice(["orc", "skeleton", "spider", "goblin"])
                    
                    self.monsters.append(Monster(mx, my, monster_type, depth))
                    break

    def _generate_items(self, rooms, depth):
        """Generate items in rooms"""
        self.items = []
        item_count = self.rng.randint(2, 4) + depth // 3
        
        for _ in range(item_count):
            room = self.rng.choice(rooms)
            for _ in range(20):  # Try to place item
                ix = self.rng.randint(room['x1'], room['x2'] - 1)
                iy = self.rng.randint(room['y1'], room['y2'] - 1)
                
                if (self.tiles[iy][ix] == TILE_FLOOR and 
                    (ix, iy) != self.player_start_pos and 
                    (ix, iy) != self.stairs_down_pos and
                    not any(m.x == ix and m.y == iy for m in self.monsters) and
                    not any(i.x == ix and i.y == iy for i in self.items)):
                    
                    item_level = max(1, depth + self.rng.randint(-1, 1))
                    item_type = self.rng.choice(["health_potion", "defense_potion", "hp_boost_potion", "sword", "shield"])
                    self.items.append(Item(ix, iy, item_type, 1, item_level))
                    break
        
        # Add summon scroll
        if depth <= 10:
            summon_chance = 0.8
        else:
            summon_chance = max(0.1, 0.5 - (depth - 10) * 0.05)
            
        if self.rng.random() < summon_chance:
            room = self.rng.choice(rooms)
            for _ in range(20):
                sx = self.rng.randint(room['x1'], room['x2'] - 1)
                sy = self.rng.randint(room['y1'], room['y2'] - 1)
                
                if (self.tiles[sy][sx] == TILE_FLOOR and 
                    not any(m.x == sx and m.y == sy for m in self.monsters) and
                    not any(i.x == sx and i.y == sy for i in self.items) and
                    (sx, sy) != self.stairs_down_pos and (sx, sy) != self.player_start_pos):
                    
                    max_summon_level = min(5, max(1, depth // 2 + 1))
                    summon_level = self.rng.randint(1, max_summon_level)
                    if depth > 10:
                        summon_level = max(summon_level, self.rng.randint(max_summon_level//2, max_summon_level))
                    self.items.append(Item(sx, sy, "summon", 1, summon_level))
                    break

    def _generate_portals(self, rooms):
        """Generate teleport portals between distant rooms"""
        if len(rooms) < 3:
            return  # Need at least 3 rooms for interesting portal placement
        
        # Create 1-2 portal pairs
        for _ in range(self.rng.randint(1, 2)):
            # Pick two rooms that are far apart
            room1, room2 = self.rng.sample(rooms, 2)
            
            # Try to place portals in the rooms
            for _ in range(20):
                x1 = self.rng.randint(room1['x1'], room1['x2'] - 1)
                y1 = self.rng.randint(room1['y1'], room1['y2'] - 1)
                x2 = self.rng.randint(room2['x1'], room2['x2'] - 1)
                y2 = self.rng.randint(room2['y1'], room2['y2'] - 1)
                
                # Make sure portals don't overlap with other entities
                if ((x1, y1) != self.player_start_pos and (x1, y1) != self.stairs_down_pos and
                    (x2, y2) != self.player_start_pos and (x2, y2) != self.stairs_down_pos and
                    not any(m.x == x1 and m.y == y1 for m in self.monsters) and
                    not any(m.x == x2 and m.y == y2 for m in self.monsters) and
                    not any(i.x == x1 and i.y == y1 for i in self.items) and
                    not any(i.x == x2 and i.y == y2 for i in self.items)):
                    
                    # Place the portal pair
                    self.tiles[y1][x1] = TILE_PORTAL
                    self.tiles[y2][x2] = TILE_PORTAL
                    self.portals.append((x1, y1, x2, y2))
                    break

    def get_tile(self, x, y): return self.tiles[y][x] if 0 <= x < self.width and 0 <= y < self.height else TILE_WALL
    def to_dict(self): return {"seed": self.seed, "monsters": [m.to_dict() for m in self.monsters], "items": [i.to_dict() for i in self.items], "portals": self.portals}
    @classmethod
    def from_dict(cls, data):
        game_map = cls(MAP_WIDTH, MAP_HEIGHT, data["seed"])
        game_map.generate_map(1)
        game_map.monsters = [Monster.from_dict(m_data) for m_data in data["monsters"]]
        game_map.items = [Item.from_dict(i_data) for i_data in data["items"]]
        game_map.portals = data.get("portals", [])
        # Restore portal tiles
        for x1, y1, x2, y2 in game_map.portals:
            game_map.tiles[y1][x1] = TILE_PORTAL
            game_map.tiles[y2][x2] = TILE_PORTAL
        return game_map

class Persistence:
    def __init__(self, no_save=False): self.no_save = no_save
    def save_game(self, game_state):
        if self.no_save: return
        try:
            with gzip.open(CHECKPOINT_FILE, 'wt', encoding='utf-8') as f: json.dump(game_state, f)
            debug_logger.debug(f"Game state saved to {CHECKPOINT_FILE}")
        except Exception as e: logger.error(f"Error saving game: {e}"); debug_logger.error(f"Error saving game: {e}", exc_info=True)

    def load_game(self):
        if not CHECKPOINT_FILE.exists(): 
            debug_logger.debug(f"No checkpoint file found at {CHECKPOINT_FILE}")
            return None
        try:
            with gzip.open(CHECKPOINT_FILE, 'rt', encoding='utf-8') as f: 
                game_state = json.load(f)
                debug_logger.debug(f"Game state loaded from {CHECKPOINT_FILE}")
                return game_state
        except Exception as e: 
            logger.error(f"Error loading game: {e}"); debug_logger.error(f"Error loading game: {e}", exc_info=True)
            CHECKPOINT_FILE.unlink(missing_ok=True); debug_logger.warning("Corrupted checkpoint deleted.")
            return None

    def save_scoreboard(self, scoreboard):
        try:
            with open(SCOREBOARD_FILE, 'w') as f: json.dump(scoreboard, f, indent=2)
            debug_logger.debug(f"Scoreboard saved to {SCOREBOARD_FILE}")
        except Exception as e: logger.error(f"Error saving scoreboard: {e}"); debug_logger.error(f"Error saving scoreboard: {e}", exc_info=True)

    def load_scoreboard(self):
        if not SCOREBOARD_FILE.exists(): 
            debug_logger.debug(f"No scoreboard file found at {SCOREBOARD_FILE}")
            return []
        try:
            with open(SCOREBOARD_FILE) as f:
                scoreboard = json.load(f)
            debug_logger.debug(f"Scoreboard loaded from {SCOREBOARD_FILE}")
            return scoreboard
        except Exception as e: 
            logger.error(f"Error loading scoreboard: {e}"); debug_logger.error(f"Error loading scoreboard: {e}", exc_info=True)
            SCOREBOARD_FILE.unlink(missing_ok=True); debug_logger.warning("Corrupted scoreboard deleted.")
            return []

    def reset_progress(self): 
        debug_logger.debug("Resetting all game progress.")
        CHECKPOINT_FILE.unlink(missing_ok=True); 
        SCOREBOARD_FILE.unlink(missing_ok=True)

class Game:
    def __init__(self, args, stdscr=None):
        self.stdscr = stdscr
        self.args = args
        self.persistence = Persistence(no_save=args.no_save)
        self.global_rng = random.Random()
        self.player, self.current_map, self.dungeon_depth, self.turn_count = None, None, 0, 0
        self.message_log, self.game_over, self.game_running = [], False, True
        self.show_inventory, self.show_help, self.show_high_scores = False, False, False
        self.summons = []  # List of active summons
        if self.stdscr: self.init_curses_colors()
        debug_logger.debug("Game object initialized.")
        self.load_or_start_game()

    def init_curses_colors(self):
        curses.start_color(); curses.use_default_colors()
        for i in range(1, 8): curses.init_pair(i, i, -1)
        curses.init_pair(9, COLOR_BLACK, COLOR_WHITE)
        debug_logger.debug("Curses colors initialized.")

    def add_message(self, message):
        self.message_log.append(message)
        if not self.stdscr: print(f"[LOG] {message}")
        debug_logger.debug(f"Message added: {message}")
        self.message_log = self.message_log[-MESSAGE_LOG_HEIGHT:]

    def new_game(self):
        import time
        seed = self.args.seed if self.args.seed is not None else int(time.time() * 1000000) % 1000000000
        self.global_rng.seed(seed)
        debug_logger.debug(f"New game started. Seed: {seed}")
        self.dungeon_depth, self.turn_count, self.message_log, self.game_over = 0, 0, [], False
        self.summons = []  # Reset summons
        self.player = Player(0, 0); self.generate_new_level()
        
        if self.stdscr: self.display_how_to_play()

    def load_or_start_game(self):
        debug_logger.debug("Attempting to load or start game.")
        if self.args.reset: self.persistence.reset_progress()
        game_state = self.persistence.load_game()
        if game_state: 
            self.load_game_state(game_state)
            debug_logger.debug("Game state loaded successfully.")
        else: 
            self.new_game()
            debug_logger.debug("No save found, starting new game.")
        if self.stdscr and game_state: self.display_splash_screen()

    def display_splash_screen(self):
        debug_logger.debug("Displaying splash screen.")
        self.stdscr.clear(); h, w = self.stdscr.getmaxyx()
        text = [f"Loaded: Depth {self.dungeon_depth}", "", "Press any key to continue or 'R' to reset."]
        for i, line in enumerate(text): self.stdscr.addstr(h//2 - 1 + i, w//2 - len(line)//2, line)
        self.stdscr.refresh()
        key = self.stdscr.getch()
        debug_logger.debug(f"Splash screen key press: {key}")
        if key in KEY_RESET_GAME: self.persistence.reset_progress(); self.new_game()

    def display_how_to_play(self):
        debug_logger.debug("Displaying how to play screen.")
        self.stdscr.clear(); h, w = self.stdscr.getmaxyx()
        text = ["--- How to Play ---", "Move: WASD or Arrows", "Inventory: i", "Goal: Find '>' to go deeper", "Good luck!", "", "Press any key to begin."]
        for i, line in enumerate(text): self.stdscr.addstr(h//2 - len(text)//2 + i, w//2 - len(line)//2, line)
        self.stdscr.refresh(); self.stdscr.getch()

    def generate_new_level(self):
        self.dungeon_depth += 1; level_seed = self.global_rng.randint(0, 1000000000)
        self.current_map = GameMap(MAP_WIDTH, MAP_HEIGHT, level_seed); self.current_map.generate_map(self.dungeon_depth)
        self.player.x, self.player.y = self.current_map.player_start_pos
        self.player.depth_reached = self.dungeon_depth
        
        # Add default companion on first level only
        if self.dungeon_depth == 1 and not self.summons:
            companion_names = ["Alex", "Sam", "Jordan", "Casey", "Riley", "Morgan", "Taylor", "Avery"]
            companion_name = self.global_rng.choice(companion_names)
            companion = Summon(0, 0, 1, 1)  # Create at (0,0) temporarily
            
            # Find a valid position next to player - NEVER same tile
            companion_placed = False
            for dx, dy in [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
                new_x, new_y = self.player.x + dx, self.player.y + dy
                if (0 <= new_x < self.current_map.width and 0 <= new_y < self.current_map.height and
                    self.current_map.tiles[new_y][new_x] == TILE_FLOOR and
                    (new_x, new_y) != (self.player.x, self.player.y) and  # Never same as player
                    not any(m.x == new_x and m.y == new_y for m in self.current_map.monsters) and
                    not any(s.x == new_x and s.y == new_y for s in self.summons)):
                    companion.x, companion.y = new_x, new_y
                    companion_placed = True
                    break
            
            # If still no spot found, search entire map for nearest floor tile
            if not companion_placed:
                for radius in range(2, 10):  # Search in expanding circles
                    for dx in range(-radius, radius + 1):
                        for dy in range(-radius, radius + 1):
                            if abs(dx) == radius or abs(dy) == radius:  # Only check perimeter
                                new_x, new_y = self.player.x + dx, self.player.y + dy
                                if (0 <= new_x < self.current_map.width and 0 <= new_y < self.current_map.height and
                                    self.current_map.tiles[new_y][new_x] == TILE_FLOOR and
                                    (new_x, new_y) != (self.player.x, self.player.y) and
                                    not any(m.x == new_x and m.y == new_y for m in self.current_map.monsters) and
                                    not any(s.x == new_x and s.y == new_y for s in self.summons)):
                                    companion.x, companion.y = new_x, new_y
                                    companion_placed = True
                                    break
                        if companion_placed:
                            break
                    if companion_placed:
                        break
            
            # Only create companion if valid position found
            if companion_placed:
                companion.name = f"{companion_name} the Guardian"
                companion.char = 'P'
                companion.color_pair = 6  # Cyan color
                self.summons.append(companion)
                self.add_message(f"{companion.name} joins you as your loyal companion!")
                debug_logger.debug(f"Companion created at ({companion.x}, {companion.y}) with char '{companion.char}'")
            else:
                debug_logger.warning("Could not find valid position for companion - skipping creation")
                self.add_message("Your companion couldn't find a safe place to join you.")
        
        # HP replenishment for player (25% minimum)
        heal_amount = max(int(self.player.get_max_hp() * 0.25), 1)
        old_hp = self.player.hp
        self.player.hp = min(self.player.get_max_hp(), self.player.hp + heal_amount)
        if self.player.hp > old_hp:
            self.add_message(f"You feel refreshed! Healed {self.player.hp - old_hp} HP.")
        
        # Move and heal summons to new level
        for summon in list(self.summons):
            if summon.is_alive():
                # HP replenishment for summons (25% minimum)
                summon_heal = max(int(summon.max_hp * 0.25), 1)
                old_summon_hp = summon.hp
                summon.hp = min(summon.max_hp, summon.hp + summon_heal)
                
                # Find empty spot near player for summon - NEVER same tile as player
                summon_placed = False
                for dx, dy in [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
                    new_x, new_y = self.player.x + dx, self.player.y + dy
                    if (0 <= new_x < self.current_map.width and 0 <= new_y < self.current_map.height and
                        self.current_map.get_tile(new_x, new_y) == TILE_FLOOR and
                        (new_x, new_y) != (self.player.x, self.player.y) and
                        not any(m.x == new_x and m.y == new_y for m in self.current_map.monsters) and
                        not any(s.x == new_x and s.y == new_y for s in self.summons if s != summon)):
                        summon.x, summon.y = new_x, new_y
                        summon_placed = True
                        break
                
                # If no adjacent space, search in expanding radius
                if not summon_placed:
                    for radius in range(2, 6):
                        for dx in range(-radius, radius + 1):
                            for dy in range(-radius, radius + 1):
                                if abs(dx) == radius or abs(dy) == radius:  # Only check perimeter
                                    new_x, new_y = self.player.x + dx, self.player.y + dy
                                    if (0 <= new_x < self.current_map.width and 0 <= new_y < self.current_map.height and
                                        self.current_map.get_tile(new_x, new_y) == TILE_FLOOR and
                                        (new_x, new_y) != (self.player.x, self.player.y) and
                                        not any(m.x == new_x and m.y == new_y for m in self.current_map.monsters) and
                                        not any(s.x == new_x and s.y == new_y for s in self.summons if s != summon)):
                                        summon.x, summon.y = new_x, new_y
                                        summon_placed = True
                                        break
                            if summon_placed:
                                break
                        if summon_placed:
                            break
                
                if not summon_placed:
                    debug_logger.warning(f"Could not find safe position for {summon.name} on new level - removing")
                    self.summons.remove(summon)
                    self.add_message(f"{summon.name} got lost during the transition!")
                
                if summon.hp > old_summon_hp:
                    self.add_message(f"{summon.name} feels refreshed!")
            else:
                # Remove dead summons
                self.summons.remove(summon)
        
        # Check if entering new biome
        current_biome = self.get_biome_colors(self.dungeon_depth)
        previous_biome = self.get_biome_colors(self.dungeon_depth - 1) if self.dungeon_depth > 1 else None
        
        if previous_biome and current_biome["name"] != previous_biome["name"]:
            self.add_message(f"You descended to Depth {self.dungeon_depth}!")
            self.add_message(f"You enter the {current_biome['name']} - {current_biome['description']}")
        else:
            self.add_message(f"You descended to Depth {self.dungeon_depth}!")
        
        self.save_game_state()
        debug_logger.debug(f"New level generated. Depth: {self.dungeon_depth}, Player pos: ({self.player.x},{self.player.y}), Biome: {current_biome['name']}")

    def save_game_state(self):
        state = {"player": self.player.to_dict(), "dungeon_depth": self.dungeon_depth, "turn_count": self.turn_count,
                 "global_seed": self.global_rng.getstate(), "map": self.current_map.to_dict(),
                 "summons": [s.to_dict() for s in self.summons]}
        self.persistence.save_game(state)
        debug_logger.debug(f"Game state saved. Turn: {self.turn_count}, Depth: {self.dungeon_depth}")

    def load_game_state(self, state):
        self.player = Player.from_dict(state["player"])
        self.dungeon_depth, self.turn_count = state["dungeon_depth"], state["turn_count"]
        rng_state = state["global_seed"]
        if isinstance(rng_state, list):
            if len(rng_state) > 1 and isinstance(rng_state[1], list):
                rng_state[1] = tuple(rng_state[1])
            self.global_rng.setstate(tuple(rng_state))
        self.current_map = GameMap.from_dict(state["map"])
        
        # Load summons
        self.summons = []
        if "summons" in state:
            for summon_data in state["summons"]:
                summon = Summon.from_dict(summon_data)
                self.summons.append(summon)
        
        self.add_message(f"Game loaded. Welcome back to Depth {self.dungeon_depth}.")
        debug_logger.debug(f"Game state loaded. Turn: {self.turn_count}, Depth: {self.dungeon_depth}")

    def handle_player_action(self, dx, dy):
        debug_logger.debug(f"Player action: dx={dx}, dy={dy}")
        new_x, new_y = self.player.x + dx, self.player.y + dy
        
        # Check for enemy at target position - combat
        target = next((m for m in self.current_map.monsters if m.x == new_x and m.y == new_y and m.is_alive()), None)
        if target: 
            debug_logger.debug(f"  -> Player initiating combat with {target.name}")
            self.combat(self.player, target)
        else:
            # Check for friendly summon at target position - swap positions
            friendly_summon = next((s for s in self.summons if s.x == new_x and s.y == new_y and s.is_alive()), None)
            moved = False
            
            if friendly_summon:
                # Swap positions with friendly summon (ensure both positions are valid)
                old_player_x, old_player_y = self.player.x, self.player.y
                if (0 <= new_x < self.current_map.width and 0 <= new_y < self.current_map.height and 
                    self.current_map.tiles[new_y][new_x] != TILE_WALL and
                    # Ensure no other entities at either position (except the two swapping)
                    not any(m.x == new_x and m.y == new_y for m in self.current_map.monsters) and
                    not any(s.x == old_player_x and s.y == old_player_y for s in self.summons if s != friendly_summon)):
                    self.player.x, self.player.y = new_x, new_y
                    friendly_summon.x, friendly_summon.y = old_player_x, old_player_y
                    debug_logger.debug(f"  -> Player swapped positions with {friendly_summon.name}")
                    moved = True
            elif self.player.move(dx, dy, self.current_map, self.current_map.monsters + self.summons):  # Check collision with all entities
                debug_logger.debug(f"  -> Player moved to ({self.player.x},{self.player.y})")
                moved = True
            
            # If player moved, check for portal teleportation and item pickup
            if moved:
                # Check for portal teleportation
                for x1, y1, x2, y2 in self.current_map.portals:
                    teleported = False
                    destination_x, destination_y = None, None
                    
                    if (self.player.x, self.player.y) == (x1, y1):
                        self.player.x, self.player.y = x2, y2
                        destination_x, destination_y = x2, y2
                        self.add_message("You step through the portal and are teleported!")
                        debug_logger.debug(f"  -> Player teleported from ({x1},{y1}) to ({x2},{y2})")
                        teleported = True
                    elif (self.player.x, self.player.y) == (x2, y2):
                        self.player.x, self.player.y = x1, y1
                        destination_x, destination_y = x1, y1
                        self.add_message("You step through the portal and are teleported!")
                        debug_logger.debug(f"  -> Player teleported from ({x2},{y2}) to ({x1},{y1})")
                        teleported = True
                    
                    # If player teleported, bring summons along
                    if teleported:
                        summons_teleported = 0
                        for summon in self.summons:
                            if summon.is_alive():
                                # Find empty spot near destination for summon
                                summon_placed = False
                                for radius in range(1, 4):  # Search in expanding radius
                                    for dx in range(-radius, radius + 1):
                                        for dy in range(-radius, radius + 1):
                                            if abs(dx) == radius or abs(dy) == radius:  # Only check perimeter
                                                new_x, new_y = destination_x + dx, destination_y + dy
                                                if (0 <= new_x < self.current_map.width and 0 <= new_y < self.current_map.height and
                                                    self.current_map.get_tile(new_x, new_y) == TILE_FLOOR and
                                                    (new_x, new_y) != (self.player.x, self.player.y) and
                                                    not any(m.x == new_x and m.y == new_y for m in self.current_map.monsters) and
                                                    not any(s.x == new_x and s.y == new_y for s in self.summons if s != summon)):
                                                    summon.x, summon.y = new_x, new_y
                                                    summons_teleported += 1
                                                    debug_logger.debug(f"  -> {summon.name} teleported to ({new_x},{new_y})")
                                                    summon_placed = True
                                                    break
                                        if summon_placed:
                                            break
                                    if summon_placed:
                                        break
                                
                                if not summon_placed:
                                    debug_logger.warning(f"  -> Could not find safe teleport location for {summon.name}")
                        
                        if summons_teleported > 0:
                            self.add_message(f"Your {summons_teleported} companion(s) followed you through the portal!")
                        break
                
                # Check for item pickup
                item = next((i for i in self.current_map.items if (i.x, i.y) == (self.player.x, self.player.y)), None)
                if item and self.player.add_item(item): 
                    self.current_map.items.remove(item); self.add_message(f"Picked up {item.name}!")
                    debug_logger.debug(f"  -> Player picked up {item.name}.")
                elif item: self.add_message("Inventory full!")
                
                # Check for stairs
                if (self.player.x, self.player.y) == self.current_map.stairs_down_pos: 
                    self.generate_new_level(); 
                    debug_logger.debug("  -> Player found stairs, descending.")
                    return
        
        self.end_player_turn()

    def combat(self, attacker, defender):
        base_damage = attacker.get_attack()
        
        # Level-scaling defense: higher level attackers penetrate defense better
        if isinstance(attacker, Monster) and isinstance(defender, Player):
            # Monster attacking player - defense effectiveness scales with level difference
            defense_effectiveness = max(0.3, 1.0 - (attacker.level - 1) * 0.1)
            effective_defense = int(defender.get_defense() * defense_effectiveness)
            damage = max(1, base_damage - effective_defense)
            self.add_message(f"{attacker.name} attacked for {damage} points")
        elif isinstance(attacker, Player) and isinstance(defender, Monster):
            # Player attacking monster - standard damage calculation
            damage = max(1, base_damage - defender.get_defense())
            self.add_message(f"You hit {defender.name} for {damage} damage.")
        elif isinstance(attacker, Summon) and isinstance(defender, Monster):
            # Summon attacking monster - standard damage calculation
            damage = max(1, base_damage - defender.get_defense())
            self.add_message(f"{attacker.name} hits {defender.name} for {damage} damage!")
        elif isinstance(attacker, Monster) and isinstance(defender, Summon):
            # Monster attacking summon - standard damage calculation
            damage = max(1, base_damage - defender.get_defense())
            self.add_message(f"{attacker.name} attacks {defender.name} for {damage} damage!")
        else:
            # Fallback for any other combinations
            damage = max(1, base_damage - defender.get_defense())
        
        debug_logger.debug(f"Combat: {attacker.name} (ATK:{base_damage}) vs {defender.name} (DEF:{defender.get_defense()}). Damage: {damage}")
        
        if defender.take_damage(damage):
            self.add_message(f"{defender.name} is defeated!")
            debug_logger.debug(f"  -> {defender.name} defeated.")
            if isinstance(defender, Player): 
                self.game_over = True
            elif isinstance(defender, Monster) and defender in self.current_map.monsters:
                if isinstance(attacker, Player):
                    self.player.monsters_killed += 1
                self.current_map.monsters.remove(defender)

    def end_player_turn(self):
        # Update temporary buffs
        buffs_expired = self.player.update_buffs()
        if buffs_expired:
            self.add_message("Some temporary effects have worn off.")
        
        debug_logger.debug(f"--- Turn {self.turn_count} End. Player HP: {self.player.hp}/{self.player.max_hp}, Pos: ({self.player.x},{self.player.y}) ---")
        
        # Summons take their turns first
        for summon in list(self.summons):
            if summon.is_alive():
                target = summon.take_turn(self.player, self.current_map, self.current_map.monsters, self.global_rng, self.summons)
                if target and target.is_alive():
                    debug_logger.debug(f"  -> {summon.name} attacking {target.name}")
                    self.combat(summon, target)
            else:
                self.summons.remove(summon)
        
        # Then monsters take their turns
        for monster in list(self.current_map.monsters):
            if monster.is_alive():
                target = monster.take_turn(self.player, self.current_map, self.global_rng, self.summons)
                
                # If monster AI returned a target, initiate combat
                if target and target.is_alive():
                    debug_logger.debug(f"  -> {monster.name} attacking {target.name}")
                    self.combat(monster, target)
                    
                    # Handle target death
                    if not target.is_alive():
                        if hasattr(target, 'inventory'):  # It's the player
                            if self.game_over: break
                        else:  # It's a summon
                            self.add_message(f"{target.name} has fallen!")
                            if target in self.summons:
                                self.summons.remove(target)
                else:
                    # Fallback: Check adjacency for any missed combat opportunities
                    # Check if monster is adjacent to player for combat
                    dx = abs(monster.x - self.player.x)
                    dy = abs(monster.y - self.player.y)
                    if (dx == 1 and dy == 0) or (dx == 0 and dy == 1):
                        self.combat(monster, self.player)
                        if self.game_over: break
                    
                    # Check if monster is adjacent to any summon for combat
                    for summon in list(self.summons):
                        if summon.is_alive():
                            sdx = abs(monster.x - summon.x)
                            sdy = abs(monster.y - summon.y)
                            if (sdx == 1 and sdy == 0) or (sdx == 0 and sdy == 1):
                                self.combat(monster, summon)
                                if not summon.is_alive():
                                    self.add_message(f"{summon.name} has fallen!")
                                    self.summons.remove(summon)
                                break
        
        self.turn_count += 1
        if self.turn_count % AUTOSAVE_INTERVAL_TURNS == 0: self.save_game_state(); self.add_message("Game autosaved.")

    def run(self):
        debug_logger.debug("Game run loop started.")
        if not self.stdscr:
            debug_logger.debug("Running in headless mode.")
            for _ in range(25): # Run for 25 turns in headless mode
                self.draw_headless()
                if self.current_map.monsters:
                    monster = self.current_map.monsters[0]
                    dx = 1 if monster.x > self.player.x else -1 if monster.x < self.player.x else 0
                    dy = 1 if monster.y > self.player.y else -1 if monster.y < self.player.y else 0
                    self.handle_player_action(dx, dy)
                else: # No monsters, just move randomly
                    self.handle_player_action(random.choice([-1, 0, 1]), random.choice([-1, 0, 1]))
                if self.game_over: break # Exit if player dies
            self.save_game_state()
            debug_logger.debug("Headless run finished.")
            return

        while self.game_running: 
            if self.game_over:
                self.handle_game_over()
                if not self.game_running:  # User chose to quit
                    break
                continue  # Restart the loop after game over handling
                
            if self.show_inventory:
                self.display_inventory()
            elif self.show_help:
                self.display_help()
            elif self.show_high_scores:
                self.display_high_scores()
            else:
                self.draw_ui()
            key = self.stdscr.getch()
            debug_logger.debug(f"Key pressed: {key}")
            self.handle_input(key)
        debug_logger.debug("Game run loop finished.")

    def handle_input(self, key):
        debug_logger.debug(f"Handling input: {key}")
        
        # Filter out mouse events and other unwanted input
        if key == -1 or key == curses.KEY_MOUSE:
            return
        
        # Handle UI state closures first
        if self.show_inventory or self.show_help or self.show_high_scores:
            if key == 27 or key in KEY_QUIT_ALT:  # ESC or Q to close
                self.show_inventory = self.show_help = self.show_high_scores = False
                debug_logger.debug("  -> Closed UI overlay.")
            elif self.show_inventory:
                self.handle_inventory_input(key)
            return
        
        # Normal game input
        if key in KEY_MOVE_N: self.handle_player_action(0, -1)
        elif key in KEY_MOVE_S: self.handle_player_action(0, 1)
        elif key in KEY_MOVE_E: self.handle_player_action(1, 0)
        elif key in KEY_MOVE_W: self.handle_player_action(-1, 0)
        elif key in KEY_INVENTORY: self.show_inventory = True; debug_logger.debug("  -> Opening inventory.")
        elif key in KEY_HELP: self.show_help = True; debug_logger.debug("  -> Opening help.")
        elif key in KEY_HIGH_SCORES: self.show_high_scores = True; debug_logger.debug("  -> Opening high scores.")
        elif key in KEY_RESET_GAME: 
            self.persistence.reset_progress()
            self.new_game()
            debug_logger.debug("  -> Game reset.")
        elif key in KEY_QUIT_ALT: self.game_running = False; debug_logger.debug("  -> Quit key pressed.")
        elif key == curses.KEY_RESIZE: debug_logger.debug("  -> Terminal resized.")
        else: debug_logger.debug(f"  -> Unhandled key: {key}")

    def handle_game_over(self):
        debug_logger.debug("Game Over state reached.")
        if not self.stdscr:
            print("GAME OVER!")
            return
            
        self.stdscr.clear()
        h, w = self.stdscr.getmaxyx()
        
        # Save score
        score = {
            'depth': self.dungeon_depth,
            'monsters': self.player.monsters_killed,
            'items': self.player.items_collected,
            'turns': self.turn_count
        }
        
        scoreboard = self.persistence.load_scoreboard()
        scoreboard.append(score)
        scoreboard.sort(key=lambda x: x['depth'], reverse=True)
        scoreboard = scoreboard[:MAX_HIGH_SCORES]
        self.persistence.save_scoreboard(scoreboard)
        
        # Display game over screen
        game_over_text = [
            "=== GAME OVER ===",
            "",
            f"You reached Depth {self.dungeon_depth}",
            f"Killed {self.player.monsters_killed} monsters",
            f"Collected {self.player.items_collected} items",
            f"Survived {self.turn_count} turns",
            "",
            "Press R to restart or Q to quit"
        ]
        
        start_y = h//2 - len(game_over_text)//2
        for i, line in enumerate(game_over_text):
            self.stdscr.addstr(start_y + i, w//2 - len(line)//2, line)
        
        self.stdscr.refresh()
        
        # Wait for input
        while True:
            key = self.stdscr.getch()
            if key in KEY_RESET_GAME:
                self.persistence.reset_progress()
                self.new_game()
                self.game_over = False
                break
            elif key in KEY_QUIT_ALT:
                self.game_running = False
                break 

    def get_biome_colors(self, depth):
        """Get biome-specific colors based on dungeon depth"""
        biomes = [
            # Depths 1-3: Stone Caverns (default gray/brown)
            {"name": "Stone Caverns", "floor": 7, "wall": 4, "description": "damp stone corridors"},
            # Depths 4-6: Ice Caves (cyan/blue)
            {"name": "Ice Caves", "floor": 6, "wall": 4, "description": "frozen crystalline chambers"},
            # Depths 7-9: Jungle Ruins (green)
            {"name": "Jungle Ruins", "floor": 2, "wall": 2, "description": "overgrown ancient temples"},
            # Depths 10-12: Fire Depths (red/yellow)
            {"name": "Fire Depths", "floor": 3, "wall": 1, "description": "molten volcanic tunnels"},
            # Depths 13-15: Shadow Realm (magenta/dark)
            {"name": "Shadow Realm", "floor": 5, "wall": 5, "description": "otherworldly dark passages"},
            # Depths 16+: Crystal Sanctum (bright colors cycling)
            {"name": "Crystal Sanctum", "floor": 6, "wall": 3, "description": "prismatic crystal formations"}
        ]
        
        # Determine biome index (every 3 levels)
        biome_index = min((depth - 1) // 3, len(biomes) - 1)
        return biomes[biome_index]

    def draw_ui(self):
        try:
            self.stdscr.erase()  # Clear screen properly
            h, w = self.stdscr.getmaxyx()
            debug_logger.debug(f"Drawing UI. Terminal size: {w}x{h}")

            # Handle terminal too small (initial check)
            if h < MIN_TERM_HEIGHT or w < MIN_TERM_WIDTH:
                self.stdscr.addstr(0,0,"Terminal too small! Please resize.")
                self.stdscr.refresh()
                return

            # Dynamically adjust map view dimensions based on current terminal size
            current_map_view_width = min(MAP_VIEW_WIDTH, w - (MAP_VIEW_WIDTH + 2)) # Account for HUD
            current_map_view_height = min(MAP_HEIGHT, h - MESSAGE_LOG_HEIGHT - 1)
            debug_logger.debug(f"Map view dimensions: {current_map_view_width}x{current_map_view_height}")

            # Calculate viewport (same as before, but using dynamic dimensions)
            vx1 = max(0, min(self.player.x - current_map_view_width // 2, MAP_WIDTH - current_map_view_width))
            vy1 = max(0, min(self.player.y - current_map_view_height // 2, MAP_HEIGHT - current_map_view_height))
            debug_logger.debug(f"Viewport: ({vx1},{vy1}) to ({vx1+current_map_view_width},{vy1+current_map_view_height})")

            for y in range(current_map_view_height):
                for x in range(current_map_view_width):
                    map_x, map_y = vx1 + x, vy1 + y
                    tile = self.current_map.get_tile(map_x, map_y)
                    
                    # --- MINIMAL CURSES MODE ---
                    if self.args.minimal_curses:
                        char, color = (TILE_FLOOR, 7) if tile == TILE_FLOOR else (TILE_WALL, 7) # Always white
                        if (self.player.x, self.player.y) == (map_x, map_y): char, color = TILE_PLAYER, 7
                    # --- END MINIMAL CURSES MODE ---
                    # --- DEBUG DRAW MODE ---
                    elif self.args.debug_draw:
                        if (self.player.x, self.player.y) == (map_x, map_y): char, color = self.player.char, self.player.color_pair
                    # --- END DEBUG DRAW MODE ---
                    else: # Full drawing mode
                        # Get biome-specific colors
                        biome = self.get_biome_colors(self.dungeon_depth)
                        char, color = (tile, biome["floor"]) if tile == TILE_FLOOR else (tile, biome["wall"])
                        if (map_x, map_y) == self.current_map.stairs_down_pos: char, color = TILE_STAIRS_DOWN, 6
                        # Check for portals
                        if tile == TILE_PORTAL: char, color = TILE_PORTAL, 5  # Magenta portals
                        item = next((i for i in self.current_map.items if (i.x, i.y) == (map_x, map_y)), None)
                        if item: char, color = item.char, item.color_pair
                        summon = next((s for s in self.summons if (s.x, s.y) == (map_x, map_y) and s.is_alive()), None)
                        if summon: char, color = summon.char, summon.color_pair
                        monster = next((m for m in self.current_map.monsters if (m.x, m.y) == (map_x, map_y) and m.is_alive()), None)
                        if monster: char, color = monster.char, monster.color_pair
                        # Only show player if no summon at same position
                        if (self.player.x, self.player.y) == (map_x, map_y) and not summon: 
                            char, color = self.player.char, self.player.color_pair
                    
                    if 0 <= y < h and 0 <= x < w: # Explicit boundary check
                        try:
                            self.stdscr.addch(y, x, char, curses.color_pair(color))
                        except curses.error:
                            pass  # Ignore curses errors at screen boundaries

            # --- MINIMAL CURSES MODE ---
            if not self.args.minimal_curses:
                # Draw HUD (adjust hud_x based on current_map_view_width)
                hud_x = current_map_view_width + 2
                p = self.player
                
                # Player stats with biome info
                biome = self.get_biome_colors(self.dungeon_depth)
                stats = [
                    "=== PLAYER ===",
                    f"HP: {p.hp}/{p.get_max_hp()}", 
                    f"ATK: {p.get_attack()} DEF: {p.get_defense()}", 
                    f"Depth: {self.dungeon_depth}",
                    f"Biome: {biome['name']}"
                ]
                
                # Add active buffs to stats
                if p.temp_buffs:
                    stats.append("Buffs:")
                    for buff_type, (amount, steps) in p.temp_buffs.items():
                        buff_name = {"defense": "DEF", "hp": "HP", "attack": "ATK"}.get(buff_type, buff_type.upper())
                        stats.append(f"  {buff_name}+{amount} ({steps})")
                
                # Add summon stats
                if self.summons:
                    stats.append("")  # Empty line separator
                    stats.append("=== SUMMONS ===")
                    for summon in self.summons:
                        if summon.is_alive():
                            stats.append(f"{summon.name}")
                            stats.append(f"HP: {summon.hp}/{summon.max_hp} ATK: {summon.atk} DEF: {summon.def_val}")
                
                for i, stat in enumerate(stats): 
                    if i < h and hud_x < w:
                        self.stdscr.addstr(i, hud_x, stat[:w-hud_x-1])

                for i, msg in enumerate(self.message_log): 
                    msg_y = h - MESSAGE_LOG_HEIGHT + i
                    if 0 <= msg_y < h:
                        self.stdscr.addstr(msg_y, 0, msg[:w-1])
            # --- END MINIMAL CURSES MODE ---
            
            self.stdscr.refresh()
            debug_logger.debug("UI drawing complete.")
            
        except Exception as e:
            debug_logger.error(f"Error in draw_ui: {e}")
            # Fallback: just refresh the screen
            try:
                self.stdscr.refresh()
            except:
                pass

    def draw_headless(self):
        debug_logger.debug(f"Drawing headless. Turn: {self.turn_count}, Depth: {self.dungeon_depth}")
        print(f"\n--- Turn {self.turn_count}, Depth {self.dungeon_depth} ---")
        grid = [list(row) for row in self.current_map.tiles]
        for item in self.current_map.items: grid[item.y][item.x] = item.char
        for monster in self.current_map.monsters: grid[monster.y][monster.x] = monster.char
        grid[self.player.y][self.player.x] = TILE_PLAYER
        for row in grid: print("".join(row))
        print(f"Player HP: {self.player.hp}/{self.player.max_hp}")

    def display_inventory(self):
        self.stdscr.clear()
        h, w = self.stdscr.getmaxyx()
        
        title = "=== INVENTORY ==="
        self.stdscr.addstr(1, w//2 - len(title)//2, title)
        
        if not self.player.inventory:
            self.stdscr.addstr(3, w//2 - 8, "Inventory empty")
        else:
            for i, item in enumerate(self.player.inventory):
                item_text = f"{chr(ord('a') + i)}) {item.name}"
                if item.stackable and item.qty > 1:
                    item_text += f" x{item.qty}"
                self.stdscr.addstr(3 + i, 2, item_text)
        
        self.stdscr.addstr(h-2, 2, "Press ESC or Q to close, a-j to use item")
        self.stdscr.refresh()

    def display_help(self):
        self.stdscr.clear()
        h, w = self.stdscr.getmaxyx()
        
        help_text = [
            "=== HELP ===",
            "",
            "Movement: WASD or Arrow Keys",
            "Inventory: I",
            "Help: ? or F1",
            "High Scores: H",
            "Reset Game: R",
            "Quit: Q",
            "",
            "Combat: Defense reduces damage (min 1)",
            "Equipment: Weapons boost ATK, Armor boosts DEF",
            "Goal: Find '>' stairs to descend deeper",
            "",
            "Press ESC or Q to close"
        ]
        
        start_y = h//2 - len(help_text)//2
        for i, line in enumerate(help_text):
            self.stdscr.addstr(start_y + i, w//2 - len(line)//2, line)
        
        self.stdscr.refresh()

    def display_high_scores(self):
        self.stdscr.clear()
        h, w = self.stdscr.getmaxyx()
        
        title = "=== HIGH SCORES ==="
        self.stdscr.addstr(1, w//2 - len(title)//2, title)
        
        scores = self.persistence.load_scoreboard()
        if not scores:
            self.stdscr.addstr(3, w//2 - 8, "No scores yet!")
        else:
            for i, score in enumerate(scores[:5]):
                score_text = f"{i+1}. Depth {score.get('depth', 0)} - {score.get('monsters', 0)} kills"
                self.stdscr.addstr(3 + i, w//2 - len(score_text)//2, score_text)
        
        self.stdscr.addstr(h-2, w//2 - 10, "Press ESC or Q to close")
        self.stdscr.refresh()

    def handle_inventory_input(self, key):
        debug_logger.debug(f"Handling inventory input: {key}")
        if ord('a') <= key <= ord('j'):
            item_index = key - ord('a')
            if 0 <= item_index < len(self.player.inventory):
                item = self.player.inventory[item_index]
                if item.use(self.player, self):
                    self.show_inventory = False
                    self.end_player_turn()
                debug_logger.debug(f"  -> Used item {item.name}")
            else:
                debug_logger.debug(f"  -> Invalid item index: {item_index}")

def run_self_tests():
    debug_logger.debug("Running self-tests...")
    print("Running self-tests...")
    results, all_passed = [], True
    try:
        test_map = GameMap(30, 30, 123); test_map.generate_map(1)
        assert test_map.player_start_pos and test_map.stairs_down_pos
        results.append("Map Generation: PASS")
    except Exception as e: results.append(f"Map Generation: FAIL ({e})"); all_passed = False
    
    try:
        args = argparse.Namespace(seed=None, reset=True, no_save=True, headless=False, debug=False)
        game_instance = Game(args, stdscr=None)
        assert game_instance.dungeon_depth == 1
        results.append("New Game Creation: PASS")
    except Exception as e: results.append(f"New Game Creation: FAIL ({e})"); all_passed = False

    try:
        args = argparse.Namespace(seed=123, reset=True, no_save=False, headless=True, debug=False)
        global CHECKPOINT_FILE
        original_checkpoint = CHECKPOINT_FILE
        CHECKPOINT_FILE = Path("./test_checkpoint.json.gz")
        
        game1 = Game(args, stdscr=None)
        if game1.current_map.monsters:
            monster = game1.current_map.monsters[0]
            game1.combat(monster, game1.player) # Force combat
        game1.turn_count = 15 # Set known state
        game1.save_game_state()

        load_args = argparse.Namespace(seed=123, reset=False, no_save=False, headless=True, debug=False)
        game2 = Game(load_args, stdscr=None)
        assert game2.turn_count == 15
        assert game2.player.hp < game2.player.max_hp
        results.append("Save/Load Cycle: PASS")
    except Exception as e:
        results.append(f"Save/Load Cycle: FAIL ({e})"); all_passed = False
    finally:
        if CHECKPOINT_FILE.exists(): CHECKPOINT_FILE.unlink()
        CHECKPOINT_FILE = original_checkpoint

    debug_logger.debug("Self-test results summary:")
    print("\nSelf-Test Results:")
    for res in results: 
        print(res)
        debug_logger.debug(res)
    if not all_passed: sys.exit(1)

def main_game(stdscr, args):
    # Ignore SIGINT (Ctrl+C/Cmd+C) to allow copying map for debugging
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    setup_logging(args.debug)
    debug_logger.debug("main_game function started.")
    curses.curs_set(0)
    stdscr.nodelay(False)  # Block for input
    stdscr.keypad(True)    # Enable special keys
    curses.noecho()        # Don't echo keys
    curses.cbreak()        # React to keys immediately
    stdscr.scrollok(False) # Disable scrolling
    game = Game(args, stdscr=stdscr)
    try:
        game.run()
    except Exception as e:
        logger.exception("Critical error during game execution:")
        debug_logger.exception("Critical error during game execution:")
        if stdscr:
            stdscr.clear()
            stdscr.addstr(0, 0, "A critical error occurred! Please check term_dungeon_rpg.log for details.")
            stdscr.addstr(1, 0, "Press any key to exit.")
            stdscr.refresh()
            stdscr.getch()
        sys.exit(1) # Exit with an error code
    finally:
        if hasattr(game, 'game_running') and game.game_running and not game.game_over: game.save_game_state()
        debug_logger.debug("main_game function finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--test", action="store_true", dest="test_mode")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--debug-draw", action="store_true", help=argparse.SUPPRESS) # Hidden from help
    parser.add_argument("--minimal-curses", action="store_true", help=argparse.SUPPRESS) # Hidden from help
    args = parser.parse_args()

    setup_logging(args.debug)
    debug_logger.debug("Script execution started.")

    if args.test_mode:
        run_self_tests()
        debug_logger.debug("Test mode finished.")
        sys.exit(0)
    
    if args.headless:
        game = Game(args)
        game.run()
        debug_logger.debug("Headless mode finished.")
        sys.exit(0)

    if sys.platform == "win32":
        try: import windows_curses
        except ImportError: print("Error: 'windows-curses' not found."); debug_logger.error("windows-curses not found."); sys.exit(1)
    
    main_with_args = partial(main_game, args=args)
    curses.wrapper(main_with_args)
    debug_logger.debug("Script execution finished.")
