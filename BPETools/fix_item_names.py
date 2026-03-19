import re

with open('BPE Emerald V1.0.1/pokeemerald-expansion/src/data/items.h', 'r', newline='') as f:
    content = f.read()

content = content.replace('\r\n', '\n')

# Replace .name = _("...") with .name = ITEM_NAME("...")
content = re.sub(r'(\.name\s*=\s*)_\("(.*?)"\)', r'\1ITEM_NAME("\2")', content)
# Replace .pluralName = _("...") with .pluralName = ITEM_PLURAL_NAME("...")
content = re.sub(r'(\.pluralName\s*=\s*)_\("(.*?)"\)', r'\1ITEM_PLURAL_NAME("\2")', content)

remaining = len(re.findall(r'\.name = _\(|\.pluralName = _\(', content))
print(f'Remaining _() name/pluralName uses: {remaining}')

with open('BPE Emerald V1.0.1/pokeemerald-expansion/src/data/items.h', 'w', newline='') as f:
    f.write(content.replace('\n', '\r\n'))

print('Done.')
