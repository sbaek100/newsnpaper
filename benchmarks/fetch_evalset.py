import argparse
import json
import os
import time
import requests
import feedparser
import xml.etree.ElementTree as ET
from pypdf import PdfReader
import re
import io
from pathlib import Path

BASE_DIR = Path(__file__).parent
EVALSET_DIR = BASE_DIR / "evalset"
PAPERS_JSON = EVALSET_DIR / "papers.json"
NEWS_JSON = EVALSET_DIR / "news.json"
PDF_DIR = BASE_DIR / "papers_pdf"

def fetch_news(count=15):
    feeds = [
        "https://www.bleepingcomputer.com/feed/",
        "https://feeds.feedburner.com/TheHackersNews",
        "https://krebsonsecurity.com/feed/"
    ]
    news_items = []
    for feed_url in feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if len(news_items) >= count:
                break
            
            summary = entry.get("summary", "")
            summary = re.sub(r'<[^>]+>', '', summary) # remove html tags
            
            text = f"Title: {entry.title}\n\nSummary: {summary}"
            news_items.append({
                "id": f"news-{len(news_items)+1}",
                "source_url": entry.link,
                "text": text
            })
        if len(news_items) >= count:
            break
    return news_items

def truncate_section(text, max_len=8000):
    if len(text) <= max_len:
        return text, False
    
    truncated = text[:max_len]
    last_period = truncated.rfind('. ')
    if last_period != -1:
        truncated = truncated[:last_period + 1]
    
    return truncated + " …(생략)", True

def extract_sections(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                full_text += extracted + "\n"
        
        # very basic heuristics for Intro/Conclusion
        intro_match = re.search(r'(?i)(?:\b1\.\s*)?Introduction\b(.*?)(?:\b2\.\s*[A-Z]|\bBackground\b|\bRelated Work\b)', full_text, re.DOTALL)
        conc_match = re.search(r'(?i)(?:\b[0-9]+\.\s*)?Conclusion(?:s)?\b(.*?)(?:\bReferences\b|\bAcknowledgments\b)', full_text, re.DOTALL)
        
        intro = intro_match.group(1).strip() if intro_match else ""
        conc = conc_match.group(1).strip() if conc_match else ""
        
        if not intro or len(intro) < 100 or not conc or len(conc) < 50:
            return None, None
            
        return intro, conc
    except Exception as e:
        print(f"Error extracting {pdf_path}: {e}")
        return None, None

def fetch_papers(count=5):
    papers = []
    start = 0
    max_results = 10
    
    os.makedirs(PDF_DIR, exist_ok=True)
    
    while len(papers) < count:
        url = f"http://export.arxiv.org/api/query?search_query=cat:cs.CR&sortBy=submittedDate&sortOrder=descending&start={start}&max_results={max_results}"
        print(f"Fetching {url}")
        try:
            headers = {"User-Agent": "python-requests/2.25.1"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except Exception as e:
            print(f"Failed to fetch arxiv: {e}")
            time.sleep(3)
            start += max_results
            continue
            
        entries = root.findall("{http://www.w3.org/2005/Atom}entry")
        if not entries:
            break
            
        for entry in entries:
            if len(papers) >= count:
                break
                
            arxiv_id = entry.find("{http://www.w3.org/2005/Atom}id").text.split("/")[-1]
            title = entry.find("{http://www.w3.org/2005/Atom}title").text.replace("\n", " ").strip()
            abstract = entry.find("{http://www.w3.org/2005/Atom}summary").text.replace("\n", " ").strip()
            
            pdf_url = None
            for link in entry.findall("{http://www.w3.org/2005/Atom}link"):
                if link.attrib.get("title") == "pdf":
                    pdf_url = link.attrib.get("href")
                    break
                    
            if not pdf_url:
                continue
                
            pdf_path = os.path.join(PDF_DIR, f"{arxiv_id}.pdf")
            try:
                print(f"Downloading {pdf_url}")
                r = requests.get(pdf_url, headers=headers, timeout=30)
                r.raise_for_status()
                with open(pdf_path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                print(f"Failed to download pdf: {e}")
                time.sleep(3)
                continue
                
            intro, conc = extract_sections(pdf_path)
            
            # Q-7: 수집한 PDF는 추출 후 삭제한다
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                
            if intro and conc:
                intro_trunc, is_intro_trunc = truncate_section(intro)
                conc_trunc, is_conc_trunc = truncate_section(conc)
                
                text = f"Title: {title}\n\nAbstract: {abstract}\n\nIntroduction: {intro_trunc}\n\nConclusion: {conc_trunc}"
                papers.append({
                    "id": f"arxiv-{arxiv_id}",
                    "source_url": f"https://arxiv.org/abs/{arxiv_id}",
                    "text": text,
                    "truncated": is_intro_trunc or is_conc_trunc,
                    "intro_original_len": len(intro),
                    "conc_original_len": len(conc)
                })
                print(f"Successfully extracted {arxiv_id}")
            else:
                print(f"Skipping {arxiv_id} due to missing sections")
                
            # Q-2: 3초 이상 간격
            time.sleep(3.5)
            
        start += max_results
        
    try:
        os.rmdir(PDF_DIR)
    except:
        pass
        
    return papers

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()
    
    os.makedirs(EVALSET_DIR, exist_ok=True)
    
    if not args.force and (os.path.exists(PAPERS_JSON) or os.path.exists(NEWS_JSON)):
        print("evalset already exists. Use --force to overwrite.")
        return
        
    print("Fetching news...")
    news_items = fetch_news(15)
    with open(NEWS_JSON, "w", encoding="utf-8") as f:
        json.dump(news_items, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(news_items)} news to {NEWS_JSON}")
        
    print("Fetching papers...")
    papers = fetch_papers(5)
    with open(PAPERS_JSON, "w", encoding="utf-8") as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(papers)} papers to {PAPERS_JSON}")

if __name__ == "__main__":
    main()
