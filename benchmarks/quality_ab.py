import argparse
import json
import os
import time
import re
import random
import datetime

def load_evalset():
    with open("benchmarks/evalset/news.json", encoding="utf-8") as f:
        news = json.load(f)
    with open("benchmarks/evalset/papers.json", encoding="utf-8") as f:
        papers = json.load(f)
    return news + papers

def load_glossary():
    with open("benchmarks/glossary.json", encoding="utf-8") as f:
        return json.load(f)["glossary"]

def check_anomalies(original, translated, glossary):
    anomalies = {}
    
    # format_fail: < 30% Korean characters
    kr_chars = len(re.findall(r'[가-힣]', translated))
    total_chars = len(re.sub(r'\s+', '', translated))
    if total_chars > 0 and (kr_chars / total_chars) < 0.3:
        anomalies["format_fail"] = True
        
    # length_anomaly
    if len(translated) < 0.3 * len(original) or len(translated) > 3 * len(original):
        anomalies["length_anomaly"] = True
        
    # preamble_fail
    preambles = ["다음은", "번역:", "here is", "translation:"]
    lower_trans = translated[:50].lower()
    if any(p in lower_trans for p in preambles):
        anomalies["preamble_fail"] = True
        
    # glossary_miss
    misses = []
    lower_orig = original.lower()
    for g in glossary:
        if g['en'].lower() in lower_orig and g['ko'] not in translated:
            misses.append(g['en'])
    if misses:
        anomalies["glossary_miss"] = misses
        
    return anomalies

def generate_prompt(text, glossary):
    glossary_lines = []
    for g in glossary:
        glossary_lines.append(f"- {g['en']} -> {g['ko']} ({g['type']})")
    glossary_str = "\n".join(glossary_lines)
    
    system_prompt = f"""You are an expert technical translator specializing in computer science and information security.
Translate the following English text into Korean.
Do not add any explanations, introductory, or concluding remarks. Output ONLY the translated text.

Use the following glossary for specific terms:
{glossary_str}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]

def run_model(args):
    # Q-12: Use same prompts and glossary as SPEC-001
    glossary = load_glossary()
    items = load_evalset()
    
    if args.dry_run:
        print("Dry run complete. Setup valid.")
        return
        
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpus
    
    # Disable flash attention specifically for Pascal
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_math_sdp(True)
    torch.backends.cuda.enable_mem_efficient_sdp(True)
    
    # EXAONE 특이사항: trust_remote_code=True
    # bf16 금지 -> torch.float16
    print(f"Loading model {args.model}...")
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.float16,
        device_map="auto",
        attn_implementation="sdpa",
        trust_remote_code=True
    )
    
    results = []
    total_anomalies = {"format_fail": 0, "length_anomaly": 0, "preamble_fail": 0, "glossary_miss": 0}
    
    for idx, item in enumerate(items):
        print(f"Translating {idx+1}/{len(items)}: {item['id']}")
        prompt = generate_prompt(item["text"], glossary)
        text_input = tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text_input, return_tensors="pt").to(model.device)
        
        start_time = time.time()
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=4096)
        call_time = time.time() - start_time
        
        out_tokens = outputs.shape[1] - inputs.input_ids.shape[1]
        out_text = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        
        anomalies = check_anomalies(item["text"], out_text, glossary)
        for k in anomalies:
            if k in total_anomalies:
                total_anomalies[k] += 1
                
        results.append({
            "id": item["id"],
            "original": item["text"],
            "translated": out_text,
            "time_sec": call_time,
            "output_tokens": out_tokens,
            "anomalies": anomalies
        })
        
    os.makedirs("benchmarks/results", exist_ok=True)
    model_slug = args.model.split("/")[-1]
    json_path = f"benchmarks/results/quality-{model_slug}.json"
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"model": args.model, "results": results, "anomalies_summary": total_anomalies}, f, indent=2, ensure_ascii=False)
        
    md_path = f"benchmarks/results/quality-{model_slug}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Quality Evaluation: {args.model}\n\n")
        f.write("## Anomalies Summary\n")
        for k, v in total_anomalies.items():
            f.write(f"- {k}: {v}\n")
            
    print(f"Saved to {json_path}")

def run_compare(file_a, file_b):
    with open(file_a, encoding="utf-8") as f:
        data_a = json.load(f)
    with open(file_b, encoding="utf-8") as f:
        data_b = json.load(f)
        
    model_a = data_a["model"]
    model_b = data_b["model"]
    
    map_a = {r["id"]: r for r in data_a["results"]}
    map_b = {r["id"]: r for r in data_b["results"]}
    
    common_ids = list(set(map_a.keys()) & set(map_b.keys()))
    common_ids.sort()
    
    graded_items = []
    blind_items = []
    answer_key = {}
    
    for cid in common_ids:
        r_a = map_a[cid]
        r_b = map_b[cid]
        
        graded_items.append({
            "id": cid,
            "original": r_a["original"],
            model_a: r_a["translated"],
            model_b: r_b["translated"]
        })
        
        # blind randomize
        models_order = [(model_a, r_a["translated"]), (model_b, r_b["translated"])]
        random.shuffle(models_order)
        
        blind_items.append({
            "id": cid,
            "original": r_a["original"],
            "Model_1": models_order[0][1],
            "Model_2": models_order[1][1]
        })
        
        answer_key[cid] = {
            "Model_1": models_order[0][0],
            "Model_2": models_order[1][0]
        }
        
    os.makedirs("benchmarks/results", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    
    with open(f"benchmarks/results/compare-graded-{ts}.json", "w", encoding="utf-8") as f:
        json.dump(graded_items, f, indent=2, ensure_ascii=False)
        
    with open(f"benchmarks/results/compare-blind-{ts}.json", "w", encoding="utf-8") as f:
        json.dump(blind_items, f, indent=2, ensure_ascii=False)
        
    with open(f"benchmarks/results/compare-key-{ts}.json", "w", encoding="utf-8") as f:
        json.dump(answer_key, f, indent=2, ensure_ascii=False)
        
    print("Created compare files: graded, blind, and answer key.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Model to run")
    parser.add_argument("--gpus", default="0,1", help="GPUs to use")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument("--compare", nargs=2, help="Compare two result JSON files")
    
    args = parser.parse_args()
    
    if args.compare:
        run_compare(args.compare[0], args.compare[1])
    elif args.model:
        run_model(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
