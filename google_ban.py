from selenium.webdriver import Chrome, ChromeOptions as Options
from selenium.webdriver.common.by import By
if __name__ == '__main__':
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = Chrome(options=options)
    driver.get('https://www.google.com/search?q=%EA%B0%88%EB%B9%84%ED%83%95&oq=%EA%B0%88%EB%B9%84%ED%83%95&gs_lcrp=EgZjaHJvbWUqDQgAEAAY4wIYsQMYgAQyDQgAEAAY4wIYsQMYgAQyCggBEC4YsQMYgAQyBwgCEAAYgAQyBwgDEAAYgAQyBwgEEAAYgAQyBwgFEAAYgAQyBwgGEAAYgAQyBggHEEUYPNIBCDI2MDFqMGo3qAIAsAIA&sourceid=chrome&ie=UTF-8')

    print(driver.find_element(By.ID, 'search').text)
    driver.quit()