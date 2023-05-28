from seleniumwire.webdriver import Chrome


class BasePage(object):
    """Base class to initialize the base page that will be called from all
    pages"""

    url = ""

    def __init__(self, driver: Chrome):
        self.driver = driver

    def go(self):
        if self.driver.current_url != self.url:
            self.driver.get(self.url)
