import re
with open(r'C:\Users\dresden\Documents\hermes-pack\.praxis\runs\evidence.jsonl', encoding='utf-8') as f:
    content = f.read()

# Fix type "file" -> "source"
content = content.replace('"type":"file"', '"type":"source"')

with open(r'C:\Users\dresden\Documents\hermes-pack\.praxis\runs\evidence.jsonl', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed evidence type')
