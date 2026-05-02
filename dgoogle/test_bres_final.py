from selenium_driver import SeleniumDriver
from bs4 import BeautifulSoup
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

url = 'https://www.google.com/search?q=hello&gl=us'
sd = SeleniumDriver(start_url=url)
driver = sd.driver
try:
    print("Waiting for bres...")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'bres')))
    print("bres found!")
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    bres = soup.find(id='bres')
    
    # Let's inspect the tags under bres
    items = []
    # Usually related searches are 'a' tags or some specific div
    for a in bres.find_all('a'):
        text = a.get_text(separator=' ', strip=True)
        if text:
            items.append(text)
    
    print("Extracted texts from 'a' tags under bres:")
    for item in set(items):
        print(f" - {item}")

except Exception as e:
    print(f"Failed: {e}")

finally:
    driver.quit()
