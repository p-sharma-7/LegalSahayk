import requests
from bs4 import BeautifulSoup
import json
import time
import fitz  # PyMuPDF
import re
import os
import logging

# ==========================================
# 1. LOGGING SETUP
# ==========================================
# This configures the logger to write to both a file and the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper.log", mode="w", encoding="utf-8"),
        logging.StreamHandler() # Keeps output in the terminal too
    ]
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ==========================================
# 2. SME LEGAL DOMAINS (The Ultimate List)
# ==========================================
LEGAL_DOMAINS = {
    "Contracts & Commercial": ["contract", "agreement", "negotiable", "sale of goods", "specific relief", "arbitration", "partnership"],
    "Core Corporate Governance": ["compan", "securities", "limited liability", "sebi", "trust", "corporate"],
    "Management & Administration": ["management", "director", "board", "administration", "managerial", "remuneration", "officer"],
    "Real Estate & Property": ["property", "stamp", "registration", "lease", "tenancy", "real estate", "rera", "transfer"],
    "Foreign Exchange & Trade": ["foreign exchange", "fema", "export", "import", "trade", "sez", "customs"],
    "Banking, Payments & Insurance": ["payment", "settlement", "insurance", "factoring", "rbi", "fund", "deposit"],
    "White-Collar Crime & Liability": ["money laundering", "pmla", "corruption", "benami", "fraud", "bribery"],
    "Taxation": ["tax", "tariff", "excise", "gst", "revenue"],
    "Insolvency & Financial Distress": ["insolvency", "bankruptcy", "sarfaesi", "recovery", "debt", "bank", "coinage", "financial"],
    "Labour & Employment": ["labour", "employment", "workmen", "wages", "gratuity", "provident", "maternity", "factories", "trade union", "industrial dispute", "bonus", "apprentice"],
    "Intellectual Property": ["copyright", "patent", "trademark", "design", "geographical indication"],
    "Data Protection & IT": ["information technology", "data", "digital", "privacy"],
    "Competition & Consumer": ["competition", "consumer", "essential commodities", "legal metrology", "standards"],
    "Environmental & Compliance": ["environment", "pollution", "water", "air", "forest", "hazard", "waste"],
    "MSME Specific": ["micro", "small", "medium", "enterprise", "msme", "khadi", "coir"]
}

ALL_KEYWORDS = [keyword for category in LEGAL_DOMAINS.values() for keyword in category]

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def get_matched_keywords(title):
    title_lower = title.lower()
    return [kw for kw in ALL_KEYWORDS if kw in title_lower]

def clean_page_text(page_text, act_title):
    lines = page_text.split('\n')
    cleaned_lines = []
    title_clean = act_title.strip().lower()
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if re.match(r'^[\s\-\_]*\d+[\s\-\_]*$', line_stripped):
            continue
        if line_stripped.lower() in title_clean or title_clean in line_stripped.lower():
            if len(line_stripped) < len(title_clean) + 20: 
                continue
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)

def extract_pdf_text(pdf_bytes, act_title):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_text = ""
    for page in doc:
        raw_page_text = page.get_text("text")
        cleaned_page_text = clean_page_text(raw_page_text, act_title)
        full_text += cleaned_page_text + "\n"
    return full_text

def chunk_text_by_section(raw_text, title, matched_keywords, pdf_link):
    chunks = []
    section_splits = re.split(r'\n(?=\d+\.\s)', raw_text)
    
    preamble = section_splits[0].strip()
    if len(preamble) > 50:
        chunks.append({
            "title": title, "act": title, "section": "Preamble / Introduction",
            "full_text": preamble, "keywords": matched_keywords, "pdf_url": pdf_link
        })
    
    for section_text in section_splits[1:]:
        section_text = section_text.strip()
        if not section_text: continue
            
        match = re.match(r'^(\d+)\.', section_text)
        section_id = f"Section {match.group(1)}" if match else "Unknown Section"
        
        chunks.append({
            "title": title, "act": title, "section": section_id,
            "full_text": section_text, "keywords": matched_keywords, "pdf_url": pdf_link
        })
    return chunks

# ==========================================
# 4. MAIN PROCESSING LOGIC
# ==========================================
def process_act(url):
    logging.info(f"Inspecting: {url}")
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        logging.error(f"Failed to load page. Status: {r.status_code}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    title_tag = soup.find("meta", {"name": "DC.title"})
    
    if not title_tag:
        logging.warning("Could not find title meta tag.")
        return []
        
    title = title_tag["content"]
    matched_keywords = get_matched_keywords(title)
    
    if not matched_keywords:
        logging.info(f"Skipping (No Relevant Keywords): {title}")
        return []
        
    logging.info(f"Match Found: {title} | Keywords: {matched_keywords}")
    
    pdf_link = None
    for a in soup.find_all("a", href=True):
        if "/bitstream/" in a["href"] and a["href"].endswith(".pdf"):
            pdf_link = "https://www.indiacode.nic.in" + a["href"]
            break
            
    if not pdf_link:
        logging.warning(f"No PDF link found for: {title}")
        return []
        
    logging.info(f"Downloading PDF: {pdf_link}")
    pdf_r = requests.get(pdf_link, headers=HEADERS)
    
    if pdf_r.status_code == 200:
        clean_text = extract_pdf_text(pdf_r.content, title)
        return chunk_text_by_section(clean_text, title, matched_keywords, pdf_link)
    else:
        logging.error(f"Failed to download PDF. Status: {pdf_r.status_code}")
        return []

if __name__ == "__main__":
    db_list = []
    
    if not os.path.exists("act_links.txt"):
        logging.error("act_links.txt not found. Please run your scraper first.")
        exit()
        
    with open("act_links.txt", "r") as f:
        links = [line.strip() for line in f.readlines() if line.strip()]
        
    logging.info(f"Loaded {len(links)} links. Starting full extraction...")
    
    for i, link in enumerate(links): 
        logging.info(f"--- Processing Link {i + 1} of {len(links)} ---")
        
        act_chunks = process_act(link)
        if act_chunks:
            db_list.extend(act_chunks) 
            logging.info(f"-> Extracted {len(act_chunks)} clean sections.")
            
        time.sleep(2) 
        
    with open("sme_statutes_db.json", "w", encoding="utf-8") as f:
        json.dump(db_list, f, indent=4, ensure_ascii=False)
        
    logging.info(f"Done! Successfully saved {len(db_list)} individual sections to sme_statutes_db.json")