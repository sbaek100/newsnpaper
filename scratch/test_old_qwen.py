import json
import re

# Import the new function from quality_ab.py
import sys
sys.path.append('benchmarks')
from quality_ab import check_anomalies, load_glossary

def run_test():
    with open('benchmarks/results/quality-Qwen2.5-7B-Instruct.json', 'r') as f:
        data = json.load(f)
    
    glossary = load_glossary()
    
    cjk_count = 0
    cyrillic_count = 0
    mojibake_count = 0
    repetition_count = 0
    format_fail_count = 0

    for result in data['results']:
        anomalies, critical = check_anomalies(result['original'], result['translated'], glossary)
        if 'cjk_contamination' in critical:
            cjk_count += 1
            print(f"CJK in {result['id']}")
        if 'cyrillic_contamination' in critical:
            cyrillic_count += 1
            print(f"Cyrillic in {result['id']}")
        if 'mojibake' in critical:
            mojibake_count += 1
            print(f"Mojibake in {result['id']}")
        if 'repetition' in critical:
            repetition_count += 1
            print(f"Repetition in {result['id']}")
        if 'format_fail' in critical:
            format_fail_count += 1
            print(f"Format fail in {result['id']}")
            
    print(f"CJK: {cjk_count}, Cyrillic: {cyrillic_count}, Mojibake: {mojibake_count}, Repetition: {repetition_count}")

if __name__ == '__main__':
    run_test()
