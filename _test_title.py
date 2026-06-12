import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scraper import scrape_article

url = "https://topsport.bg/mondial-2026/meksiko-yuzhna-afrika-2-0-v-mach-ot-mondiala.html"
result = scrape_article(url)
print("TITLE:", result["title"])
print("AUTHORS:", result.get("authors"))
print("DATE:", result.get("publish_date"))
print("TEXT LEN:", len(result.get("text", "")))
print("TEXT FIRST 200:", result.get("text", "")[:200])
