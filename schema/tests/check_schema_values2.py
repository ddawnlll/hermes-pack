import yaml, json
with open(r'C:\Users\dresden\Documents\hermes-pack\schemas\planspec.v0.1.schema.yaml', encoding='utf-8') as f:
    schema = yaml.safe_load(f)

defs = schema.get('$defs', {})
print('Defs keys:', list(defs.keys()))

# Find executor from authority ref chain
authority = defs.get('authority', {})
if authority:
    props = authority.get('properties', {})
    for k, v in props.items():
        ref = v.get('$ref', '')
        if ref:
            ref_key = ref.replace('#/$defs/', '')
            ref_obj = defs.get(ref_key, {})
            enum = ref_obj.get('enum', [])
            print(f'  {k} -> {ref_key} enum: {json.dumps(enum)}')
        else:
            print(f'  {k}: inline type={v.get("type")}, enum={json.dumps(v.get("enum", "none"))}')

# Execution agent
exec_props = defs.get('execution', {}).get('properties', {})
for k, v in exec_props.items():
    ref = v.get('$ref', '')
    if ref:
        ref_key = ref.replace('#/$defs/', '')
        ref_obj = defs.get(ref_key, {})
        print(f'  exec.{k} -> {ref_key} type={ref_obj.get("type")}, enum={json.dumps(ref_obj.get("enum", "none"))}')

# Acceptance criteria verification
ac = defs.get('acceptanceCriterion', {})
ac_props = ac.get('properties', {})
print('AC props:', list(ac_props.keys()))
for k, v in ac_props.items():
    ref = v.get('$ref', '')
    if ref:
        ref_key = ref.replace('#/$defs/', '')
        ref_obj = defs.get(ref_key, {})
        print(f'  AC.{k} -> {ref_key}: {json.dumps({kk: vv for kk, vv in ref_obj.items() if kk in ["type", "enum", "items", "properties"]}, default=str)}')

# Verification props
ver = defs.get('verification', {})
ver_props = ver.get('properties', {})
print('Verification props:', list(ver_props.keys()))
for k, v in ver_props.items():
    ref = v.get('$ref', '')
    if ref:
        ref_key = ref.replace('#/$defs/', '')
        ref_obj = defs.get(ref_key, {})
        print(f'  Ver.{k} -> {ref_key}: {json.dumps({kk: vv for kk, vv in ref_obj.items() if kk in ["type", "enum", "items"]}, default=str)}')

# Gates 
gates = defs.get('gates', {})
gates_props = gates.get('properties', {})
print('Gates props:', list(gates_props.keys()))
reason_codes = gates_props.get('reasonCodes', {})
ref = reason_codes.get('$ref', '')
if ref:
    ref_key = ref.replace('#/$defs/', '')
    ref_obj = defs.get(ref_key, {})
    print(f'  reasonCodes -> {ref_key}: {json.dumps({kk: vv for kk, vv in ref_obj.items() if kk in ["type", "additionalProperties", "patternProperties"]}, default=str)}')
