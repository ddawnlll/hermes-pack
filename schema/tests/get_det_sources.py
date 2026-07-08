with open(r'C:\Users\dresden\Documents\praxis\packages\kernel\src\evidence\types.ts', encoding='utf-8') as f:
    content = f.read()
in_det = False
for line in content.split('\n'):
    if 'DETERMINISTIC_SOURCES' in line:
        in_det = True
    elif 'WEAK_SOURCES' in line and in_det:
        in_det = False
    elif in_det and line.strip():
        print(line.strip())
