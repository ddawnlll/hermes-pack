import re
data = open(r'C:\Users\dresden\AppData\Roaming\npm\node_modules\@praxis\cli\dist\cli.js').read()
for m in re.finditer(r'require\(["\']([^"\']+)["\']\)', data):
    path = m.group(1)
    if 'diagnostic' in path.lower() or 'kernel' in path.lower():
        print(path)
