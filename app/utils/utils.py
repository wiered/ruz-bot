import random

RANDOM_GROUP_NAMES = [
    'ИС222', 
    'ИС221',
    'МС221',
    'МС222',
    'МС223',
    'МС231',
    'МС232',
    'МС233',
    'МС241',
    'МС242',
    'МС243',
    'БИС221',
    'БИС222',
    'БИС231',
    'БИС231',
    'БАС221',
    'БАС231',
    'БАС232',
    'БАС241',
    'БАС242',
    'ЭВМ221',
    'ЭВМб211',
    'ЭВМб212',
    'УВД221',
    'УВД222',
    'УВД231',
    'УВД241',
    ]

def getRandomGroup() -> str:
    """
    Returns a random group name from the RANDOM_GROUP_NAMES list.

    Returns:
        str: A random group name.
    """
    return random.choice(RANDOM_GROUP_NAMES)

def isSubGroupValid(lesson, sub_group):
    if len(list_sub_groups := lesson.get("listSubGroups")) == 0:
        return True
    if sub_group == int(list_sub_groups[0].get("subgroup")[-1]):
        return True
    
    return False

