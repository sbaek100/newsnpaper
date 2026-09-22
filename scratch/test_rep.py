import json
import re

with open('benchmarks/results/quality-Qwen2.5-7B-Instruct.json', 'r') as f:
    data = json.load(f)

for result in data['results']:
    if result['id'] == 'news-4':
        t = result['translated']
        for i in range(len(t)-30):
            sub = t[i:i+30]
            if t.count(sub) >= 3:
                print(f"Found repetition of: {sub}")
                break
