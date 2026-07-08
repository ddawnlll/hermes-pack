import yaml, json
with open(r'C:\Users\dresden\Documents\hermes-pack\schemas\planspec.v0.1.schema.yaml', encoding='utf-8') as f:
    schema = yaml.safe_load(f)

props = schema.get('properties', {})

# Find executor enum
auth = props.get('authority', {}).get('properties', {})
executor = auth.get('executor', {})
print('Executor allowed:', json.dumps(executor.get('enum', 'not found')))

# Agent enum
exec_props = props.get('execution', {}).get('properties', {})
agent = exec_props.get('agent', {})
print('Agent allowed:', json.dumps(agent.get('enum', 'not found')))

# verification type enum
tasks = props.get('tasks', {}).get('items', {}).get('properties', {})
ac = tasks.get('acceptanceCriteria', {}).get('items', {})
ac_props = ac.get('properties', {})
print('AC required:', json.dumps(ac.get('required', [])))
verification = ac_props.get('verification', {}).get('properties', {})
print('verification properties:', json.dumps(list(verification.keys())))
print('verification type enum:', json.dumps(verification.get('type', {}).get('enum', 'not found')))
evid_refs = verification.get('evidenceRefs', {})
print('evidenceRefs type:', evid_refs.get('type'))
print('evidenceRefs items enum:', json.dumps(evid_refs.get('items', {}).get('enum', 'not found')))

# Evidence required items
required_evidence = ac_props.get('requiredEvidence', {})
print('requiredEvidence type:', required_evidence.get('type'))
print('requiredEvidence items enum:', json.dumps(required_evidence.get('items', {}).get('enum', 'not found')))

# Gates reasonCodes
gates_props = props.get('gates', {}).get('properties', {})
reason_codes = gates_props.get('reasonCodes', {})
print('reasonCodes type:', reason_codes.get('type'))
print('reasonCodes additionalProperties type:', reason_codes.get('additionalProperties', {}).get('type'))
