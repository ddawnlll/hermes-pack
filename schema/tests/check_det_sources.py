"""Extract the actual source sets from types.ts"""
with open(r'C:\Users\dresden\Documents\praxis\packages\kernel\src\evidence\types.ts', encoding='utf-8') as f:
    content = f.read()

# Find EvidenceSourceV01 type
for i, line in enumerate(content.split('\n'), 1):
    if 'EvidenceSourceV01' in line:
        print(f'L{i}: {line.strip()}')
    if line.strip().startswith("'") and ('test' in line or 'git' in line or 'agent' in line or 'manual' in line or 'runner' in line):
        print(f'L{i}: {line.strip()}')
