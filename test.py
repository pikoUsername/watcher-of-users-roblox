import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from dotenv import load_dotenv

from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import pika


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


def second_main():
    load_dotenv()

    params = pika.URLParameters(os.environ["queue_dsn"])
    conn = pika.BlockingConnection(params)

    channel = conn.channel()

    channel.queue_declare(os.environ["queue_name"])

    print(os.environ["queue_name"], ", Published a data")

    for _ in range(10):
        channel.basic_publish(
            exchange="url",
            routing_key=os.environ["queue_name"],
            body=b'{"url": "https://www.roblox.com/game-pass/19962432/unnamed/"}',
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=pika.DeliveryMode.Transient),
        )

    conn.close()


if __name__ == "__main__":
    second_main()
