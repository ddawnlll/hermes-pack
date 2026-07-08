import re
with open(r'C:\Users\dresden\Documents\hermes-pack\.praxis\runs\evidence.jsonl', encoding='utf-8') as f:
    content = f.read()

# Fix recordId pattern: evt- -> EV-
content = re.sub(r'"recordId":"evt-', '"recordId":"EV-', content)

with open(r'C:\Users\dresden\Documents\hermes-pack\.praxis\runs\evidence.jsonl', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed record IDs')
