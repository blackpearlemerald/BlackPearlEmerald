import re

with open('BPE Emerald V1.0.1/pokeemerald-expansion/src/data/items.h', 'r', newline='') as f:
    content = f.read()

content = content.replace('\r\n', '\n')

# Find all item designators and their positions
# Pattern: [ITEM_XXX] =
designator_re = re.compile(r'\n    \[ITEM_\w+\] =\n    \{')
matches = list(designator_re.finditer(content))

# Extract item names and find duplicates
item_positions = {}
duplicates = []
for m in matches:
    name_match = re.search(r'\[(\w+)\]', m.group())
    if name_match:
        name = name_match.group(1)
        if name in item_positions:
            duplicates.append((name, item_positions[name], m.start()))
        else:
            item_positions[name] = m.start()

print(f'Found {len(duplicates)} duplicate item definitions:')
for name, first, second in duplicates:
    print(f'  {name}: first at {first}, second at {second}')

if not duplicates:
    print('No duplicates found.')
else:
    # Remove the later (second) occurrences
    # We need to remove each duplicate block: from '[ITEM_X] = {' to the matching '}'
    # Sort by position in reverse order so we can remove from the end
    duplicates_to_remove = sorted([(second, name) for name, first, second in duplicates], reverse=True)

    for pos, name in duplicates_to_remove:
        # Find the start of this item block (the newline before the designator)
        # Find the matching closing brace
        # The block starts at 'pos' and goes until we find '},' or '};\n' at the item level
        # Find the end: look for the next designator or end of array

        # pos is at '\n    [ITEM_X] =\n    {'
        # We need to find the end of this item's definition
        # Count braces from '{'
        start = pos
        # Find the opening {
        open_brace = content.index('{', pos + 1)
        depth = 0
        i = open_brace
        while i < len(content):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    # Found the matching close
                    end = i + 1
                    # Skip trailing comma if present
                    if end < len(content) and content[end] == ',':
                        end += 1
                    # Skip trailing newline(s)
                    while end < len(content) and content[end] == '\n':
                        end += 1
                    break
            i += 1

        removed_block = content[start:end]
        print(f'\nRemoving duplicate [{name}] at pos {start}:')
        print(repr(removed_block[:80]))
        content = content[:start] + content[end:]

    # Verify no more duplicates
    matches2 = list(designator_re.finditer(content))
    item_positions2 = {}
    remaining_dups = 0
    for m in matches2:
        name_match = re.search(r'\[(\w+)\]', m.group())
        if name_match:
            name = name_match.group(1)
            if name in item_positions2:
                remaining_dups += 1
            else:
                item_positions2[name] = m.start()
    print(f'\nRemaining duplicates: {remaining_dups}')

with open('BPE Emerald V1.0.1/pokeemerald-expansion/src/data/items.h', 'w', newline='') as f:
    f.write(content.replace('\n', '\r\n'))

print('Done.')
