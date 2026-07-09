#!/usr/bin/env python3
import json, os, sys, subprocess, tempfile, shutil

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
PASS = 0
FAIL = 0

def ok(msg):
    global PASS
    PASS += 1
    print('[PASS] ' + msg)

def no(msg):
    global FAIL
    FAIL += 1
    print('[FAIL] ' + msg)

SCRIPT = os.path.join(REPO_ROOT, 'templates', 'scripts', 'ratchet-update.py')

def run_r(ld):
    r = subprocess.run([sys.executable, SCRIPT, ld], capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        return json.loads(r.stdout.strip()), None
    return None, r.stderr

def load_r(ld):
    with open(os.path.join(ld, 'ratchet.json')) as f:
        return json.load(f)

def mk_obj(path, sust, blk):
    with open(path, 'w') as f:
        for i in range(sust):
            f.write(json.dumps({'verdict': 'SUSTAIN', 'tick': i}) + chr(10))
        for i in range(blk):
            f.write(json.dumps({'verdict': 'BLOCK', 'tick': sust + i}) + chr(10))

print('[TEST] ratchet-update.py exists')
if os.path.exists(SCRIPT):
    ok('exists')
else:
    no('NOT found')

print('[TEST] ratchet.json template')
tp = os.path.join(REPO_ROOT, 'templates', 'ratchet.json')
if os.path.exists(tp):
    r = json.load(open(tp))
    for field in ['schema_version', 'level', 'blocking_ratio', 'window_size', 'history']:
        if field in r:
            ok(field + ' present')
        else:
            no(field + ' MISSING')
else:
    no('template NOT found')

print('[TEST] Init creates ratchet.json')
d = tempfile.mkdtemp()
ld = os.path.join(d, 'ledger')
os.makedirs(ld)
out, err = run_r(ld)
if out and out['action'] == 'init':
    ok('init ok')
else:
    no('init failed: ' + str(err))
if os.path.exists(os.path.join(ld, 'ratchet.json')):
    ok('file exists')
else:
    no('file missing')
shutil.rmtree(d)

print('[TEST] Tighten (ratio < 0.20)')
d = tempfile.mkdtemp()
ld = os.path.join(d, 'ledger')
os.makedirs(os.path.join(ld, 'redteam'))
mk_obj(os.path.join(ld, 'redteam', 'objections.jsonl'), 9, 1)
run_r(ld)
run_r(ld)
r = load_r(ld)
lvl = r['level']
ratio = r['blocking_ratio']
if lvl == 1:
    ok('level=1 (tighten)')
else:
    no('level=' + str(lvl) + ', expected 1')
if ratio == 0.1:
    ok('ratio=0.1')
else:
    no('ratio=' + str(ratio) + ', expected 0.1')
shutil.rmtree(d)

print('[TEST] Loosen (ratio > 0.80)')
d = tempfile.mkdtemp()
ld = os.path.join(d, 'ledger')
os.makedirs(os.path.join(ld, 'redteam'))
mk_obj(os.path.join(ld, 'redteam', 'objections.jsonl'), 1, 9)
run_r(ld)
run_r(ld)
r = load_r(ld)
lvl = r['level']
if lvl == -1:
    ok('level=-1 (loosen)')
else:
    no('level=' + str(lvl) + ', expected -1')
shutil.rmtree(d)

print('[TEST] Maintain (balanced)')
d = tempfile.mkdtemp()
ld = os.path.join(d, 'ledger')
os.makedirs(os.path.join(ld, 'redteam'))
mk_obj(os.path.join(ld, 'redteam', 'objections.jsonl'), 5, 5)
run_r(ld)
run_r(ld)
r = load_r(ld)
lvl = r['level']
if lvl == 0:
    ok('level=0 (maintain)')
else:
    no('level=' + str(lvl) + ', expected 0')
shutil.rmtree(d)

print('[TEST] Level clamping')
d = tempfile.mkdtemp()
ld = os.path.join(d, 'ledger')
os.makedirs(os.path.join(ld, 'redteam'))
with open(os.path.join(ld, 'ratchet.json'), 'w') as f:
    json.dump({'schema_version': 1, 'level': 5, 'blocking_ratio': 0.0, 'window_size': 20, 'history': [], 'last_updated': None}, f)
mk_obj(os.path.join(ld, 'redteam', 'objections.jsonl'), 10, 0)
run_r(ld)
r = load_r(ld)
lvl = r['level']
if lvl <= 5:
    ok('level=' + str(lvl) + ' (clamped)')
else:
    no('level=' + str(lvl) + ', exceeds max=5')
shutil.rmtree(d)

print('[TEST] History tracked')
d = tempfile.mkdtemp()
ld = os.path.join(d, 'ledger')
os.makedirs(os.path.join(ld, 'redteam'))
mk_obj(os.path.join(ld, 'redteam', 'objections.jsonl'), 0, 10)
run_r(ld)
run_r(ld)
run_r(ld)
r = load_r(ld)
h = len(r['history'])
if h >= 2:
    ok('history=' + str(h) + ' entries')
else:
    no('history=' + str(h) + ', expected>=2')
shutil.rmtree(d)

print('[TEST] SOUL references ratchet')
sp = os.path.join(REPO_ROOT, 'templates', 'SOUL.redteam.md')
if os.path.exists(sp):
    s = open(sp, encoding='utf-8', errors='replace').read()
    if 'ratchet' in s.lower():
        ok('ratchet in SOUL')
    else:
        no('SOUL missing ratchet')
else:
    no('SOUL not found')

print()
print('=' * 60)
print('  Adaptive Ratchet: %d passed, %d failed' % (PASS, FAIL))
print('=' * 60)
sys.exit(1 if FAIL > 0 else 0)
