import argparse
import json
import os
import time
import datetime
import math
import statistics
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

def check_numa_boundaries(gpus):
    if not gpus:
        return
    gpu_list = [int(g.strip()) for g in gpus.split(',')]
    group_a = set(range(0, 4))
    group_b = set(range(4, 8))
    
    in_a = any(g in group_a for g in gpu_list)
    in_b = any(g in group_b for g in gpu_list)
    
    if in_a and in_b:
        print(f"WARNING: Selected GPUs {gpus} cross NUMA boundaries (0-3 / 4-7). Performance may degrade.")

def get_call_distribution(total_calls):
    # Base distribution for 80 calls: 25, 25, 8, 22 (8, 7, 7)
    ratio_news_t = 25 / 80
    ratio_news_s = 25 / 80
    ratio_paper_t = 8 / 80
    ratio_paper_a = 8 / 80
    ratio_paper_i = 7 / 80
    ratio_paper_c = 7 / 80
    
    news_t = int(round(total_calls * ratio_news_t))
    news_s = int(round(total_calls * ratio_news_s))
    paper_t = int(round(total_calls * ratio_paper_t))
    paper_a = int(round(total_calls * ratio_paper_a))
    paper_i = int(round(total_calls * ratio_paper_i))
    
    # Give the rest to conclusion to ensure sum equals total_calls
    paper_c = total_calls - (news_t + news_s + paper_t + paper_a + paper_i)
    
    return {
        "news_title": news_t,
        "news_summary": news_s,
        "paper_title": paper_t,
        "paper_abstract": paper_a,
        "paper_introduction": paper_i,
        "paper_conclusion": paper_c
    }

def load_fixtures():
    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, "fixtures", "news_titles.json")) as f:
        news_titles = json.load(f)
    with open(os.path.join(base, "fixtures", "news_summaries.json")) as f:
        news_summaries = json.load(f)
    with open(os.path.join(base, "fixtures", "paper_titles.json")) as f:
        paper_titles = json.load(f)
    with open(os.path.join(base, "fixtures", "paper_sections.json")) as f:
        paper_sections = json.load(f)
        
    abstracts = [s['text'] for s in paper_sections if s['name'] == 'Abstract']
    intros = [s['text'] for s in paper_sections if s['name'] == 'Introduction']
    conclusions = [s['text'] for s in paper_sections if s['name'] == 'Conclusion']
    
    with open(os.path.join(base, "glossary.json")) as f:
        glossary = json.load(f)["glossary"]
        
    return news_titles, news_summaries, paper_titles, abstracts, intros, conclusions, glossary

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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--gpus", default="0,1")
    parser.add_argument("--calls", type=int, default=80)
    parser.add_argument("--out", default="results/")
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpus
    check_numa_boundaries(args.gpus)
    
    dist = get_call_distribution(args.calls)
    news_titles, news_summaries, paper_titles, abstracts, intros, conclusions, glossary = load_fixtures()
    
    tasks = []
    def add_tasks(texts, count, name):
        for i in range(count):
            tasks.append({
                "type": name,
                "text": texts[i % len(texts)]
            })
            
    add_tasks(news_titles, dist["news_title"], "news_title")
    add_tasks(news_summaries, dist["news_summary"], "news_summary")
    add_tasks(paper_titles, dist["paper_title"], "paper_title")
    add_tasks(abstracts, dist["paper_abstract"], "paper_abstract")
    add_tasks(intros, dist["paper_introduction"], "paper_introduction")
    add_tasks(conclusions, dist["paper_conclusion"], "paper_conclusion")
    
    if args.dry_run:
        print("Dry run complete. Setup valid.")
        return
        
    # Disable flash attention specifically for Pascal
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_math_sdp(True)
    torch.backends.cuda.enable_mem_efficient_sdp(True)
    
    print(f"Loading model {args.model}...")
    start_load = time.time()
    
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.float16,
        device_map="auto",
        attn_implementation="sdpa"
    )
    
    load_time = time.time() - start_load
    print(f"Model loaded in {load_time:.2f} seconds.")
    
    # Check for CPU offloading
    for name, param in model.named_parameters():
        if param.device.type == "cpu":
            raise RuntimeError(f"CPU offloading detected for parameter {name}. Test invalid.")
            
    # Warmup
    print(f"Running {args.warmup} warmup calls...")
    for i in range(args.warmup):
        prompt = generate_prompt(news_titles[i % len(news_titles)], glossary)
        text_input = tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text_input, return_tensors="pt").to(model.device)
        with torch.no_grad():
            model.generate(**inputs, max_new_tokens=50)
            
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    
    print("Starting benchmark...")
    start_bench = time.time()
    
    results_by_type = {k: [] for k in dist.keys()}
    total_out_tokens = 0
    samples = []
    
    for idx, task in enumerate(tasks):
        prompt = generate_prompt(task["text"], glossary)
        text_input = tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text_input, return_tensors="pt").to(model.device)
        
        # Proportional max_new_tokens
        in_len = inputs.input_ids.shape[1]
        max_new = min(2048, max(50, int(in_len * 1.5)))
        
        start_call = time.time()
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=max_new)
        torch.cuda.synchronize()
        call_time = time.time() - start_call
        
        out_tokens = outputs.shape[1] - inputs.input_ids.shape[1]
        total_out_tokens += out_tokens
        
        results_by_type[task["type"]].append(call_time)
        
        if len(samples) < 20:
            out_text = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
            samples.append({
                "type": task["type"],
                "original": task["text"],
                "translated": out_text
            })
            
        if (idx + 1) % 10 == 0:
            print(f"Processed {idx + 1}/{len(tasks)}...")
            
    total_time = time.time() - start_bench
    
    # Peak VRAM
    vram_peaks = []
    for i in range(torch.cuda.device_count()):
        peak = torch.cuda.max_memory_allocated(i) / (1024**3)
        vram_peaks.append(f"GPU {i}: {peak:.2f} GB")
        
    stats = {}
    for k, v in results_by_type.items():
        if not v:
            continue
        v_sorted = sorted(v)
        stats[k] = {
            "avg": sum(v)/len(v),
            "p50": v_sorted[int(len(v)*0.5)],
            "p95": v_sorted[int(len(v)*0.95)]
        }
        
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    model_slug = args.model.split("/")[-1]
    
    # JSON Result
    res_json = {
        "model": args.model,
        "gpus": args.gpus,
        "total_calls": args.calls,
        "load_time_sec": load_time,
        "total_time_sec": total_time,
        "total_time_min": total_time / 60,
        "tokens_per_sec": total_out_tokens / total_time,
        "vram_peaks": vram_peaks,
        "stats_by_type": stats
    }
    
    os.makedirs(args.out, exist_ok=True)
    json_path = os.path.join(args.out, f"{ts}-{model_slug}.json")
    with open(json_path, "w") as f:
        json.dump(res_json, f, indent=2)
        
    # Markdown Result
    md_path = os.path.join(args.out, f"{ts}-{model_slug}.md")
    if total_time <= 3600:
        status = "🟢 통과"
    elif total_time <= 14400:
        status = "🟡 조건부"
    else:
        status = "🔴 실패"
        
    with open(md_path, "w") as f:
        f.write(f"# {status}\n\n")
        f.write(f"- Model: {args.model}\n")
        f.write(f"- GPUs: {args.gpus}\n")
        f.write(f"- Total Calls: {args.calls}\n")
        f.write(f"- Total Time: {total_time/60:.2f} minutes\n")
        f.write(f"- Load Time: {load_time:.2f} seconds\n")
        f.write(f"- Output Tokens/Sec: {total_out_tokens / total_time:.2f}\n")
        f.write("- VRAM Peaks:\n")
        for p in vram_peaks:
            f.write(f"  - {p}\n")
            
        f.write("\n## Stats by Type (seconds)\n")
        for k, v in stats.items():
            f.write(f"- **{k}**: Avg {v['avg']:.2f}, p50 {v['p50']:.2f}, p95 {v['p95']:.2f}\n")
            
        f.write("\n## Samples (first 20)\n")
        for idx, s in enumerate(samples):
            f.write(f"### Sample {idx+1} ({s['type']})\n")
            f.write(f"**Original:** {s['original']}\n\n")
            f.write(f"**Translated:** {s['translated']}\n\n")
            
    print(f"Done. Saved to {json_path} and {md_path}")

if __name__ == "__main__":
    main()
