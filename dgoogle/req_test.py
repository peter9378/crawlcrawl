import urllib.request
import re
from bs4 import BeautifulSoup

url = 'https://www.google.com/search?q=hello&gl=us'
req = urllib.request.Request(
    url, 
    data=None, 
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
)
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        bres = soup.find(id='bres')
        if bres:
            print("Found bres using urllib:")
            for a in bres.find_all('a'):
                text = a.get_text(separator=' ', strip=True)
                if text:
                    print(f" - {text}")
        else:
            print("No bres found.")
except Exception as e:
    print(e)
