"""Check what lock modes are supported by the kernel."""
import os, re
for root, dirs, files in os.walk(r'C:\Users\dresden\Documents\praxis\packages\kernel\src\lock'):
    for f in files:
        if f.endswith('.ts'):
            path = os.path.join(root, f)
            with open(path, encoding='utf-8') as fh:
                content = fh.read()
            print(f'=== {f} ===')
            # Find LockMode or lock mode references
            for line in content.split('\n'):
                stripped = line.strip()
                if 'LockMode' in stripped or 'lockMode' in stripped.lower() or 'create_if_missing' in stripped or 'overwrite' in stripped.lower():
                    print(f'  {stripped[:150]}')
            # Find the function signature and params
            for i, line in enumerate(content.split('\n'), 1):
                if 'export function' in line or 'export interface Lock' in line:
                    print(f'  L{i}: {line.strip()[:200]}')
                if 'LockGateInput' in line or 'LockGateParams' in line:
                    print(f'  L{i}: {line.strip()[:200]}')

# Also check the index.ts re-exports
with open(r'C:\Users\dresden\Documents\praxis\packages\kernel\src\index.ts', encoding='utf-8') as f:
    content = f.read()
for line in content.split('\n'):
    if 'lock' in line.lower() and ('export' in line or 'Lock' in line):
        print(f'index.ts: {line.strip()[:150]}')
