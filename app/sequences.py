from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By

from .config import Settings
from .puller import IListener


def auth(browser: Chrome, config: Settings):
    """
    Redirects to home page

    :param browser:
    :param config:
    :return:
    """
    browser.get("https://www.roblox.com/game-pass/19962432/unnamed")
    browser.add_cookie({"name": ".ROBLOSECURITY", "value": config.roblox_token, "domain": "www.roblox.com"})
    elemt = browser.find_element(By.CLASS_NAME, "rbx-navbar-login")
    link = elemt.get_attribute("href")
    browser.get(link)


class UrlHandler(IListener):
    def __init__(self, driver: Chrome):
        self.driver = driver

    def __call__(self, data: dict):
        url = data.pop("url")
        driver = self.driver

        driver.get(url)
        # finds a buy button element
        btn = driver.find_element(By.CLASS_NAME, "PurchaseButton")
        btn.click()
