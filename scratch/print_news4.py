import json

with open('benchmarks/results/quality-Qwen2.5-7B-Instruct.json', 'r') as f:
    data = json.load(f)

for result in data['results']:
    if result['id'] == 'news-4':
        print(result['translated'])
