import yaml
with open(r'C:\Users\dresden\Documents\hermes-pack\schemas\planspec.v0.1.schema.yaml', encoding='utf-8') as f:
    s = yaml.safe_load(f)

defs = s.get('$defs', {})
# Find the evidence record definition
for k, v in defs.items():
    if 'evidence' in k.lower() and isinstance(v, dict) and 'properties' in v:
        print(f'=== {k} ===')
        req = v.get('required', [])
        props = v.get('properties', {})
        for pk, pv in props.items():
            ref = pv.get('$ref', '')
            if ref:
                rk = ref.replace('#/$defs/', '')
                ro = defs.get(rk, {})
                print(f'  {pk}: type={ro.get("type","")} enum={ro.get("enum","")} required={pk in req}')
            else:
                ptype = pv.get('type', pv.get('oneOf', pv.get('anyOf', '')))
                print(f'  {pk}: type={ptype} enum={pv.get("enum","")} required={pk in req}')
