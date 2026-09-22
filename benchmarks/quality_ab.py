import argparse
import json
import os
import time
import re
import random
import datetime
from pathlib import Path
import sys

BASE_DIR = Path(__file__).parent

def load_evalset():
    with open(BASE_DIR / "evalset" / "news.json", encoding="utf-8") as f:
        news = json.load(f)
    with open(BASE_DIR / "evalset" / "papers.json", encoding="utf-8") as f:
        papers = json.load(f)
    return news + papers

def load_glossary():
    with open(BASE_DIR / "glossary.json", encoding="utf-8") as f:
        return json.load(f)["glossary"]

def check_anomalies(original, translated, glossary):
    anomalies = {}
    critical_anomalies = {}
    
    kr_chars = len(re.findall(r'[가-힣]', translated))
    total_chars = len(re.sub(r'\s+', '', translated))
    if total_chars > 0 and (kr_chars / total_chars) < 0.45:
        critical_anomalies["format_fail"] = {"index": 0, "context": "ratio < 45%"}
        
    if len(translated) < 0.3 * len(original) or len(translated) > 3 * len(original):
        anomalies["length_anomaly"] = True
        
    preambles = ["다음은", "번역:", "here is", "translation:"]
    lower_trans = translated[:50].lower()
    if any(p in lower_trans for p in preambles):
        anomalies["preamble_fail"] = True
        
    misses = []
    lower_orig = original.lower()
    for g in glossary:
        if g['en'].lower() in lower_orig and g['ko'] not in translated:
            misses.append(g['en'])
    if misses:
        anomalies["glossary_miss"] = misses

    cjk_match = re.search(r'[\u4e00-\u9fff]', translated)
    if cjk_match:
        idx = cjk_match.start()
        context = translated[max(0, idx-40):min(len(translated), idx+41)]
        critical_anomalies["cjk_contamination"] = {"index": idx, "context": context}

    cyrillic_match = re.search(r'[\u0400-\u04ff]', translated)
    if cyrillic_match:
        idx = cyrillic_match.start()
        context = translated[max(0, idx-40):min(len(translated), idx+41)]
        critical_anomalies["cyrillic_contamination"] = {"index": idx, "context": context}

    mojibake_match = re.search(r'[\ufffd]', translated)
    if mojibake_match:
        idx = mojibake_match.start()
        context = translated[max(0, idx-40):min(len(translated), idx+41)]
        critical_anomalies["mojibake"] = {"index": idx, "context": context}

    repetition = None
    for i in range(len(translated) - 30):
        substr = translated[i:i+30]
        first_idx = translated.find(substr)
        if first_idx == i:
            second_idx = translated.find(substr, first_idx + 30)
            if second_idx != -1:
                idx = second_idx
                context = translated[max(0, idx-40):min(len(translated), idx+41)]
                repetition = {"index": idx, "context": context}
                break
    if repetition:
        critical_anomalies["repetition"] = repetition

    return anomalies, critical_anomalies

def generate_prompt_pass1(text, glossary):
    glossary_lines = []
    for g in glossary:
        glossary_lines.append(f"- {g['en']} -> {g['ko']} ({g['type']})")
    glossary_str = "\n".join(glossary_lines)
    
    system_prompt = f"""You are an expert technical translator specializing in computer science and information security.
Translate the following English text into Korean.
Do not add any explanations, introductory, or concluding remarks. Output ONLY the translated text.
Ensure the output formatting matches the input exactly. Translate section labels as follows:
- 'Title:' -> '제목:'
- 'Summary:' -> '요약:'
- 'Abstract:' -> '초록:'
- 'Introduction:' -> '서론:'
- 'Conclusion:' -> '결론:'

Use the following glossary for specific terms:
{glossary_str}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]

def generate_prompt_pass2(original_text, draft_translation, glossary):
    glossary_lines = []
    for g in glossary:
        glossary_lines.append(f"- {g['en']} -> {g['ko']} ({g['type']})")
    glossary_str = "\n".join(glossary_lines)
    
    system_prompt = f"""You are an expert technical translator and reviewer. Your task is to verify and refine a draft Korean translation of an English text.
Do not add any explanations, introductory, or concluding remarks. Output ONLY the final translated text.
If there is nothing to fix, output the draft translation exactly as is.
Do not add any new content or explanations not present in the original text.

Limit your corrections to the following 5 categories:
1. Mistranslations
2. Omissions
3. Hallucinations
4. Glossary violations
5. Awkward literal translations (revise literal translations into natural idiomatic expressions used in Korean technical documents)

Ensure section labels are correctly translated (Title:->제목:, Summary:->요약:, Abstract:->초록:, Introduction:->서론:, Conclusion:->결론:).

Use the following glossary for specific terms:
{glossary_str}"""

    user_prompt = f"""Original Text:
{original_text}

Draft Translation:
{draft_translation}"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

def run_model(args):
    try:
        glossary = load_glossary()
        items = load_evalset()
    except Exception as e:
        if args.dry_run:
            print(f"Dry run failed: {e}")
            sys.exit(1)
        else:
            raise

    if args.dry_run:
        prompt_p1 = generate_prompt_pass1("test", glossary)
        prompt_p2 = generate_prompt_pass2("test", "test draft", glossary)
        print("Dry run complete. Setup valid.")
        return
        
    if not args.model:
        print("Error: --model required for non-dry-run execution")
        sys.exit(1)
        
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpus
    
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_math_sdp(True)
    torch.backends.cuda.enable_mem_efficient_sdp(True)
    
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
    total_critical = {"cjk_contamination": 0, "cyrillic_contamination": 0, "mojibake": 0, "repetition": 0}
    flags = {"overedit": 0, "verify_fail": 0}
    
    for idx, item in enumerate(items):
        print(f"Translating {idx+1}/{len(items)}: {item['id']}")
        
        # Pass 1
        prompt1 = generate_prompt_pass1(item["text"], glossary)
        text_input1 = tokenizer.apply_chat_template(prompt1, tokenize=False, add_generation_prompt=True)
        inputs1 = tokenizer(text_input1, return_tensors="pt").to(model.device)
        
        start_time = time.time()
        with torch.no_grad():
            outputs1 = model.generate(**inputs1, max_new_tokens=4096)
        call_time1 = time.time() - start_time
        
        out_text1 = tokenizer.decode(outputs1[0][inputs1.input_ids.shape[1]:], skip_special_tokens=True)
        
        if args.passes == 1:
            out_text2 = out_text1
            call_time2 = 0.0
            overedit = False
            verify_fail = False
        else:
            # Pass 2
            prompt2 = generate_prompt_pass2(item["text"], out_text1, glossary)
            text_input2 = tokenizer.apply_chat_template(prompt2, tokenize=False, add_generation_prompt=True)
            inputs2 = tokenizer(text_input2, return_tensors="pt").to(model.device)
            
            start_time = time.time()
            with torch.no_grad():
                outputs2 = model.generate(**inputs2, max_new_tokens=4096)
            call_time2 = time.time() - start_time
            
            out_text2_raw = tokenizer.decode(outputs2[0][inputs2.input_ids.shape[1]:], skip_special_tokens=True)
            
            # Check length overedit
            len_draft = len(out_text1)
            len_final = len(out_text2_raw)
            overedit = False
            if len_draft > 0:
                ratio = len_final / len_draft
                if ratio < 0.7 or ratio > 1.5:
                    overedit = True
                    
            # Check critical anomalies in pass 2 output
            _, pass2_critical = check_anomalies(item["text"], out_text2_raw, glossary)
            verify_fail = len(pass2_critical) > 0
            
            if overedit or verify_fail:
                out_text2 = out_text1
                if overedit: flags["overedit"] += 1
                if verify_fail: flags["verify_fail"] += 1
            else:
                out_text2 = out_text2_raw
        
        anom, crit = check_anomalies(item["text"], out_text2, glossary)
        for k in anom:
            if k in total_anomalies:
                total_anomalies[k] += 1
        for k in crit:
            if k in total_critical:
                total_critical[k] += 1
                
        results.append({
            "id": item["id"],
            "original": item["text"],
            "draft": out_text1,
            "translated": out_text2,
            "time_sec_pass1": call_time1,
            "time_sec_pass2": call_time2,
            "overedit": overedit,
            "verify_fail": verify_fail,
            "anomalies": anom,
            "critical_anomalies": crit
        })
        
    out_dir = BASE_DIR / "results"
    out_dir.mkdir(exist_ok=True)
    model_slug = args.model.split("/")[-1]
    
    passes_suffix = f"-p{args.passes}"
    json_path = out_dir / f"quality-{model_slug}{passes_suffix}.json"
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"model": args.model, "passes": args.passes, "results": results, "anomalies_summary": total_anomalies, "critical_summary": total_critical, "flags": flags}, f, indent=2, ensure_ascii=False)
        
    md_path = out_dir / f"quality-{model_slug}{passes_suffix}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Quality Evaluation: {args.model} (Passes: {args.passes})\n\n")
        f.write("## Critical Anomalies\n")
        for k, v in total_critical.items():
            f.write(f"- {k}: {v}\n")
        f.write("\n## Anomalies Summary\n")
        for k, v in total_anomalies.items():
            f.write(f"- {k}: {v}\n")
        f.write("\n## Protection Flags\n")
        f.write(f"- overedit: {flags['overedit']}\n")
        f.write(f"- verify_fail: {flags['verify_fail']}\n")
            
    print(f"Saved to {json_path}")

def run_compare(file_a, file_b):
    with open(file_a, encoding="utf-8") as f:
        data_a = json.load(f)
    with open(file_b, encoding="utf-8") as f:
        data_b = json.load(f)
        
    model_a = f"{data_a.get('model', 'model_a')}_p{data_a.get('passes', '?')}"
    model_b = f"{data_b.get('model', 'model_b')}_p{data_b.get('passes', '?')}"
    
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
        
    out_dir = BASE_DIR / "results"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    
    with open(out_dir / f"compare-graded-{ts}.json", "w", encoding="utf-8") as f:
        json.dump(graded_items, f, indent=2, ensure_ascii=False)
        
    with open(out_dir / f"compare-blind-{ts}.json", "w", encoding="utf-8") as f:
        json.dump(blind_items, f, indent=2, ensure_ascii=False)
        
    with open(out_dir / f"compare-key-{ts}.json", "w", encoding="utf-8") as f:
        json.dump(answer_key, f, indent=2, ensure_ascii=False)
        
    print("Created compare files: graded, blind, and answer key.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Model to run")
    parser.add_argument("--gpus", default="0,1", help="GPUs to use")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument("--compare", nargs=2, help="Compare two result JSON files")
    parser.add_argument("--passes", type=int, choices=[1, 2], default=2, help="Number of translation passes")
    
    args = parser.parse_args()
    
    if args.compare:
        run_compare(args.compare[0], args.compare[1])
    elif args.dry_run or args.model:
        run_model(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
