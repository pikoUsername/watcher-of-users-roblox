Установка
------------
Сперва на перво надо запускать это все в wsl. или на сервере со linux. 
Потом установить postgres, и rabbitmq. Потом надо установить headless браузер. 
По инструкции ниже. 
```shell
$ sudo apt-get update
$ sudo apt-get install -y unzip openjdk-8-jre-headless xvfb libxi6 libgconf-2-4 python3.10 python3.10-venv 
```
После установки. Переходим в режим `sudo` с помощью sudo -i 
```shell
# Установка Headless хрома 
$ sudo curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add
$ sudo echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
$ sudo apt-get -y update
$ sudo apt-get -y install google-chrome-stable
$ wget -N https://chromedriver.storage.googleapis.com/79.0.3945.36/chromedriver_linux64.zip -P ~/
$ unzip ~/chromedriver_linux64.zip -d ~/
$ rm ~/chromedriver_linux64.zip
$ sudo mv -f ~/chromedriver /usr/local/bin/chromedriver
$ sudo chown root:root /usr/local/bin/chromedriver
$ sudo chmod 0755 /usr/local/bin/chromedrive
```
После этого создаем виртуальное окуржение: 
```shell 
$ python3 -m venv venv 
$ . ./venv/bin/activate 
$ python3 -m pip install pipenv 
$ python3 -m pipenv install 
```
После этого переименовываем .env.dist в .env, вводим 
в неё все данные db_dsn, queue_dsn, там указываете по шаблону 
юзернеймы пароли, и т.д. После этого можно запускать: 
```shell
python3 -m app 
```

TODO 
--------------
- Избавиться от сложной установки, и впихнуть это все на докер. Что бы можно было 
запустить одной коммандой - ```docker-compose up app```(не сделано)
- Полноценная оброботка ошибок(не сделано)
- Мултитрединг(не сделано)
