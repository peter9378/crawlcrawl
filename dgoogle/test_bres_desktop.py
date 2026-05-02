from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

options = Options()
options.add_argument('--headless')
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

driver = webdriver.Chrome(options=options)
driver.get('https://www.google.com/search?q=hello&gl=us')

time.sleep(3)
html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')
bres = soup.find(id='bres')
if bres:
    print("Found bres!")
    links = bres.find_all('a')
    for a in links:
        print(a.get_text(separator=' ', strip=True))
    with open('desktop_bres.html', 'w') as f:
        f.write(bres.prettify())
else:
    print("No bres found on desktop layout.")
    
driver.quit()
