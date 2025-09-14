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

    def move(self, dx, dy, game_map):
        new_x, new_y = self.x + dx, self.y + dy
        if 0 <= new_x < game_map.width and 0 <= new_y < game_map.height and game_map.tiles[new_y][new_x] != TILE_WALL:
            self.x, self.y = new_x, new_y
            debug_logger.debug(f"  -> {self.name} moved to ({self.x},{self.y})")
            return True
        debug_logger.debug(f"  -> {self.name} tried to move to ({new_x},{new_y}) but was blocked.")
        return False

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

    def to_dict(self):
        return {"x": self.x, "y": self.y, "char": self.char, "color_pair": self.color_pair, "name": self.name,
                "hp": self.hp, "max_hp": self.max_hp, "atk": self.atk, "def_val": self.def_val}

    def to_dict(self):
        return {"x": self.x, "y": self.y, "char": self.char, "color_pair": self.color_pair, "name": self.name,
                "hp": self.hp, "max_hp": self.max_hp, "atk": self.atk, "def_val": self.def_val}

    def to_dict(self):
        return {"x": self.x, "y": self.y, "char": self.char, "color_pair": self.color_pair, "name": self.name,
                "hp": self.hp, "max_hp": self.max_hp, "atk": self.atk, "def_val": self.def_val}

    def to_dict(self):
        return {"x": self.x, "y": self.y, "char": self.char, "color_pair": self.color_pair, "name": self.name,
                "hp": self.hp, "max_hp": self.max_hp, "atk": self.atk, "def_val": self.def_val}

    def to_dict(self):
        return {"x": self.x, "y": self.y, "char": self.char, "color_pair": self.color_pair, "name": self.name,
                "hp": self.hp, "max_hp": self.max_hp, "atk": self.atk, "def_val": self.def_val}

    def to_dict(self):
        return {"x": self.x, "y": self.y, "char": self.char, "color_pair": self.color_pair, "name": self.name,
                "hp": self.hp, "max_hp": self.max_hp, "atk": self.atk, "def_val": self.def_val}

    def to_dict(self):
        return {"x": self.x, "y": self.y, "char": self.char, "color_pair": self.color_pair, "name": self.name,
                "hp": self.hp, "max_hp": self.max_hp, "atk": self.atk, "def_val": self.def_val}

    def to_dict(self):
        return {"x": self.x, "y": self.y, "char": self.char, "color_pair": self.color_pair, "name": self.name,
                "hp": self.hp, "max_hp": self.max_hp, "atk": self.atk, "def_val": self.def_val}

    def to_dict(self):
        return {"x": self.x, "y": self.y, "char": self.char, "color_pair": self.color_pair, "name": self.name,
                "hp": self.hp, "max_hp": self.max_hp, "atk": self.atk, "def_val": self.def_val}

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

    def get_attack(self): return self.atk + (self.equipped_weapon.power if self.equipped_weapon else 0)
    def get_defense(self): return self.def_val + (self.equipped_armor.power if self.equipped_armor else 0)

    def to_dict(self):
        data = super().to_dict()
        data.update({"inventory": [item.to_dict() for item in self.inventory], "depth_reached": self.depth_reached,
                     "monsters_killed": self.monsters_killed, "items_collected": self.items_collected,
                     "equipped_weapon": self.equipped_weapon.to_dict() if self.equipped_weapon else None,
                     "equipped_armor": self.equipped_armor.to_dict() if self.equipped_armor else None})
        return data

    @classmethod
    def from_dict(cls, data):
        player = cls(data["x"], data["y"]); player.__dict__.update(data)
        player.inventory = [Item.from_dict(item_data) for item_data in data["inventory"]]
        if data.get("equipped_weapon"): player.equipped_weapon = Item.from_dict(data["equipped_weapon"])
        if data.get("equipped_armor"): player.equipped_armor = Item.from_dict(data["equipped_armor"])
        return player

class Monster(Entity):
    def __init__(self, x, y, monster_id, depth):
        templates = {"goblin": ('g', 2, "Goblin", 5, 2, 0, 5), "orc": ('o', 3, "Orc", 10, 4, 1, 7), "slime": ('s', 4, "Slime", 3, 1, 0, 4)}
        char, color, name, hp, atk, def_val, sight = templates.get(monster_id, templates["slime"])
        super().__init__(x, y, char, color, name, hp + depth, atk + depth // 2, def_val + depth // 3)
        self.monster_id = monster_id

    def take_turn(self, player, game_map, rng):
        debug_logger.debug(f"  -> {self.name} ({self.monster_id}) taking turn.")
        if abs(self.x - player.x) <= 8 and abs(self.y - player.y) <= 8:
            dx = 1 if player.x > self.x else -1 if player.x < self.x else 0
            dy = 1 if player.y > self.y else -1 if player.y < self.y else 0
            debug_logger.debug(f"    -> Chasing player. Target dx:{dx}, dy:{dy}")
            if not self.move(dx, dy, game_map):
                if dx != 0 and self.move(dx, 0, game_map): pass
                elif dy != 0 and self.move(0, dy, game_map): pass
        else:
            dx, dy = rng.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
            debug_logger.debug(f"    -> Wandering. Chosen dx:{dx}, dy:{dy}")
            self.move(dx, dy, game_map)

    def to_dict(self):
        data = super().to_dict(); data.update({"monster_id": self.monster_id}); return data

    @classmethod
    def from_dict(cls, data):
        monster = cls(data["x"], data["y"], data["monster_id"], 1); monster.__dict__.update(data); return monster

class Item:
    def __init__(self, x, y, item_id, qty=1):
        self.x, self.y, self.item_id, self.qty = x, y, item_id, qty
        templates = {"potion": ("Health Potion", TILE_POTION, 5, True, 10, self._use_potion),
                     "sword": ("Iron Sword", TILE_WEAPON, 6, False, 2, self._equip_weapon),
                     "shield": ("Wooden Shield", TILE_ARMOR, 4, False, 1, self._equip_armor)}
        self.name, self.char, self.color_pair, self.stackable, self.power, self.effect = templates.get(item_id, ("Unknown", '?', 7, False, 0, None))

    def _use_potion(self, player, game):
        debug_logger.debug(f"  -> Using {self.name}.")
        if player.hp >= player.max_hp: game.add_message("You are already at full health."); return False
        player.hp = min(player.max_hp, player.hp + self.power)
        game.add_message(f"You used a {self.name} and healed {self.power} HP!"); player.remove_item(self); return True

    def _equip_weapon(self, player, game):
        debug_logger.debug(f"  -> Equipping {self.name}.")
        if player.equipped_weapon: player.inventory.append(player.equipped_weapon)
        player.equipped_weapon = self; player.remove_item(self); game.add_message(f"You equipped the {self.name}."); return True

    def _equip_armor(self, player, game):
        debug_logger.debug(f"  -> Equipping {self.name}.")
        if player.equipped_armor: player.inventory.append(player.equipped_armor)
        player.equipped_armor = self; player.remove_item(self); game.add_message(f"You equipped the {self.name}."); return True

    def use(self, player, game): return self.effect(player, game) if self.effect else False
    def to_dict(self): return {"x": self.x, "y": self.y, "item_id": self.item_id, "qty": self.qty}
    @classmethod
    def from_dict(cls, data): return cls(data["x"], data["y"], data["item_id"], data["qty"])

class GameMap:
    def __init__(self, width, height, seed):
        self.width, self.height, self.seed = width, height, seed
        self.tiles = [[TILE_WALL for _ in range(width)] for _ in range(height)]
        self.monsters, self.items = [], []; self.stairs_down_pos, self.player_start_pos = None, None
        self.rng = random.Random(seed)

    def generate_map(self, depth):
        debug_logger.debug(f"Generating map for depth {depth} with seed {self.seed}")
        rooms = []
        for _ in range(self.rng.randint(5, 10) + depth // 2):
            w, h = self.rng.randint(5, 15), self.rng.randint(3, 10)
            x, y = self.rng.randint(1, self.width - w - 2), self.rng.randint(1, self.height - h - 2)
            new_room = {'x1': x, 'y1': y, 'x2': x + w, 'y2': y + h}
            if not any((new_room['x1'] <= r['x2'] and new_room['x2'] >= r['x1'] and new_room['y1'] <= r['y2'] and new_room['y2'] >= r['y1']) for r in rooms):
                rooms.append(new_room)
                for ry in range(new_room['y1'], new_room['y2']):
                    for rx in range(new_room['x1'], new_room['x2']): self.tiles[ry][rx] = TILE_FLOOR
        if not rooms: self.generate_map(depth); return

        for i in range(1, len(rooms)):
            px, py = self.rng.randint(rooms[i-1]['x1'], rooms[i-1]['x2']-1), self.rng.randint(rooms[i-1]['y1'], rooms[i-1]['y2']-1)
            cx, cy = self.rng.randint(rooms[i]['x1'], rooms[i]['x2']-1), self.rng.randint(rooms[i]['y1'], rooms[i]['y2']-1)
            for x in range(min(px, cx), max(px, cx) + 1): self.tiles[py][x] = TILE_FLOOR
            for y in range(min(py, cy), max(py, cy) + 1): self.tiles[y][cx] = TILE_FLOOR

        self.player_start_pos = (self.rng.randint(rooms[0]['x1'], rooms[0]['x2'] - 1), self.rng.randint(rooms[0]['y1'], rooms[0]['y2'] - 1))
        self.stairs_down_pos = (self.rng.randint(rooms[-1]['x1'], rooms[-1]['x2'] - 1), self.rng.randint(rooms[-1]['y1'], rooms[-1]['y2'] - 1))
        self.tiles[self.stairs_down_pos[1]][self.stairs_down_pos[0]] = TILE_STAIRS_DOWN

        for _ in range(self.rng.randint(depth, depth * 2 + 3)):
            room = self.rng.choice(rooms)
            mx, my = self.rng.randint(room['x1'], room['x2'] - 1), self.rng.randint(room['y1'], room['y2'] - 1)
            if (mx, my) != self.player_start_pos: self.monsters.append(Monster(mx, my, self.rng.choice(["goblin", "orc"]), depth))
        for _ in range(self.rng.randint(1, 3) + depth // 3):
            room = self.rng.choice(rooms)
            ix, iy = self.rng.randint(room['x1'], room['x2'] - 1), self.rng.randint(room['y1'], room['y2'] - 1)
            if not any(m.x == ix and m.y == iy for m in self.monsters): self.items.append(Item(ix, iy, self.rng.choice(["potion", "sword", "shield"])))

    def get_tile(self, x, y): return self.tiles[y][x] if 0 <= x < self.width and 0 <= y < self.height else TILE_WALL
    def to_dict(self): return {"seed": self.seed, "monsters": [m.to_dict() for m in self.monsters], "items": [i.to_dict() for i in self.items]}
    @classmethod
    def from_dict(cls, data):
        game_map = cls(MAP_WIDTH, MAP_HEIGHT, data["seed"])
        game_map.generate_map(1)
        game_map.monsters = [Monster.from_dict(m_data) for m_data in data["monsters"]]
        game_map.items = [Item.from_dict(i_data) for i_data in data["items"]]
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
            scoreboard = json.load(open(SCOREBOARD_FILE))
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
        seed = self.args.seed if self.args.seed is not None else self.global_rng.randint(0, 1000000000)
        self.global_rng.seed(seed)
        debug_logger.debug(f"New game started. Seed: {seed}")
        self.dungeon_depth, self.turn_count, self.message_log, self.game_over = 0, 0, [], False
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
        self.add_message(f"You descended to Depth {self.dungeon_depth}!"); self.save_game_state()
        debug_logger.debug(f"New level generated. Depth: {self.dungeon_depth}, Player pos: ({self.player.x},{self.player.y})")

    def save_game_state(self):
        state = {"player": self.player.to_dict(), "dungeon_depth": self.dungeon_depth, "turn_count": self.turn_count,
                 "global_seed": self.global_rng.getstate(), "map": self.current_map.to_dict()}
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
        self.add_message(f"Game loaded. Welcome back to Depth {self.dungeon_depth}.")
        debug_logger.debug(f"Game state loaded. Turn: {self.turn_count}, Depth: {self.dungeon_depth}")

    def handle_player_action(self, dx, dy):
        debug_logger.debug(f"Player action: dx={dx}, dy={dy}")
        new_x, new_y = self.player.x + dx, self.player.y + dy
        target = next((m for m in self.current_map.monsters if m.x == new_x and m.y == new_y and m.is_alive()), None)
        if target: 
            debug_logger.debug(f"  -> Player initiating combat with {target.name}")
            self.combat(self.player, target)
        elif self.player.move(dx, dy, self.current_map):
            debug_logger.debug(f"  -> Player moved to ({self.player.x},{self.player.y})")
            item = next((i for i in self.current_map.items if (i.x, i.y) == (self.player.x, self.player.y)), None)
            if item and self.player.add_item(item): 
                self.current_map.items.remove(item); self.add_message(f"Picked up {item.name}!")
                debug_logger.debug(f"  -> Player picked up {item.name}.")
            elif item: self.add_message("Inventory full!")
            if (self.player.x, self.player.y) == self.current_map.stairs_down_pos: 
                self.generate_new_level(); 
                debug_logger.debug("  -> Player found stairs, descending.")
                return
        else: 
            self.add_message("You can't move there.")
            debug_logger.debug("  -> Player hit obstacle.")
            return
        self.end_player_turn()

    def combat(self, attacker, defender):
        damage = max(1, attacker.get_attack() - defender.get_defense())
        debug_logger.debug(f"Combat: {attacker.name} (ATK:{attacker.get_attack()}) vs {defender.name} (DEF:{defender.get_defense()}). Damage: {damage}")
        if defender.take_damage(damage):
            self.add_message(f"{defender.name} is defeated!")
            debug_logger.debug(f"  -> {defender.name} defeated.")
            if isinstance(defender, Player): self.game_over = True
            else: self.player.monsters_killed += 1; self.current_map.monsters.remove(defender)
        else: self.add_message(f"{attacker.name} hits {defender.name} for {damage} damage.")

    def end_player_turn(self):
        debug_logger.debug(f"--- Turn {self.turn_count} End. Player HP: {self.player.hp}/{self.player.max_hp}, Pos: ({self.player.x},{self.player.y}) ---")
        for monster in list(self.current_map.monsters): # Iterate over a copy
            if monster.is_alive() and (monster.x, monster.y) != (self.player.x, self.player.y):
                monster.take_turn(self.player, self.current_map, self.global_rng)
                if (monster.x, monster.y) == (self.player.x, self.player.y): 
                    debug_logger.debug(f"  -> Monster {monster.name} initiating combat with Player.")
                    self.combat(monster, self.player)
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

        while self.game_running and not self.game_over: 
            self.draw_ui()
            key = self.stdscr.getch()
            debug_logger.debug(f"Key pressed: {key}")
            self.handle_input(key)
            curses.doupdate() # Update the screen once per turn
        if self.game_over: self.handle_game_over()
        debug_logger.debug("Game run loop finished.")

    def handle_input(self, key):
        debug_logger.debug(f"Handling input: {key}")
        if key in KEY_MOVE_N: self.handle_player_action(0, -1)
        elif key in KEY_MOVE_S: self.handle_player_action(0, 1)
        elif key in KEY_MOVE_E: self.handle_player_action(1, 0)
        elif key in KEY_MOVE_W: self.handle_player_action(-1, 0)
        elif key in KEY_INVENTORY: self.show_inventory = True; debug_logger.debug("  -> Opening inventory.")
        elif key in KEY_HELP: self.show_help = True; debug_logger.debug("  -> Opening help.")
        elif key in KEY_HIGH_SCORES: self.show_high_scores = True; debug_logger.debug("  -> Opening high scores.")
        elif key in KEY_QUIT_ALT: self.game_running = False; debug_logger.debug("  -> Quit key pressed.")
        elif key == curses.KEY_RESIZE: debug_logger.debug("  -> Terminal resized.")
        else: debug_logger.debug("  -> Unhandled key.")

    def handle_game_over(self):
        debug_logger.debug("Game Over state reached.")
        # Placeholder for actual game over screen and score submission
        pass 

    def draw_ui(self):
        self.stdscr.clear(); h, w = self.stdscr.getmaxyx()
        debug_logger.debug(f"Drawing UI. Terminal size: {w}x{h}")

        # Handle terminal too small (initial check)
        if h < MIN_TERM_HEIGHT or w < MIN_TERM_WIDTH:
            self.stdscr.addstr(0,0,"Terminal too small! Please resize."); self.stdscr.refresh(); return

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
                    char, color = (tile, 7) if tile == TILE_FLOOR else (tile, 4)
                    if (map_x, map_y) == self.current_map.stairs_down_pos: char, color = TILE_STAIRS_DOWN, 6
                    item = next((i for i in self.current_map.items if (i.x, i.y) == (map_x, map_y)), None)
                    if item: char, color = item.char, item.color_pair
                    monster = next((m for m in self.current_map.monsters if (m.x, m.y) == (map_x, map_y) and m.is_alive()), None)
                    if monster: char, color = monster.char, monster.color_pair
                    if (self.player.x, self.player.y) == (map_x, map_y): char, color = self.player.char, self.player.color_pair
                
                if 0 <= y < h and 0 <= x < w: # Explicit boundary check
                    self.stdscr.addch(y, x, char, curses.color_pair(color))
        self.stdscr.noutrefresh()

        # --- MINIMAL CURSES MODE ---
        if not self.args.minimal_curses:
            # Draw HUD (adjust hud_x based on current_map_view_width)
            hud_x = current_map_view_width + 2
            p = self.player
            stats = [f"HP: {p.hp}/{p.max_hp}", f"ATK: {p.get_attack()}", f"DEF: {p.get_defense()}", f"Depth: {self.dungeon_depth}"]
            for i, stat in enumerate(stats): self.stdscr.addstr(i, hud_x, stat)

            for i, msg in enumerate(self.message_log): self.stdscr.addstr(h - MESSAGE_LOG_HEIGHT + i, 0, msg.ljust(w))
        # --- END MINIMAL CURSES MODE ---
        debug_logger.debug("UI drawing complete.")

    def draw_headless(self):
        debug_logger.debug(f"Drawing headless. Turn: {self.turn_count}, Depth: {self.dungeon_depth}")
        print(f"\n--- Turn {self.turn_count}, Depth {self.dungeon_depth} ---")
        grid = [list(row) for row in self.current_map.tiles]
        for item in self.current_map.items: grid[item.y][item.x] = item.char
        for monster in self.current_map.monsters: grid[monster.y][monster.x] = monster.char
        grid[self.player.y][self.player.x] = TILE_PLAYER
        for row in grid: print("".join(row))
        print(f"Player HP: {self.player.hp}/{self.player.max_hp}")

    def handle_inventory_input(self, key):
        debug_logger.debug(f"Handling inventory input: {key}")
        # Placeholder for inventory logic
        pass

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
    setup_logging(args.debug)
    debug_logger.debug("main_game function started.")
    curses.curs_set(0); stdscr.nodelay(True); stdscr.timeout(100)
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
