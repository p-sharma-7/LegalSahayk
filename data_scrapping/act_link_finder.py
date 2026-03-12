#finding total act's link
import requests
from bs4 import BeautifulSoup
import time

# Base URL for searching Central Acts on India Code
# rpp = results per page (max 100), start = pagination offset
BASE_URL = "https://www.indiacode.nic.in/handle/123456789/1362/simple-search?rpp=100&start={}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def scrape_acts_via_search(max_pages=5):
    act_links = set()
    
    print("Starting pagination scrape...")
    for page in range(max_pages):
        start_offset = page * 100
        url = BASE_URL.format(start_offset)
        print(f"\nScraping page {page + 1}: {url}")
        
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            print(f"Failed to fetch page. Status code: {r.status_code}")
            break
            
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Find all <a> tags (links) on the page
        found_on_page = 0
        for a in soup.find_all("a", href=True):
            href = a["href"]
            
            # Filter to make sure it's an Act link and not a random navigation button
            if "/handle/" in href and "simple-search" not in href and "browse" not in href:
                # Resolve relative URLs to absolute URLs
                full_url = "https://www.indiacode.nic.in" + href if href.startswith("/") else href
                
                if full_url not in act_links:
                    act_links.add(full_url)
                    found_on_page += 1
                    
        print(f"-> Found {found_on_page} unique Act links on this page.")
        
        # Polite delay to prevent the NIC firewall from temporarily blocking your IP
        time.sleep(2)
        
    return list(act_links)

if __name__ == "__main__":
    # Change max_pages to a higher number to scrape the entire database
    links = scrape_acts_via_search(max_pages=3) 
    
    print(f"\nTotal Acts collected: {len(links)}")
    
    if links:
        with open("act_links.txt", "w") as f:
            for l in links:
                f.write(l + "\n")
        print("Successfully saved to act_links.txt")