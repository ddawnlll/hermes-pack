import re
with open(r'C:\Users\dresden\Documents\praxis\packages\kernel\src\evidence\types.ts', encoding='utf-8') as f:
    content = f.read()

# Find EVIDENCE_VERSION_V01
m = re.search(r'export const EVIDENCE_VERSION_V01\s*=\s*[\'"]([^\'"]+)[\'"]', content)
if m: 
    print(f'EVIDENCE_VERSION_V01 = {m.group(1)}')
else:
    print('EVIDENCE_VERSION_V01 not found')
    # Try looking for the value
    for line in content.split('\n'):
        if 'EVIDENCE_VERSION' in line:
            print(f'  {line.strip()}')

# Find EvidenceRecordV01 fields
m2 = re.search(r'export interface EvidenceRecordV01\s*\{([^}]+)\}', content, re.DOTALL)
if m2:
    block = m2.group(1)
    for line in block.split('\n'):
        line = line.strip()
        if line and not line.startswith('/') and not line.startswith('*'):
            print(f'Field: {line}')
