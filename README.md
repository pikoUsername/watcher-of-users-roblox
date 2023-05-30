Про что бот 
-----------
Бот сделан для обхода аунтентификации сайта [роблокса](www.roblox.com), и для последующей 
покупки Робуксов, ничего больше. Не перечисление родуксов на аккаунт в тг боте, 
только для покупки геймпассов, и ничего больше.

Но должна выдерживать нагрузку в 20 RPS в секунду. Что сделать крайне трудно,
с учетом отсутвия асинхронных вебдрайверов для браузеров. Обычный запрос занимает 
6 секунд со средним интернетом. и 2 секунды на сервере.

Спецификация 
------------
Для коммуникации с этим скриптом нужен реббитмкью. Значение канала для доступа: 
```
queue_name="url_queue" 
exchange_key="url"
routing_key="url_queue"
exchange_type="direct"
```
Схему которую вы должны отправить в очередь "url_queue":
```json
{
    "url": "<your_url_here>",
    "price": 99999
} 
```
Таблица в БД с именем указанным в переменной окружении - `db_tokens_table` должна иметь следующую 
структуру, если её нету то скрипт создаст её сам: 
```sql
CREATE TABLE IF NOT EXISTS {model_name_here} (
    id SERIAL PRIMARY KEY,
    token TEXT,
    is_active BOOLEAN DEFAULT true
);
```
Также имеется второя очередь которая отправляет отправителю Ошибку транзакции, если 
робуксы не возможно купить, таким образом предовращая ошибочное списание средств. 
Спецификация очереди, отправляется один тип данных - ReturnSignal: 
```json5
{
  "errors": [],  // тип ошибок - list<SendError> 
  "status": 200, // возвращается несколько состояния, см. app/schemas.py StatusCodes   
  "info": ""  // дополнительная информация 
} 
```
`SendError`: 
```json5
{ 
  "name": "str",  // имя исключения 
  "info": ""  // Информация от исключения 
} 
```
Также имя очереди, и роутинг кей теже как и в переменной окружения `queue_name`, 
но добовляется "_return" если не указано `send_queue_name`. 

Статус Коды: 
 - 200 - Успех
 - 500 - Внутренная проблема
 - 401 - Геймпасс уже куплен
 - 400 - не правильные данные
 - 402 - Не имеется доступных токенов которые могут купить этот геймпасс. 
 - 403 - Неправильная цена

Замечания
------------

1) Если у вас выходит такая ошибка как 
`RETURN CHANNEL UNEXPECTEDLY CLOSED BY PEER, TRY TO INCREASE HEARTBEAT`
То попробуйте добавить в queue_dsn параметр соединения как `heartbeat` и 
установите её значение больше 30 секунд, так как обработка сообщения может занять даже 20 секунд при 
медленном интернет подключении(ну или при баге). 

2) При мультитрединг режиме могут возникнуть ошибки при закрытии, игнорируйте. 
3) Также игнорируйте warning-и при однопоточном режиме. 

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
$ python3 -m pip install poetry  
$ python3 -m poetry install 
```
После этого переименовываем .env.dist в .env, вводим 
в неё все данные db_dsn, queue_dsn, там указываете по шаблону 
юзернеймы пароли, и т.д. После этого можно запускать: 
```shell
python3 -m app 
```

Настройка 
------------
Предаварительно надо настроить докер на машине(НЕ СДЕЛАНО)
```shell
$ docker-compose up app 
```

TODO 
--------------
- Избавиться от сложной установки, и впихнуть это все на докер. Что бы можно было 
запустить одной коммандой - ```docker-compose up app```(сделано)
- Полноценная оброботка ошибок(не сделано)
- Мултитрединг(альфа)
