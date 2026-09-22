import json
import random

def generate_text(num_words, include_ransomware=False):
    words = ["security", "system", "network", "data", "attack", "hacker", "vulnerability", 
             "cyber", "threat", "model", "analysis", "framework", "evaluation", "performance",
             "algorithm", "method", "approach", "results", "conclusion", "future"]
    
    sentence = []
    for _ in range(num_words):
        sentence.append(random.choice(words))
    
    if include_ransomware:
        insert_idx = random.randint(0, len(sentence)-1)
        sentence[insert_idx] = "ransomware"
        
    sentence[0] = sentence[0].capitalize()
    return " ".join(sentence) + "."

def main():
    # News titles (25+) - 10 to 20 words
    news_titles = []
    for i in range(30):
        news_titles.append(generate_text(random.randint(10, 20), include_ransomware=(i==0)))
    with open("benchmarks/fixtures/news_titles.json", "w") as f:
        json.dump(news_titles, f, indent=2)
        
    # News summaries (25+) - 40 to 80 words
    news_summaries = []
    for i in range(30):
        news_summaries.append(generate_text(random.randint(40, 80), include_ransomware=(i==0)))
    with open("benchmarks/fixtures/news_summaries.json", "w") as f:
        json.dump(news_summaries, f, indent=2)
        
    # Paper titles (8+) - 10 to 20 words
    paper_titles = []
    for i in range(10):
        paper_titles.append(generate_text(random.randint(10, 20)))
    with open("benchmarks/fixtures/paper_titles.json", "w") as f:
        json.dump(paper_titles, f, indent=2)
        
    # Paper sections (22+) - name, text
    # Abstract: 8, Intro: 7, Conclusion: 7
    paper_sections = []
    for i in range(8):
        paper_sections.append({"name": "Abstract", "text": generate_text(random.randint(150, 250), include_ransomware=(i==0))})
    for i in range(7):
        paper_sections.append({"name": "Introduction", "text": generate_text(random.randint(600, 1000))})
    for i in range(7):
        paper_sections.append({"name": "Conclusion", "text": generate_text(random.randint(300, 500))})
        
    with open("benchmarks/fixtures/paper_sections.json", "w") as f:
        json.dump(paper_sections, f, indent=2)

if __name__ == "__main__":
    main()
