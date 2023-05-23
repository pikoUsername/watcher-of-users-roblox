
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService

from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


def main():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--window-size=%s" % '1920,1080')
    opts.add_argument('--no-sandbox')

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager(path="./drivers/").install()), options=opts)
    driver.get("https://www.google.com")

    try:
        x = driver.find_element(By.ID, "fuck")
    except Exception:
        print("HERE")
        raise

    while 1:
        pass

if __name__ == "__main__":
    main()
