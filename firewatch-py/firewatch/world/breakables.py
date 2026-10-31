"""What can be broken in the game, with what, and what it gives.

Objects and foliage groups carry a 'breakable' record (edited in the editor):
  enabled  bool
  tool     'axe' (needs an axe), 'any' (any tool, or bare hands) or 'hands' (bare hands only)
  hits     hits of damage 1 to break it (an axe's damage setting makes each swing count more)
  drops    [{'item': name, 'count': n}, ...] added to the player's inventory when it breaks

Breaking lasts for the play session: the save is never changed by playing.
"""
TOOLS = ('axe', 'any', 'hands')
TOOL_LABELS = ('Axe', 'Any tool or hands', 'Bare hands')


def new_breakable(enabled=False, tool='axe', hits=3, drops=None):
    return {'enabled': bool(enabled), 'tool': tool, 'hits': float(hits),
            'drops': drops if drops is not None else [{'item': 'wood', 'count': 3}, {'item': '', 'count': 0}]}


def default_breakable(model):
    """Trees break with an axe into wood; everything else starts unbreakable."""
    name = model.lower().rsplit('/', 1)[-1]
    if 'tree' in name and 'bush' not in name:
        return new_breakable(True, 'axe', 4, [{'item': 'wood', 'count': 3}, {'item': '', 'count': 0}])
    if 'bush' in name:
        return new_breakable(False, 'any', 2, [{'item': 'branch', 'count': 2}, {'item': 'berries', 'count': 3}])
    return new_breakable(False)


def accepts(breakable, held_type):
    """Can something with this record be damaged by the held item type (None = bare hands)?"""
    if not breakable.get('enabled'):
        return False
    tool = breakable.get('tool', 'axe')
    if tool == 'axe':
        return held_type == 'axe'
    if tool == 'hands':
        return held_type is None
    return True


def drops(breakable):
    return [(drop['item'].strip(), int(drop['count'])) for drop in breakable.get('drops', [])
            if drop.get('item', '').strip() and int(drop.get('count', 0)) > 0]
