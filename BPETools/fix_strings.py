import sys
sys.stdout.reconfigure(encoding='utf-8')

f = open(r'E:\Projects\PokemonBlackPearlEmerald\BPE Emerald V1.0.1\pokeemerald-expansion\data\event_scripts.s', 'r', encoding='utf-8', newline='')
content = f.read()
f.close()

start_marker = 'gText_FirstShouldRestoreMonsHealth::'
end_marker = '\ngText_RegisteredTrainerinPokeNav::'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("ERROR: markers not found")
    sys.exit(1)

e = '\u00e9'  # precomposed e-acute (é)
# Use raw strings to avoid escape interpretation
# \n = line break in game, \p = page break, \l = line break (no scroll)
correct = (
    'gText_FirstShouldRestoreMonsHealth::\n'
    '\t.string "First, you should restore your\\n"\n'
    '\t.string "POK' + e + 'MON to full health.$"\n'
    '\n'
    'gText_MonsHealedShouldBuyPotions::\n'
    '\t.string "Your POK' + e + 'MON have been healed\\n"\n'
    '\t.string "to perfect health.\\p"\n'
    '\t.string "If your POK' + e + 'MON\'s energy, HP,\\n"\n'
    '\t.string "is down, please come see us.\\p"\n'
    '\t.string "If you\'re planning to go far in the\\n"\n'
    '\t.string "field, you should buy some POTIONS\\l"\n'
    '\t.string "at the POK' + e + 'MON MART.\\p"\n'
    '\t.string "We hope you excel!$"\n'
    '\n'
    'gText_MonsHealed::\n'
    '\t.string "Your POK' + e + 'MON have been healed\\n"\n'
    '\t.string "to perfect health.\\p"\n'
    '\t.string "We hope you excel!$"\n'
    '\n'
    'gText_HadQuiteAnExperienceTakeRest::\n'
    '\t.string "MOM: {PLAYER}!\\n"\n'
    '\t.string "Welcome home.\\p"\n'
    '\t.string "It sounds like you had quite\\n"\n'
    '\t.string "an experience.\\p"\n'
    '\t.string "Maybe you should take a quick\\n"\n'
    '\t.string "rest.$"\n'
    '\n'
    'gText_MomExplainHPGetPotions::\n'
    '\t.string "MOM: Oh, good! You and your\\n"\n'
    '\t.string "POK' + e + 'MON are looking great.\\p"\n'
    '\t.string "I just heard from PROF. BIRCH.\\p"\n'
    '\t.string "He said that POK' + e + 'MON\'s energy is\\n"\n'
    '\t.string "measured in HP.\\p"\n'
    '\t.string "If your POK' + e + 'MON lose their HP,\\n"\n'
    '\t.string "you can restore them at any\\l"\n'
    '\t.string "POK' + e + 'MON CENTER.\\p"\n'
    '\t.string "If you\'re going to travel far away,\\n"\n'
    '\t.string "the smart TRAINER stocks up on\\l"\n'
    '\t.string "POTIONS at the POK' + e + 'MON MART.\\p"\n'
    '\t.string "Make me proud, honey!\\p"\n'
    '\t.string "Take care!$"\n'
)

# Verify our strings have literal backslash-n (2 chars) not newline (1 char)
test = correct[:correct.find('\\n') + 2]
print(f"Test - backslash-n in string: {'\\\\n' in correct}")
print(f"First 80 chars: {repr(correct[:80])}")

new_content = content[:start_idx] + correct + content[end_idx:]

f = open(r'E:\Projects\PokemonBlackPearlEmerald\BPE Emerald V1.0.1\pokeemerald-expansion\data\event_scripts.s', 'w', encoding='utf-8', newline='')
f.write(new_content)
f.close()
print('Done - wrote file')
