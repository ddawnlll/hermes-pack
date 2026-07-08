import re
with open(r'C:\Users\dresden\Documents\praxis\packages\kernel\src\evidence\types.ts', encoding='utf-8') as f:
    content = f.read()

for m in re.finditer(r'DETERMINISTIC_SOURCES.*?\];', content, re.DOTALL):
    print('DETERMINISTIC_SOURCES:')
    for line in m.group(0).split('\n'):
        if 'EvidenceSource' in line or '"' in line:
            print(f'  {line.strip()}')

for m in re.finditer(r'WEAK_SOURCES.*?\];', content, re.DOTALL):
    print('WEAK_SOURCES:')
    for line in m.group(0).split('\n'):
        print(f'  {line.strip()}')
