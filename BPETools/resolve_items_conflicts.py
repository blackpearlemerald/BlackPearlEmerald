import re

with open('BPE Emerald V1.0.1/pokeemerald-expansion/src/data/items.h', 'r', newline='') as f:
    content = f.read()

# Normalize to LF for processing
content = content.replace('\r\n', '\n')

CONFLICT_RE = re.compile(
    r'<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> expansion/1\.13\.4\n',
    re.DOTALL
)

def resolve(m):
    head = m.group(1)
    upstream = m.group(2)

    h_has_name = '.name = _(' in head or '.pluralName = _(' in head
    u_has_name = 'ITEM_NAME(' in upstream or 'ITEM_PLURAL_NAME(' in upstream
    h_has_price = '.price = ' in head
    u_has_price = '.price = ' in upstream
    h_has_secondary = '.secondaryId = ' in head

    # Case 1: Name + Price conflict
    # Use upstream ITEM_NAME format; keep BPE price = 0
    if h_has_name and u_has_name:
        # Replace _("X") with ITEM_NAME("X") in head
        result = head
        # Replace .name = _("...") with .name = ITEM_NAME("...")
        result = re.sub(r'\.name = _\("(.*?)"\)', r'.name = ITEM_NAME("\1")', result)
        result = re.sub(r'\.pluralName = _\("(.*?)"\)', r'.pluralName = ITEM_PLURAL_NAME("\1")', result)
        # Keep BPE price (already in head), drop upstream price
        return result

    # Case 2: secondaryId in head, upstream is empty or has content
    if h_has_secondary and not u_has_name and not u_has_price:
        if upstream.strip() == '':
            # BPE added secondaryId, upstream removed it - keep BPE's
            return head
        else:
            # BPE adds secondaryId to current item; upstream also adds new items
            # Keep BPE's secondaryId AND upstream's new content
            return head + upstream

    # Case 3: Fallback - take upstream if it's clearly better (has ITEM_NAME)
    if u_has_name and not h_has_name:
        return upstream

    # Default: keep HEAD
    print(f'UNHANDLED CONFLICT:\n  HEAD: {repr(head[:80])}\n  UPS: {repr(upstream[:80])}')
    return head

result = CONFLICT_RE.sub(resolve, content)

# Verify no conflicts remain
remaining = result.count('<<<<<<< HEAD')
print(f'Remaining conflicts: {remaining}')

# Write back with CRLF
with open('BPE Emerald V1.0.1/pokeemerald-expansion/src/data/items.h', 'w', newline='') as f:
    f.write(result.replace('\n', '\r\n'))

print('Done.')
