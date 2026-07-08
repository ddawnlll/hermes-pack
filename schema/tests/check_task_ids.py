import os
plan_dir = r'C:\Users\dresden\Documents\hermes-pack\.praxis'
for issue_id in ['issue-2','issue-5','issue-6','issue-7','issue-8','issue-9','issue-11','issue-13','issue-15','issue-17']:
    path = os.path.join(plan_dir, f'{issue_id}.plan.yaml')
    with open(path, encoding='cp1252') as f:
        for line in f:
            line = line.strip()
            if 'id:' in line and ('task-' in line):
                print(f'{issue_id}: {line}')
                break
