import re
data = open(r'C:\Users\dresden\AppData\Roaming\npm\node_modules\@praxis\cli\dist\cli.js').read()
# Find ALL require paths
paths = set()
for m in re.finditer(r'require\(["\']([^"\']+)["\']\)', data):
    paths.add(m.group(1))
for p in sorted(paths):
    print(p)
