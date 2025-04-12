from selenium_driver import SeleniumDriver

class DriverManager:
  def __init__(self, driver_count:int=1):
    self.driver = SeleniumDriver().set_up()

  def restart_driver(self, driver):
    driver.quit()
    driver = SeleniumDriver().set_up()
    return driver

  def get_current_port(self, driver):
    service = driver.service

    service_url = service.service_url

    _, _, port = service_url.split(':')

    print(f"Current port: {port}")

    return int(port)
  def quit_driver(self, driver):
    driver.quit()

if __name__ == "__main__":
  driver_manager = DriverManager()
  driver = driver_manager.get_available_driver()
  driver = driver_manager.restart_driver(driver)
