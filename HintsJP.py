import io
import hashlib
import logging
import os
import struct
import random
import re
from collections import OrderedDict
import urllib.request
from urllib.error import URLError, HTTPError
import json
from enum import Enum
import itertools

from TransJP import LocationJP, ItemTrJP
from HintListJP import getHint, getHintGroup, Hint, hintExclusions, HT
from Item import MakeEventItem
from MessagesJP import update_message_jp
from StartingItems import everything
from Search import Search
from Utils import random_choices, data_path, read_json


bingoBottlesForHints = (
    "Bottle", "Bottle with Red Potion","Bottle with Green Potion", "Bottle with Blue Potion",
    "Bottle with Fairy", "Bottle with Fish", "Bottle with Blue Fire", "Bottle with Bugs",
    "Bottle with Big Poe", "Bottle with Poe",
)

defaultHintDists = [
    'balanced.json', 'bingo.json', 'ddr.json', 'scrubs.json', 'strong.json', 'tournament.json', 'useless.json', 'very_strong.json'
]

class RegionRestriction(Enum):
    NONE = 0,
    DUNGEON = 1,
    OVERWORLD = 2,


class GossipStone():
    def __init__(self, name, location):
        self.name = name
        self.location = location
        self.reachable = True


class GossipText():
    def __init__(self, text, colors=None, prefix=""):
        text = prefix + text
        self.text = text
        self.colors = colors


    def to_json(self):
        return {'text': self.text, 'colors': self.colors}


    def __str__(self):
        return get_raw_text(colorText(self))

#   Abbreviations
#       DMC     Death Mountain Crater
#       DMT     Death Mountain Trail
#       GC      Goron City
#       GV      Gerudo Valley
#       HC      Hyrule Castle
#       HF      Hyrule Field
#       KF      Kokiri Forest
#       LH      Lake Hylia
#       LW      Lost Woods
#       SFM     Sacred Forest Meadow
#       ToT     Temple of Time
#       ZD      Zora's Domain
#       ZF      Zora's Fountain
#       ZR      Zora's River

gossipLocations = {
    0x0405: GossipStone('DMC (Bombable Wall)',              'DMC Gossip Stone'),
    0x0404: GossipStone('DMT (Biggoron)',                   'DMT Gossip Stone'),
    0x041A: GossipStone('Colossus (Spirit Temple)',         'Colossus Gossip Stone'),
    0x0414: GossipStone('Dodongos Cavern (Bombable Wall)',  'Dodongos Cavern Gossip Stone'),
    0x0411: GossipStone('GV (Waterfall)',                   'GV Gossip Stone'),
    0x0415: GossipStone('GC (Maze)',                        'GC Maze Gossip Stone'),
    0x0419: GossipStone('GC (Medigoron)',                   'GC Medigoron Gossip Stone'),
    0x040A: GossipStone('Graveyard (Shadow Temple)',        'Graveyard Gossip Stone'),
    0x0412: GossipStone('HC (Malon)',                       'HC Malon Gossip Stone'),
    0x040B: GossipStone('HC (Rock Wall)',                   'HC Rock Wall Gossip Stone'),
    0x0413: GossipStone('HC (Storms Grotto)',               'HC Storms Grotto Gossip Stone'),
    0x041F: GossipStone('KF (Deku Tree Left)',              'KF Deku Tree Gossip Stone (Left)'),
    0x0420: GossipStone('KF (Deku Tree Right)',             'KF Deku Tree Gossip Stone (Right)'),
    0x041E: GossipStone('KF (Outside Storms)',              'KF Gossip Stone'),
    0x0403: GossipStone('LH (Lab)',                         'LH Lab Gossip Stone'),
    0x040F: GossipStone('LH (Southeast Corner)',            'LH Gossip Stone (Southeast)'),
    0x0408: GossipStone('LH (Southwest Corner)',            'LH Gossip Stone (Southwest)'),
    0x041D: GossipStone('LW (Bridge)',                      'LW Gossip Stone'),
    0x0416: GossipStone('SFM (Maze Lower)',                 'SFM Maze Gossip Stone (Lower)'),
    0x0417: GossipStone('SFM (Maze Upper)',                 'SFM Maze Gossip Stone (Upper)'),
    0x041C: GossipStone('SFM (Saria)',                      'SFM Saria Gossip Stone'),
    0x0406: GossipStone('ToT (Left)',                       'ToT Gossip Stone (Left)'),
    0x0407: GossipStone('ToT (Left-Center)',                'ToT Gossip Stone (Left-Center)'),
    0x0410: GossipStone('ToT (Right)',                      'ToT Gossip Stone (Right)'),
    0x040E: GossipStone('ToT (Right-Center)',               'ToT Gossip Stone (Right-Center)'),
    0x0409: GossipStone('ZD (Mweep)',                       'ZD Gossip Stone'),
    0x0401: GossipStone('ZF (Fairy)',                       'ZF Fairy Gossip Stone'),
    0x0402: GossipStone('ZF (Jabu)',                        'ZF Jabu Gossip Stone'),
    0x040D: GossipStone('ZR (Near Grottos)',                'ZR Near Grottos Gossip Stone'),
    0x040C: GossipStone('ZR (Near Domain)',                 'ZR Near Domain Gossip Stone'),
    0x041B: GossipStone('HF (Cow Grotto)',                  'HF Cow Grotto Gossip Stone'),

    0x0430: GossipStone('HF (Near Market Grotto)',          'HF Near Market Grotto Gossip Stone'),
    0x0432: GossipStone('HF (Southeast Grotto)',            'HF Southeast Grotto Gossip Stone'),
    0x0433: GossipStone('HF (Open Grotto)',                 'HF Open Grotto Gossip Stone'),
    0x0438: GossipStone('Kak (Open Grotto)',                'Kak Open Grotto Gossip Stone'),
    0x0439: GossipStone('ZR (Open Grotto)',                 'ZR Open Grotto Gossip Stone'),
    0x043C: GossipStone('KF (Storms Grotto)',               'KF Storms Grotto Gossip Stone'),
    0x0444: GossipStone('LW (Near Shortcuts Grotto)',       'LW Near Shortcuts Grotto Gossip Stone'),
    0x0447: GossipStone('DMT (Storms Grotto)',              'DMT Storms Grotto Gossip Stone'),
    0x044A: GossipStone('DMC (Upper Grotto)',               'DMC Upper Grotto Gossip Stone'),
}

gossipLocations_reversemap = {
    stone.name : stone_id for stone_id, stone in gossipLocations.items()
}

def has_eng(text):
    if text is None:
        return False
    return re.search(r'[a-z]+', text) is not None
    
reject_end = ("たたえて","と","により")
def loctextJ(text, mode = 0):
    location_text_J = None
    if not (has_eng(text)):
        location_text_J = text
    elif has_eng(text) or has_eng(location_text_J):
        for region, (opt, clear, type) in HT.items():
            if ((clear == text) is True and not(has_eng(clear))):
                location_text_J = clear
                break
            if ((text in opt) is True and (opt == text) is False and not (has_eng(opt[opt.find(text)]))):
                if len(opt[opt.find(text)]) == 1:
                    location_text_J = opt
                    if (int(len(location_text_J)) - int(location_text_J.find("は"))) < 2 and int(location_text_J.find("は")) != 0:
                        count = location_text_J.rfind('は')
                        list_loc = list(location_text_J)
                        list_loc[count] = ""
                        location_text_J = "".join(list_loc)
                    break
                else:
                    location_text_J = opt[opt.find(text)]
                    break
            if ((opt == text) is True and (has_eng(opt)) == False):
                location_text_J = opt
                break
        if location_text_J is None:
            raise TypeError('%s' % text)

    if has_eng(location_text_J):
        return loctextJ(location_text_J)
    counts = int(location_text_J.rfind('は'))
    if (int(len(location_text_J) - counts) > 2) or ((int(len(location_text_J)) - counts) is ((int(len(location_text_J)) + 1))):
        if location_text_J.endswith(reject_end):
            pass
        else:
            location_text_J = location_text_J + "は"
    else:
        pass
    if mode == 1:
        counta = location_text_J.rfind('は')
        list_locx = list(location_text_J)
        if (len(location_text_J) - counta) < 2:
            list_locx[counta] = ""
            location_text_J = "".join(list_locx)
    return location_text_J
    
def getItemGenericName(item):
    if item.unshuffled_dungeon_item:
        return item.type
    else:
        return item.name


def isRestrictedDungeonItem(dungeon, item):
    if (item.map or item.compass) and dungeon.world.settings.shuffle_mapcompass == 'dungeon':
        return item in dungeon.dungeon_items
    if item.type == 'SmallKey' and dungeon.world.settings.shuffle_smallkeys == 'dungeon':
        return item in dungeon.small_keys
    if item.type == 'BossKey' and dungeon.world.settings.shuffle_bosskeys == 'dungeon':
        return item in dungeon.boss_key
    if item.type == 'GanonBossKey' and dungeon.world.settings.shuffle_ganon_bosskey == 'dungeon':
        return item in dungeon.boss_key
    return False


def add_hint(spoiler, world, groups, gossip_text, count, location=None, force_reachable=False):
    random.shuffle(groups)
    skipped_groups = []
    duplicates = []
    first = True
    success = True
    # early failure if not enough
    if len(groups) < int(count):
        return False
    # Randomly round up, if we have enough groups left
    total = int(random.random() + count) if len(groups) > count else int(count)
    while total:
        if groups:
            group = groups.pop(0)

            if any(map(lambda id: gossipLocations[id].reachable, group)):
                stone_names = [gossipLocations[id].location for id in group]
                stone_locations = [world.get_location(stone_name) for stone_name in stone_names]
                if not first or any(map(lambda stone_location: can_reach_hint(spoiler.worlds, stone_location, location), stone_locations)):
                    if first and location:
                        # just name the event item after the gossip stone directly
                        event_item = None
                        for i, stone_name in enumerate(stone_names):
                            # place the same event item in each location in the group
                            if event_item is None:
                                event_item = MakeEventItem(stone_name, stone_locations[i], event_item)
                            else:
                                MakeEventItem(stone_name, stone_locations[i], event_item)

                        # This mostly guarantees that we don't lock the player out of an item hint
                        # by establishing a (hint -> item) -> hint -> item -> (first hint) loop
                        location.add_rule(world.parser.parse_rule(repr(event_item.name)))

                    total -= 1
                    first = False
                    for id in group:
                        spoiler.hints[world.id][id] = gossip_text
                    # Immediately start choosing duplicates from stones we passed up earlier
                    while duplicates and total:
                        group = duplicates.pop(0)
                        total -= 1
                        for id in group:
                            spoiler.hints[world.id][id] = gossip_text
                else:
                    # Temporarily skip this stone but consider it for duplicates
                    duplicates.append(group)
            else:
                if not force_reachable:
                    # The stones are not readable at all in logic, so we ignore any kind of logic here
                    if not first:
                        total -= 1
                        for id in group:
                            spoiler.hints[world.id][id] = gossip_text
                    else:
                        # Temporarily skip this stone but consider it for duplicates
                        duplicates.append(group)
                else:
                    # If flagged to guarantee reachable, then skip
                    # If no stones are reachable, then this will place nothing
                    skipped_groups.append(group)
        else:
            # Out of groups
            if not force_reachable and len(duplicates) >= total:
                # Didn't find any appropriate stones for this hint, but maybe enough completely unreachable ones.
                # We'd rather not use reachable stones for this.
                unr = [group for group in duplicates if all(map(lambda id: not gossipLocations[id].reachable, group))]
                if len(unr) >= total:
                    duplicates = [group for group in duplicates if group not in unr[:total]]
                    for group in unr[:total]:
                        for id in group:
                            spoiler.hints[world.id][id] = gossip_text
                    # Success
                    break
            # Failure
            success = False
            break
    groups.extend(duplicates)
    groups.extend(skipped_groups)
    return success


def can_reach_hint(worlds, hint_location, location):
    if location == None:
        return True

    old_item = location.item
    location.item = None
    search = Search.max_explore([world.state for world in worlds])
    location.item = old_item

    return (search.spot_access(hint_location)
            and (hint_location.type != 'HintStone' or search.state_list[location.world.id].guarantee_hint()))


def writeGossipStoneHints(spoiler, world, messages):
    for id, gossip_text in spoiler.hints[world.id].items():
        update_message_jp(messages, id, str(gossip_text), 0x23)


def filterTrailingSpace(text):
    if text.endswith('&'):
        return text[:-1]
    else:
        return text


hintPrefixes = [
    'いくつかの',
    '多くの',
    '',
]

def getSimpleHintNoPrefix(item):
    if type(getHint(item.name, True)) != str:
        hint = getHint(item.name, True).text
    elif type(getHint(item.name, True)) == str:
        hint = getHint(item.name, True)
    for prefix in hintPrefixes:
        if hint.startswith(prefix):
            # return without the prefix
            return hint[len(prefix):]

    # no prefex
    return hint


def colorText(gossip_text):
    colorMap = {
        'White':      '\x00',
        'Red':        '\x01',
        'Green':      '\x02',
        'Blue':       '\x03',
        'Light Blue': '\x04',
        'Pink':       '\x05',
        'Yellow':     '\x06',
        'Black':      '\x07',
    }

    text = gossip_text.text
    colors = list(gossip_text.colors) if gossip_text.colors is not None else []
    color = 'White'

    while 'C' in text:
        splitText = text.split('C', 2)
        if len(colors) > 0:
            color = colors.pop()

        for prefix in hintPrefixes:
            if splitText[1].startswith(prefix):
                splitText[0] += splitText[1][:len(prefix)]
                splitText[1] = splitText[1][len(prefix):]
                break

        splitText[1] = '#' + colorMap[color] + splitText[1] + '#\x00'
        text = ''.join(splitText)

    return text


class HintAreaNotFound(RuntimeError):
    pass


# Peforms a breadth first search to find the closest hint area from a given spot (location or entrance)
# May fail to find a hint if the given spot is only accessible from the root and not from any other region with a hint area
def get_hint_area(spot):
    already_checked = []
    spot_queue = [spot]

    while spot_queue:
        current_spot = spot_queue.pop(0)
        already_checked.append(current_spot)

        parent_region = current_spot.parent_region
    
        if parent_region.dungeon:
            return parent_region.dungeon.hint
        elif parent_region.hint and (spot.parent_region.name == 'Root' or parent_region.name != 'Root'):
            return parent_region.hint

        spot_queue.extend(list(filter(lambda ent: ent not in already_checked, parent_region.entrances)))

    raise HintAreaNotFound('%s [World %d]&にヒントはありません' % (spot, spot.world.id))


def get_woth_hint(spoiler, world, checked):
    locations = spoiler.required_locations[world.id]
    locations = list(filter(lambda location:
        location.name not in checked
        and not (world.woth_dungeon >= world.hint_dist_user['dungeons_woth_limit'] and location.parent_region.dungeon)
        and location.name not in world.hint_exclusions
        and location.name not in world.hint_type_overrides['woth']
        and location.item.name not in world.item_hint_type_overrides['woth'],
        locations))

    if not locations:
        return None

    location = random.choice(locations)
    checked.add(location.name)

    if location.parent_region.dungeon:
        world.woth_dungeon += 1
        if type(getHint(location.parent_region.dungeon.name, world.settings.clearer_hints)) != str:
            location_text = getHint(location.parent_region.dungeon.name, world.settings.clearer_hints).text
        else:
            location_text = getHint(location.parent_region.dungeon.name, world.settings.clearer_hints)
    else:
        location_unit = get_hint_area(location)
        if type(getHint(location_unit, world.settings.clearer_hints)) != str:
            location_text = getHint(location_unit, world.settings.clearer_hints).text
        else:
            location_text = getHint(location_unit, world.settings.clearer_hints)
    location_text_J = loctextJ(location_text).replace("には","は")  
    if 'C' not in location_text_J:
        location_text_J = 'C%sC' % location_text_J
    return (GossipText('<%s&勇者への道' % location_text_J, ['Light Blue']), location)

def get_checked_areas(world, checked):
    def get_area_from_name(check):
        try:
            location = world.get_location(check)
        except Exception as e:
            return check
        return get_hint_area(location)

    return set(get_area_from_name(check) for check in checked)

def get_goal_category(spoiler, world, goal_categories):
    cat_sizes = []
    cat_names = []
    zero_weights = True
    goal_category = None
    for cat_name, category in goal_categories.items():
        # Only add weights if the category has goals with hintable items
        if world.id in spoiler.goal_locations and cat_name in spoiler.goal_locations[world.id]:
            # Build lists for weighted choice
            if category.weight > 0:
                zero_weights = False
            cat_sizes.append(category.weight)
            cat_names.append(category.name)
            # Depends on category order to choose next in the priority list
            # Each category is guaranteed a hint first round, then weighted based on goal count
            if not goal_category and category.name not in world.hinted_categories:
                goal_category = category
                world.hinted_categories.append(category.name)

    # random choice if each category has at least one hint
    if not goal_category and len(cat_names) > 0:
        if zero_weights:
            goal_category = goal_categories[random.choice(cat_names)]
        else:
            goal_category = goal_categories[random.choices(cat_names, weights=cat_sizes)[0]]

    return goal_category

def get_goal_hint(spoiler, world, checked):
    goal_category = get_goal_category(spoiler, world, world.goal_categories)

    # check if no goals were generated (and thus no categories available)
    if not goal_category:
        return None

    goals = goal_category.goals
    goal_locations = []

    # Choose random goal and check if any locations are already hinted.
    # If all locations for a goal are hinted, remove the goal from the list and try again.
    # If all locations for all goals are hinted, try remaining goal categories
    # If all locations for all goal categories are hinted, return no hint.
    while not goal_locations:
        if not goals:
            del world.goal_categories[goal_category.name]
            goal_category = get_goal_category(spoiler, world, world.goal_categories)
            if not goal_category:
                return None
            else:
                goals = goal_category.goals

        weights = []
        zero_weights = True
        for goal in goals:
            if goal.weight > 0:
                zero_weights = False
            weights.append(goal.weight)

        if zero_weights:
            goal = random.choice(goals)
        else:
            goal = random.choices(goals, weights=weights)[0]

        goal_locations = list(filter(lambda location:
            location[0].name not in checked
            and location[0].name not in world.hint_exclusions
            and location[0].name not in world.hint_type_overrides['goal']
            and location[0].item.name not in world.item_hint_type_overrides['goal'],
            goal.required_locations))

        if not goal_locations:
            goals.remove(goal)

    # Goal weight to zero mitigates double hinting this goal
    # Once all goals in a category are 0, selection is true random
    goal.weight = 0
    location_tuple = random.choice(goal_locations)
    location = location_tuple[0]
    world_ids = location_tuple[3]
    world_id = random.choice(world_ids)
    checked.add(location.name)

    if location.parent_region.dungeon:
        location_text = getHint(location.parent_region.dungeon.name, world.settings.clearer_hints).text
    else:
        location_unit = get_hint_area(location)
        if type(getHint(location_unit, world.settings.clearer_hints)) != str:
            location_text = getHint(location_unit, world.settings.clearer_hints).text
        else:
            location_text = getHint(location_unit, world.settings.clearer_hints)
    location_text_J = loctextJ(location_text)
    if 'C' not in location_text_J:
        location_text_J = 'C%sC' % location_text_J
    if world_id == world.id:
        goal_text = goal.hint_text
    else:
        goal_text = spoiler.goal_categories[world_id][goal_category.name].get_goal(goal.name).hint_text

    return (GossipText('%s&%s' % (location_text_J, goal_text), [goal.color, 'Light Blue']), location)

def get_barren_hint(spoiler, world, checked):
    if not hasattr(world, 'get_barren_hint_prev'):
        world.get_barren_hint_prev = RegionRestriction.NONE

    areas = list(filter(lambda area:
        area not in checked
        and area not in world.hint_type_overrides['barren']
        and not (world.barren_dungeon >= world.hint_dist_user['dungeons_barren_limit'] and world.empty_areas[area]['dungeon']),
        world.empty_areas.keys()))

    if not areas:
        return None

    # Randomly choose between overworld or dungeon
    dungeon_areas = list(filter(lambda area: world.empty_areas[area]['dungeon'], areas))
    overworld_areas = list(filter(lambda area: not world.empty_areas[area]['dungeon'], areas))
    if not dungeon_areas:
        # no dungeons left, default to overworld
        world.get_barren_hint_prev = RegionRestriction.OVERWORLD
    elif not overworld_areas:
        # no overworld left, default to dungeons
        world.get_barren_hint_prev = RegionRestriction.DUNGEON
    else:
        if world.get_barren_hint_prev == RegionRestriction.NONE:
            # 50/50 draw on the first hint
            world.get_barren_hint_prev = random.choices([RegionRestriction.DUNGEON, RegionRestriction.OVERWORLD], [0.5, 0.5])[0]
        elif world.get_barren_hint_prev == RegionRestriction.DUNGEON:
            # weights 75% against drawing dungeon again
            world.get_barren_hint_prev = random.choices([RegionRestriction.DUNGEON, RegionRestriction.OVERWORLD], [0.25, 0.75])[0]
        elif world.get_barren_hint_prev == RegionRestriction.OVERWORLD:
            # weights 75% against drawing overworld again
            world.get_barren_hint_prev = random.choices([RegionRestriction.DUNGEON, RegionRestriction.OVERWORLD], [0.75, 0.25])[0]

    if world.get_barren_hint_prev == RegionRestriction.DUNGEON:
        areas = dungeon_areas
    else:
        areas = overworld_areas
    if not areas:
        return None

    area_weights = [world.empty_areas[area]['weight'] for area in areas]

    area = random_choices(areas, weights=area_weights)[0]
    if world.empty_areas[area]['dungeon']:
        world.barren_dungeon += 1

    checked.add(area)
    if type(getHint(area, world.settings.clearer_hints)) != str:
        area_text = getHint(area, world.settings.clearer_hints).text
    else:
        area_text = getHint(area, world.settings.clearer_hints)
    area_J = loctextJ(area_text, 1)  
    if 'C' not in area_J:
        area_J = 'C%sC' % area_J
    return (GossipText("<%s&行くことはおろかな選択だ" % area_J, ['Pink']), None)


def is_not_checked(location, checked):
    return not (location.name in checked or get_hint_area(location) in checked)


def get_good_item_hint(spoiler, world, checked):
    locations = list(filter(lambda location:
        is_not_checked(location, checked)
        and (location.item.majoritem
            or location.name in world.added_hint_types['item']
            or location.item.name in world.item_added_hint_types['item'])
        and not location.locked
        and location.name not in world.hint_exclusions
        and location.name not in world.hint_type_overrides['item']
        and location.item.name not in world.item_hint_type_overrides['item'],
        world.get_filled_locations()))
    if not locations:
        return None

    location = random.choice(locations)
    checked.add(location.name)

    item_text = getHint(getItemGenericName(location.item), world.settings.clearer_hints).text
    if location.parent_region.dungeon:
        if type(getHint(location.parent_region.dungeon.name, world.settings.clearer_hints)) != str:
            location_text = getHint(location.parent_region.dungeon.name, world.settings.clearer_hints).text
        else:
            location_text = getHint(location.parent_region.dungeon.name, world.settings.clearer_hints)
        location_text_J = loctextJ(location_text).replace("には","は")  
        if 'C' not in location_text_J:
            location_text_J = 'C%sC' % location_text_J
        return (GossipText('<%s&C%sCを&つかさどる' % (location_text_J, item_text), ['Green', 'Red']), location)
    else:
        location_unit = get_hint_area(location)
        if type(getHint(location_unit, world.settings.clearer_hints)) != str:
            location_text = getHint(location_unit, world.settings.clearer_hints).text
        else:
            location_text = getHint(location_unit, world.settings.clearer_hints)
        location_text_J = loctextJ(location_text).replace("には","は")  
        if 'C' not in location_text_J:
            location_text_J = 'C%sC' % location_text_J
        return (GossipText('<%s&C%sCを&もたらす' % (location_text_J, item_text), ['Green', 'Red']), location)


def get_specific_item_hint(spoiler, world, checked):
    if len(world.named_item_pool) == 0:
        logger = logging.getLogger('')
        logger.info("Named item hint requested, but pool is empty.")
        return None  
    while True:
        itemname = world.named_item_pool.pop(0)
        if itemname == "Bottle" and world.settings.hint_dist == "bingo":
            locations = [
                location for location in world.get_filled_locations()
                if (is_not_checked(location, checked)
                    and location.name not in world.hint_exclusions
                    and location.item.name in bingoBottlesForHints
                    and not location.locked
                    and location.name not in world.hint_type_overrides['named-item'])
            ]
        else:
            locations = [
                location for location in world.get_filled_locations()
                if (is_not_checked(location, checked)
                    and location.name not in world.hint_exclusions
                    and location.item.name == itemname
                    and not location.locked
                    and location.name not in world.hint_type_overrides['named-item'])
            ]
        if len(locations) > 0:
            break
        if len(world.named_item_pool) == 0:
            return None

    location = random.choice(locations)
    checked.add(location.name)
    item_text = getHint(getItemGenericName(location.item), world.settings.clearer_hints).text
    
    if location.parent_region.dungeon:
        if type(getHint(location.parent_region.dungeon.name, world.settings.clearer_hints)) != str:
            location_text = getHint(location.parent_region.dungeon.name, world.settings.clearer_hints).text
        else:
            location_text = getHint(location.parent_region.dungeon.name, world.settings.clearer_hints)
        location_text_J = loctextJ(location_text).replace("には","は")  
        if 'C' not in location_text_J:
            location_text_J = 'C%sC' % location_text_J
        if world.hint_dist_user.get('vague_named_items', False):
            return (GossipText('<%s&勇者への道' % (location_text_J), ['Green']), location)
        else:
            return (GossipText('<%s&C%sCを&つかさどる' % (location_text_J, item_text), ['Green', 'Red']), location)
    else:
        location_unit = get_hint_area(location)
        if type(getHint(location_unit, world.settings.clearer_hints)) != str:
            location_text = getHint(location_unit, world.settings.clearer_hints).text
        else:
            location_text = getHint(location_unit, world.settings.clearer_hints)
        location_text_J = loctextJ(location_text).replace("には","は")  
        if 'C' not in location_text_J:
            location_text_J = 'C%sC' % location_text_J
        if world.hint_dist_user.get('vague_named_items', False):
            return (GossipText('<%s&勇者への道' % (location_text_J), ['Green']), location)
        else:
            return (GossipText('<%s&C%sCを&もたらす' % (location_text_J, item_text), ['Green', 'Red']), location)


def get_random_location_hint(spoiler, world, checked):
    locations = list(filter(lambda location:
        is_not_checked(location, checked)
        and location.item.type not in ('Drop', 'Event', 'Shop', 'DungeonReward')
        and not (location.parent_region.dungeon and isRestrictedDungeonItem(location.parent_region.dungeon, location.item))
        and not location.locked
        and location.name not in world.hint_exclusions
        and location.name not in world.hint_type_overrides['item']
        and location.item.name not in world.item_hint_type_overrides['item'],
        world.get_filled_locations()))
    if not locations:
        return None

    location = random.choice(locations)
    checked.add(location.name)
    dungeon = location.parent_region.dungeon

    item_text = getHint(getItemGenericName(location.item), world.settings.clearer_hints).text
    if dungeon:
        if type(getHint(dungeon.name, world.settings.clearer_hints)) != str:
            location_text = getHint(dungeon.name, world.settings.clearer_hints).text
        else:
            location_text = getHint(dungeon.name, world.settings.clearer_hints)
        location_text_J = loctextJ(location_text).replace("には","は")
        if 'C' not in location_text_J:
            location_text_J = 'C%sC' % location_text_J
        return (GossipText('<%s&C%sCを&つかさどる' % (location_text_J, item_text), ['Green', 'Red']), location)
    else:
        location_unit = get_hint_area(location)
        if type(getHint(location_unit, world.settings.clearer_hints)) != str:
            location_text = getHint(location_unit, world.settings.clearer_hints).text
        else:
            location_text = getHint(location_unit, world.settings.clearer_hints)
        location_text_J = loctextJ(location_text).replace("には","は")  
        if 'C' not in location_text_J:
            location_text_J = 'C%sC' % location_text_J
        return (GossipText('<%s&C%sCを&もたらす' % (location_text_J, item_text), ['Green', 'Red']), location)


def get_specific_hint(spoiler, world, checked, type):
    hintGroup = getHintGroup(type, world)
    hintGroup = list(filter(lambda hint: is_not_checked(world.get_location(hint.name), checked), hintGroup))
    if not hintGroup:
        return None

    hint = random.choice(hintGroup)
    location = world.get_location(hint.name)
    checked.add(location.name)

    if location.name in world.hint_text_overrides:
        location_text = world.hint_text_overrides[location.name]
    else:
        location_text = hint.text
    location_text_J = loctextJ(location_text)
    if 'C' not in location_text_J:
        location_text_J = 'C%sC' % location_text_J
    item_text = getHint(getItemGenericName(location.item), world.settings.clearer_hints).text

    return (GossipText('<%s&C%sC' % (location_text_J, item_text), ['Green', 'Red']), location)


def get_sometimes_hint(spoiler, world, checked):
    return get_specific_hint(spoiler, world, checked, 'sometimes')


def get_song_hint(spoiler, world, checked):
    return get_specific_hint(spoiler, world, checked, 'song')


def get_overworld_hint(spoiler, world, checked):
    return get_specific_hint(spoiler, world, checked, 'overworld')


def get_dungeon_hint(spoiler, world, checked):
    return get_specific_hint(spoiler, world, checked, 'dungeon')


def get_entrance_hint(spoiler, world, checked):
    if not world.entrance_shuffle:
        return None

    entrance_hints = list(filter(lambda hint: hint.name not in checked, getHintGroup('entrance', world)))
    shuffled_entrance_hints = list(filter(lambda entrance_hint: world.get_entrance(entrance_hint.name).shuffled, entrance_hints))

    regions_with_hint = [hint.name for hint in getHintGroup('region', world)]
    valid_entrance_hints = list(filter(lambda entrance_hint:
                                       (world.get_entrance(entrance_hint.name).connected_region.name in regions_with_hint or
                                        world.get_entrance(entrance_hint.name).connected_region.dungeon), shuffled_entrance_hints))

    if not valid_entrance_hints:
        return None

    entrance_hint = random.choice(valid_entrance_hints)
    entrance = world.get_entrance(entrance_hint.name)
    checked.add(entrance.name)

    entrance_text = entrance_hint.text
    

    if 'C' not in entrance_text:
        entrance_text = 'C%sC' % entrance_text

    connected_region = entrance.connected_region
    if connected_region.dungeon:
        if type(getHint(connected_region.dungeon.name, world.settings.clearer_hints)) != str:
            region_text = getHint(connected_region.dungeon.name, world.settings.clearer_hints).text
        else:
            region_text = getHint(connected_region.dungeon.name, world.settings.clearer_hints)
    else:
        if type(getHint(connected_region.name, world.settings.clearer_hints)) != str:
            region_text = getHint(connected_region.name, world.settings.clearer_hints).text
        else:
            region_text = getHint(connected_region.name, world.settings.clearer_hints)

    if 'C' not in region_text:
        region_text = 'C%sC' % region_text

    return (GossipText('<%s&%s' % (entrance_text, region_text), ['Light Blue', 'Green']), None)

   
def get_junk_hint(spoiler, world, checked):
    hints = getHintGroup('junk', world)
    hints = list(filter(lambda hint: hint.name not in checked, hints))
    if not hints:
        return None

    hint = random.choice(hints)
    checked.add(hint.name)

    return (GossipText(hint.text, prefix=''), None)


hint_func = {
    'trial':      lambda spoiler, world, checked: None,
    'always':     lambda spoiler, world, checked: None,
    'woth':             get_woth_hint,
    'goal':             get_goal_hint,
    'barren':           get_barren_hint,
    'item':             get_good_item_hint,
    'sometimes':        get_sometimes_hint,
    'song':             get_song_hint,
    'overworld':        get_overworld_hint,
    'dungeon':          get_dungeon_hint,
    'entrance':         get_entrance_hint,
    'random':           get_random_location_hint,
    'junk':             get_junk_hint,
    'named-item':       get_specific_item_hint
}

hint_dist_keys = {
    'trial',
    'always',
    'woth',
    'goal',
    'barren',
    'item',
    'song',
    'overworld',
    'dungeon',
    'entrance',
    'sometimes',
    'random',
    'junk',
    'named-item'
}


def buildBingoHintList(boardURL):
    try:
        if len(boardURL) > 256:
            raise URLError(f"URL too large {len(boardURL)}")
        with urllib.request.urlopen(boardURL + "/board") as board:
            if board.length and 0 < board.length < 4096:
                goalList = board.read()
            else:
                raise HTTPError(f"Board of invalid size {board.length}")
    except (URLError, HTTPError) as e:
        logger = logging.getLogger('')
        logger.info(f"Could not retrieve board info. Using default bingo hints instead: {e}")
        genericBingo = read_json(data_path('Bingo/generic_bingo_hints.json'))
        return genericBingo['settings']['item_hints']

    # Goal list returned from Bingosync is a sequential list of all of the goals on the bingo board, starting at top-left and moving to the right.
    # Each goal is a dictionary with attributes for name, slot, and colours. The only one we use is the name
    goalList = [goal['name'] for goal in json.loads(goalList)]
    goalHintRequirements = read_json(data_path('Bingo/bingo_goals.json'))

    hintsToAdd = {}
    for goal in goalList:
        # Using 'get' here ensures some level of forward compatibility, where new goals added to randomiser bingo won't
        # cause the generator to crash (though those hints won't have item hints for them)
        requirements = goalHintRequirements.get(goal,{})
        if len(requirements) != 0:
            for item in requirements:
                hintsToAdd[item] = max(hintsToAdd.get(item, 0), requirements[item]['count'])

    # Items to be hinted need to be included in the item_hints list once for each instance you want hinted
    # (e.g. if you want all three strength upgrades to be hintes it needs to be in the list three times)
    hints = []
    for key, value in hintsToAdd.items():
        for _ in range(value):
            hints.append(key)
    if len(hints) == 0:
        raise Exception('No item hints found for goals on Bingosync card. Verify Bingosync URL is correct, or leave field blank for generic bingo hints.')
    return hints



def buildGossipHints(spoiler, worlds):
    checkedLocations = dict()
    # Add Light Arrow locations to "checked" locations if Ganondorf is reachable without it.
    for world in worlds:
        location = world.light_arrow_location
        if location is None:
            continue
        if world.settings.misc_hints and can_reach_hint(worlds, world.get_location("Ganondorf Hint"), location):
            light_arrow_world = location.world
            if light_arrow_world.id not in checkedLocations:
                checkedLocations[light_arrow_world.id] = set()
            checkedLocations[light_arrow_world.id].add(location.name)

    # Build all the hints.
    for world in worlds:
        world.update_useless_areas(spoiler)
        buildWorldGossipHints(spoiler, world, checkedLocations.pop(world.id, None))


# builds out general hints based on location and whether an item is required or not
def buildWorldGossipHints(spoiler, world, checkedLocations=None):

    world.barren_dungeon = 0
    world.woth_dungeon = 0

    search = Search.max_explore([w.state for w in spoiler.worlds])
    for stone in gossipLocations.values():
        stone.reachable = (
            search.spot_access(world.get_location(stone.location))
            and search.state_list[world.id].guarantee_hint())

    if checkedLocations is None:
        checkedLocations = set()

    stoneIDs = list(gossipLocations.keys())

    world.distribution.configure_gossip(spoiler, stoneIDs)

    if 'disabled' in world.hint_dist_user:
        for stone_name in world.hint_dist_user['disabled']:
            try:
                stone_id = gossipLocations_reversemap[stone_name]
            except KeyError:
                raise ValueError(f'Gossip stone location "{stone_name}" is not valid')
            stoneIDs.remove(stone_id)
            (gossip_text, _) = get_junk_hint(spoiler, world, checkedLocations)
            spoiler.hints[world.id][stone_id] = gossip_text

    stoneGroups = []
    if 'groups' in world.hint_dist_user:
        for group_names in world.hint_dist_user['groups']:
            group = []
            for stone_name in group_names:
                try:
                    stone_id = gossipLocations_reversemap[stone_name]
                except KeyError:
                    raise ValueError(f'Gossip stone location "{stone_name}" is not valid')

                stoneIDs.remove(stone_id)
                group.append(stone_id)
            stoneGroups.append(group)
    # put the remaining locations into singleton groups
    stoneGroups.extend([[id] for id in stoneIDs])

    random.shuffle(stoneGroups)

    # Create list of items for which we want hints. If Bingosync URL is supplied, include items specific to that bingo.
    # If not (or if the URL is invalid), use generic bingo hints
    if world.settings.hint_dist == "bingo":
        bingoDefaults = read_json(data_path('Bingo/generic_bingo_hints.json'))
        if world.bingosync_url is not None and world.bingosync_url.startswith("https://bingosync.com/"): # Verify that user actually entered a bingosync URL
            logger = logging.getLogger('')
            logger.info("Got Bingosync URL. Building board-specific goals.")
            world.settings.item_hints = buildBingoHintList(world.bingosync_url)
        else:
            world.settings.item_hints = bingoDefaults['settings']['item_hints']

        if world.settings.tokensanity in ("overworld", "all") and "Suns Song" not in world.settings.item_hints:
            world.settings.item_hints.append("Suns Song")

        if world.settings.shopsanity != "off" and "Progressive Wallet" not in world.settings.item_hints:
            world.settings.item_hints.append("Progressive Wallet")
    #Removes items from item_hints list if they are included in starting gear.
    #This method ensures that the right number of copies are removed, e.g.
    #if you start with one strength and hints call for two, you still get
    #one hint for strength
    for item in itertools.chain(world.settings.starting_items, world.settings.starting_equipment, world.settings.starting_songs):
        itemname = everything[item].itemname
        if itemname in world.item_hints:
            world.item_hints.remove(itemname)

    #Skip_child_zelda can cause the same problem, but needs to be handled separately since
    #it doesn't update the starting gear lists
    if world.settings.skip_child_zelda:
        itemname = world.get_location('Song from Impa').item.name 
        if itemname in world.item_hints:
            world.item_hints.remove(itemname)

    world.named_item_pool = list(world.settings.item_hints)


    # Load hint distro from distribution file or pre-defined settings
    #
    # 'fixed' key is used to mimic the tournament distribution, creating a list of fixed hint types to fill
    # Once the fixed hint type list is exhausted, weighted random choices are taken like all non-tournament sets
    # This diverges from the tournament distribution where leftover stones are filled with sometimes hints (or random if no sometimes locations remain to be hinted)
    sorted_dist = {}
    type_count = 1
    hint_dist = OrderedDict({})
    fixed_hint_types = []
    max_order = 0
    for hint_type in world.hint_dist_user['distribution']:
        if world.hint_dist_user['distribution'][hint_type]['order'] > 0:
            hint_order = int(world.hint_dist_user['distribution'][hint_type]['order'])
            sorted_dist[hint_order] = hint_type
            if max_order < hint_order:
                max_order = hint_order
            type_count = type_count + 1
    if (type_count - 1) < max_order:
        raise Exception("There are gaps in the custom hint orders. Please revise your plando file to remove them.")
    for i in range(1, type_count):
        hint_type = sorted_dist[i]
        if world.hint_dist_user['distribution'][hint_type]['copies'] > 0:
            fixed_num = world.hint_dist_user['distribution'][hint_type]['fixed']
            hint_weight = world.hint_dist_user['distribution'][hint_type]['weight']
        else:
            logging.getLogger('').warning("Hint copies is zero for type %s. Assuming this hint type should be disabled.", hint_type)
            fixed_num = 0
            hint_weight = 0
        hint_dist[hint_type] = (hint_weight, world.hint_dist_user['distribution'][hint_type]['copies'])
        hint_dist.move_to_end(hint_type)
        fixed_hint_types.extend([hint_type] * int(fixed_num))

    hint_types, hint_prob = zip(*hint_dist.items())
    hint_prob, _ = zip(*hint_prob)

    # Add required location hints, only if hint copies > 0
    if hint_dist['always'][1] > 0:
        alwaysLocations = getHintGroup('always', world)
        for hint in alwaysLocations:
            location = world.get_location(hint.name)
            checkedLocations.add(hint.name)
            if location.item.name in bingoBottlesForHints and world.settings.hint_dist == 'bingo':
                always_item = 'Bottle'
            else:
                always_item = location.item.name
            if always_item in world.named_item_pool:
                world.named_item_pool.remove(always_item)

            if location.name in world.hint_text_overrides:
                location_text = world.hint_text_overrides[location.name]
            else:
                location_text = getHint(location.name, world.settings.clearer_hints).text
            location_text_J = loctextJ(location_text)  
            if 'C' not in location_text_J:
                location_text_J = 'C%sC' % location_text_J
            item_text = getHint(getItemGenericName(location.item), world.settings.clearer_hints).text
            add_hint(spoiler, world, stoneGroups, GossipText('<%s&C%sC' % (location_text_J, item_text), ['Green', 'Red']), hint_dist['always'][1], location, force_reachable=True)
            logging.getLogger('').debug('Placed always hint for %s.', location.name)

    trial_translate = [
        ('Light',  '光の力'),
        ('Forest', '森の力'),
        ('Fire',   '炎の力'),
        ('Water',  '水の力'),
        ('Shadow', '闇の力'),
        ('Spirit', '魂の力'),
    ]
    # Add trial hints, only if hint copies > 0
    if hint_dist['trial'][1] > 0:
        if world.settings.trials_random and world.settings.trials == 6:
            add_hint(spoiler, world, stoneGroups, GossipText("<Cガノン城Cは強力な力で&守られている", ['Pink']), hint_dist['trial'][1], force_reachable=True)
        elif world.settings.trials_random and world.settings.trials == 0:
            add_hint(spoiler, world, stoneGroups, GossipText("<シークはCガノン城Cの&バリアを破壊した", ['Yellow']), hint_dist['trial'][1], force_reachable=True)
        elif world.settings.trials < 6 and world.settings.trials > 3:
            for trial,skipped in world.skipped_trials.items():
                trialjp = "どこか"
                if skipped:
                    for (en, jp) in trial_translate:
                        if trial == en:
                            trialjp = jp
                            break
                    add_hint(spoiler, world, stoneGroups,GossipText("<シークはC%sCの&バリアを破壊した" % trialjp, ['Yellow']), hint_dist['trial'][1], force_reachable=True)
        elif world.settings.trials <= 3 and world.settings.trials > 0:
            for trial,skipped in world.skipped_trials.items():
                trialjp = "どこか"
                if not skipped:
                    for (en, jp) in trial_translate:
                        if trial == en:
                            trialjp = jp
                            break
                    add_hint(spoiler, world, stoneGroups, GossipText("<ガノン城はC%sCに&守られている" % trialjp, ['Pink']), hint_dist['trial'][1], force_reachable=True)

    # Add user-specified hinted item locations if using a built-in hint distribution
    # Raise error if hint copies is zero
    if len(world.named_item_pool) > 0 and world.hint_dist_user['named_items_required']:
        if hint_dist['named-item'][1] == 0:
            raise Exception('User-provided item hints were requested, but copies per named-item hint is zero')
        else:
            for i in range(0, len(world.named_item_pool)):
                hint = get_specific_item_hint(spoiler, world, checkedLocations)
                if hint == None:
                    raise Exception('No valid hints for user-provided item')
                else:
                    gossip_text, location = hint
                    place_ok = add_hint(spoiler, world, stoneGroups, gossip_text, hint_dist['named-item'][1], location)
                    if not place_ok:
                        raise Exception('Not enough gossip stones for user-provided item hints')
    
    # Shuffle named items hints
    # When all items are not required to be hinted, this allows for
    # opportunity-style hints to be drawn at random from the defined list.
    random.shuffle(world.named_item_pool)

    hint_types = list(hint_types)
    hint_prob  = list(hint_prob)
    hint_counts = {}

    custom_fixed = True
    while stoneGroups:
        if fixed_hint_types:
            hint_type = fixed_hint_types.pop(0)
            copies = hint_dist[hint_type][1]
            if copies > len(stoneGroups):
                # Quiet to avoid leaking information.
                logging.getLogger('').debug(f'Not enough gossip stone locations ({len(stoneGroups)} groups) for fixed hint type {hint_type} with {copies} copies, proceeding with available stones.')
                copies = len(stoneGroups)
        else:
            custom_fixed = False
            # Make sure there are enough stones left for each hint type
            num_types = len(hint_types)
            hint_types = list(filter(lambda htype: hint_dist[htype][1] <= len(stoneGroups), hint_types))
            new_num_types = len(hint_types)
            if new_num_types == 0:
                raise Exception('Not enough gossip stone locations for remaining weighted hint types.')
            elif new_num_types < num_types:
                hint_prob = []
                for htype in hint_types:
                    hint_prob.append(hint_dist[htype][0])
            try:
                # Weight the probabilities such that hints that are over the expected proportion
                # will be drawn less, and hints that are under will be drawn more.
                # This tightens the variance quite a bit. The variance can be adjusted via the power
                weighted_hint_prob = []
                for w1_type, w1_prob in zip(hint_types, hint_prob):
                    p = w1_prob
                    if p != 0: # If the base prob is 0, then it's 0
                        for w2_type, w2_prob in zip(hint_types, hint_prob):
                            if w2_prob != 0: # If the other prob is 0, then it has no effect
                                # Raising this term to a power greater than 1 will decrease variance
                                # Conversely, a power less than 1 will increase variance
                                p = p * (((hint_counts.get(w2_type, 0) / w2_prob) + 1) / ((hint_counts.get(w1_type, 0) / w1_prob) + 1))
                    weighted_hint_prob.append(p)

                hint_type = random_choices(hint_types, weights=weighted_hint_prob)[0]
                copies = hint_dist[hint_type][1]
            except IndexError:
                raise Exception('Not enough valid hints to fill gossip stone locations.')

        hint = hint_func[hint_type](spoiler, world, checkedLocations)

        if hint == None:
            index = hint_types.index(hint_type)
            hint_prob[index] = 0
            # Zero out the probability in the base distribution in case the probability list is modified
            # to fit hint types in remaining gossip stones
            hint_dist[hint_type] = (0.0, copies)
        else:
            gossip_text, location = hint
            place_ok = add_hint(spoiler, world, stoneGroups, gossip_text, copies, location)
            if place_ok:
                hint_counts[hint_type] = hint_counts.get(hint_type, 0) + 1
                if location is None:
                    logging.getLogger('').debug('Placed %s hint.', hint_type)
                else:
                    logging.getLogger('').debug('Placed %s hint for %s.', hint_type, location.name)
            if not place_ok and custom_fixed:
                logging.getLogger('').debug('Failed to place %s fixed hint for %s.', hint_type, location.name)
                fixed_hint_types.insert(0, hint_type)


# builds text that is displayed at the temple of time altar for child and adult, rewards pulled based off of item in a fixed order.
def buildAltarHints(world, messages, include_rewards=True, include_wincons=True):
    # text that appears at altar as a child.
    child_text = '<'
    if include_rewards:
        bossRewardsSpiritualStones = [
            ('Kokiri Emerald',   'Green'), 
            ('Goron Ruby',       'Red'), 
            ('Zora Sapphire',    'Blue'),
        ]
        child_text += getHint('Spiritual Stone Text Start', world.settings.clearer_hints).text + '^'
        for (reward, color) in bossRewardsSpiritualStones:
            child_text += buildBossString(reward, color, world)
    child_text += getHint('Child Altar Text End', world.settings.clearer_hints).text
    child_text += '{'
    update_message_jp(messages, 0x707A, get_raw_text(child_text), 0x20)

    # text that appears at altar as an adult.
    adult_text = '<'
    adult_text += getHint('Adult Altar Text Start', world.settings.clearer_hints).text + '^'
    if include_rewards:
        bossRewardsMedallions = [
            ('Light Medallion',  'Light Blue'),
            ('Forest Medallion', 'Green'),
            ('Fire Medallion',   'Red'),
            ('Water Medallion',  'Blue'),
            ('Shadow Medallion', 'Pink'),
            ('Spirit Medallion', 'Yellow'),
        ]
        for (reward, color) in bossRewardsMedallions:
            adult_text += buildBossString(reward, color, world)
    if include_wincons:
        adult_text += buildBridgeReqsString(world)
        adult_text += '^'
        adult_text += buildGanonBossKeyString(world)
    else:
        adult_text += getHint('Adult Altar Text End', world.settings.clearer_hints).text
    adult_text += '{'
    update_message_jp(messages, 0x7057, get_raw_text(adult_text), 0x20)


# pulls text string from hintlist for reward after sending the location to hintlist.
def buildBossString(reward, color, world):
    for location in world.get_filled_locations():
        if location.item.name == reward:
            item_icon = chr(location.item.special['item_id'])
            
            if type(getHint(location.name, world.settings.clearer_hints)) != str:
                location_text = getHint(location.name, world.settings.clearer_hints).text
            else:
                location_text = getHint(location.name, world.settings.clearer_hints)
            location_text_J = loctextJ(location_text)  
            if 'C' not in location_text_J:
                location_text_J = 'C%sC' % location_text_J
            return str(GossipText("<~%s%s" % (item_icon, location_text_J), [color], prefix='')) + '^'
    return ''


def buildBridgeReqsString(world):
    string = "<~\x12" # Light Arrow Icon
    if world.settings.bridge == 'open':
        string += "賢者たちはCガノン城Cへの&橋をすでにかけた。"
    else:
        item_req_string = getHint('bridge_' + world.settings.bridge, world.settings.clearer_hints).text
        if world.settings.bridge == 'medallions':
            item_req_string = str(world.settings.bridge_medallions).translate(str.maketrans({chr(0x0021 + i): chr(0xFF01 + i) for i in range(94)})) + '個の' + item_req_string
        elif world.settings.bridge == 'stones':
            item_req_string = str(world.settings.bridge_stones).translate(str.maketrans({chr(0x0021 + i): chr(0xFF01 + i) for i in range(94)})) + '個の' +item_req_string
        elif world.settings.bridge == 'dungeons':
            item_req_string = str(world.settings.bridge_rewards).translate(str.maketrans({chr(0x0021 + i): chr(0xFF01 + i) for i in range(94)})) + 'つの' +item_req_string
        elif world.settings.bridge == 'tokens':
            item_req_string = str(world.settings.bridge_tokens).translate(str.maketrans({chr(0x0021 + i): chr(0xFF01 + i) for i in range(94)})) + '個の' +item_req_string
        if '#' not in item_req_string:
            item_req_string = 'C%sC' % item_req_string
        string += "賢者たちは勇者が&%sを&集めるのを待っている。" % item_req_string
    return str(GossipText(string, ['Green'], prefix=''))


def buildGanonBossKeyString(world):
    string = "<~\x74" # Boss Key Icon
    if world.settings.shuffle_ganon_bosskey == 'remove':
        string += "#\x01心　悪しき者#\x00への扉は&C開かれているC。"
    else:
        if world.settings.shuffle_ganon_bosskey == 'on_lacs':
            item_req_string = getHint('lacs_' + world.settings.lacs_condition, world.settings.clearer_hints).text
            if world.settings.lacs_condition == 'medallions':
                item_req_string = str(world.settings.lacs_medallions).translate(str.maketrans({chr(0x0021 + i): chr(0xFF01 + i) for i in range(94)})) + '個の' +item_req_string
            elif world.settings.lacs_condition == 'stones':
                item_req_string = str(world.settings.lacs_stones).translate(str.maketrans({chr(0x0021 + i): chr(0xFF01 + i) for i in range(94)})) + '個の' +item_req_string
            elif world.settings.lacs_condition == 'dungeons':
                item_req_string = str(world.settings.lacs_rewards).translate(str.maketrans({chr(0x0021 + i): chr(0xFF01 + i) for i in range(94)})) + 'つの' +item_req_string
            elif world.settings.lacs_condition == 'tokens':
                item_req_string = str(world.settings.lacs_tokens).translate(str.maketrans({chr(0x0021 + i): chr(0xFF01 + i) for i in range(94)})) + '個の' +item_req_string
            if 'C' not in item_req_string:
                item_req_string = 'C%sC' % item_req_string
            bk_location_string = "%s&することで開かれる" % item_req_string
        elif world.settings.shuffle_ganon_bosskey in ['stones', 'medallions', 'dungeons', 'tokens']:
            item_req_string = getHint('ganonBK_' + world.settings.shuffle_ganon_bosskey, world.settings.clearer_hints).text
            if world.settings.shuffle_ganon_bosskey == 'medallions':
                item_req_string = str(world.settings.ganon_bosskey_medallions).translate(str.maketrans({chr(0x0021 + i): chr(0xFF01 + i) for i in range(94)})) + '個の' +item_req_string
            elif world.settings.shuffle_ganon_bosskey == 'stones':
                item_req_string = str(world.settings.ganon_bosskey_stones).translate(str.maketrans({chr(0x0021 + i): chr(0xFF01 + i) for i in range(94)})) + '個の' +item_req_string
            elif world.settings.shuffle_ganon_bosskey == 'dungeons':
                item_req_string = str(world.settings.ganon_bosskey_rewards).translate(str.maketrans({chr(0x0021 + i): chr(0xFF01 + i) for i in range(94)})) + 'つの' +item_req_string
            elif world.settings.shuffle_ganon_bosskey == 'tokens':
                item_req_string = str(world.settings.ganon_bosskey_tokens).translate(str.maketrans({chr(0x0021 + i): chr(0xFF01 + i) for i in range(94)})) + '個の' +item_req_string
            if 'C' not in item_req_string:
                item_req_string = 'C%sC' % item_req_string
            bk_location_string = "%s&することで開かれる" % item_req_string
        else:
            bk_location_string = getHint('ganonBK_' + world.settings.shuffle_ganon_bosskey, world.settings.clearer_hints).text
        string += "#\x01心　悪しき者#\x00への扉は&%s。" % bk_location_string
    return str(GossipText(string, ['Yellow'], prefix=''))


# fun new lines for Ganon during the final battle
def buildGanonText(world, messages):
    # empty now unused messages to make space for ganon lines
    update_message_jp(messages, 0x70C8, "　")
    update_message_jp(messages, 0x70C9, "　")
    update_message_jp(messages, 0x70CA, "　")

    # lines before battle
    ganonLines = getHintGroup('ganonLine', world)
    random.shuffle(ganonLines)
    text = get_raw_text(ganonLines.pop().text)
    update_message_jp(messages, 0x70CB, text)

    # light arrow hint or validation chest item
    if world.distribution.get_starting_item('Light Arrows') > 0:
        text = get_raw_text(getHint('Light Arrow Location', world.settings.clearer_hints).text)
        text += "#\x02手元#\x00にある"
    elif world.light_arrow_location:
        text = get_raw_text(getHint('Light Arrow Location', world.settings.clearer_hints).text)
        location = world.light_arrow_location
        location_unit = get_hint_area(location)
        if type(getHint(location_unit, world.settings.clearer_hints)) != str:
            location_hint = getHint(location_unit, world.settings.clearer_hints).text
        else:
            location_hint = getHint(location_unit, world.settings.clearer_hints)
        location_hint_J = loctextJ(location_hint) 
        if 'C' in location_hint_J:
            location_hint_J = location_hint_J.replace('C', '')        
        if world.id != location.world.id:
            text += "#\x02%s#\x00" % (get_raw_text(location_hint_J))
        else:
            location_hint = location_hint_J.replace('ガノン城', '私の城')
            text += get_raw_text(location_hint_J)
        text += "にある"
    else:
        text = get_raw_text(getHint('Validation Line', world.settings.clearer_hints).text)
        for location in world.get_filled_locations():
            if location.name == 'Ganons Tower Boss Key Chest':
                text += get_raw_text(getHint(getItemGenericName(location.item), world.settings.clearer_hints).text)
                break
    text += '&#\x06矢#\x00無しでは不可能！'

    update_message_jp(messages, 0x70CC, text)


def get_raw_text(string):
    text = ''
    for char in string:
        if char == '^':
            text += '^' # box break
        elif char == '&':
            text += '&' # new line
        elif char == '@':
            text += '@N' # print player name
        elif char == '#':
            text += '#' # sets color to white
        else:
            text += char
    return text


def HintDistFiles():
    return [os.path.join(data_path('Hints/'), d) for d in defaultHintDists] + [
            os.path.join(data_path('Hints/'), d)
            for d in sorted(os.listdir(data_path('Hints/')))
            if d.endswith('.json') and d not in defaultHintDists]


def HintDistList():
    dists = {}
    for d in HintDistFiles():
        dist = read_json(d)
        dist_name = dist['name']
        gui_name = dist['gui_name']
        dists.update({ dist_name: gui_name })
    return dists


def HintDistTips():
    tips = ""
    first_dist = True
    line_char_limit = 33
    for d in HintDistFiles():
        if not first_dist:
            tips = tips + "\n"
        else:
            first_dist = False
        dist = read_json(d)
        gui_name = dist['gui_name']
        desc = dist['description']
        i = 0
        end_of_line = False
        tips = tips + "<b>"
        for c in gui_name:
            if c == " " and end_of_line:
                tips = tips + "\n"
                end_of_line = False
            else:
                tips = tips + c
                i = i + 1
                if i > line_char_limit:
                    end_of_line = True
                    i = 0
        tips = tips + "</b>: "
        i = i + 2
        for c in desc:
            if c == " " and end_of_line:
                tips = tips + "\n"
                end_of_line = False
            else:
                tips = tips + c
                i = i + 1
                if i > line_char_limit:
                    end_of_line = True
                    i = 0
        tips = tips + "\n"
    return tips
