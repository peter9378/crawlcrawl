from bs4 import BeautifulSoup

html = """
<html><body>
<div id="bres">
    <div>
        <a href="/search?q=hello+kitty">hello kitty</a>
    </div>
    <div>
        <a href="/search?q=hello+world">
            <div class="test">hello world</div>
        </a>
    </div>
    <div>
        <a href="/search?q=hello+adele">hello adele</a>
    </div>
    <!-- Duplicate to verify uniqueness -->
    <div>
        <a href="/search?q=hello+kitty">hello kitty</a>
    </div>
</div>
</body></html>
"""
soup = BeautifulSoup(html, 'html.parser')
bres_div = soup.find(id='bres')
new_results = []
if bres_div:
    seen = set()
    for a in bres_div.find_all('a'):
        text = a.get_text(separator=' ', strip=True)
        if text and text not in seen:
            seen.add(text)
            new_results.append({"searchType": "pc", "relatedKeyword": text})

print(new_results)
