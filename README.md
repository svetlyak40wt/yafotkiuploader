Загрузчик фотографий в Яндекс Фотки
===================================

Это скрипт предназначен для закачивания фотографий на сервис
Яндекс.Фотки (http://fotki.yandex.ru). Программа неофициальная,
и Яндекс не занимается ее поддержкой и распространением.

Помимо command-line интерфейса, `yafotki` так же являются оберткой
вокруг фоточного API. Этот модуль может быть использован из других
программ на Python для управления альбомами и фотографиями.


Установка
---------

Сначала необходимо создать виртуальное окружение и установить в него
необходимые библиотеки:

    python virtualenv.py env
    env/bin/pip install -r requirements.txt
    . env/bin/activate

Если вы хотите, чтобы теги, название и описание фотографии
брались из Exif и Iptc тегов, то вам так же понадобится
библиотека python-pyexiv2.

В Linux системах, основанных на Debian, эти пакеты устанавливаются
очень просто:

    apt-get install python-pyexiv2


Использование
-------------

Перед использованием программы, необходимо авторизоваться:

    ./yaploader auth --username some-yandex-login

Программа запросит ваш пароль на Яндексе. Но сам пароль нигде
не будет сохранен. Вместо него на диске, в файле `~/.fotki.token`,
будет сохранен специальный ключ, предоставляющий доступ только
к сервису Яндекс.Фотки.

Программа поддерживает допольно много команд по управлению альбомами
и фотографиями.

Доступ к альбомам осуществляется по номеру альбома. Например, чтобы
загрузить фотографию в конкретный альбом, следует выполнить команду:

    ./yaploader albums

Она выдаст примерно список альбомов:

    1) "Умолчательный альбом", 21 image(s)
    2) "Screenshots", empty
    3) "Пейзажи", 16 image(s)

Далее, можно воспользоваться командой `upload`:

    ./yaploader upload -a 3 forest.jpg sunset.jpg

В этом примере, мы загружаем два снимка в альбом "Пейзажи".
Обратите внимание, что при этом указывается его номер. Номер
альбома непостоянен, и может измениться при удалении какого-либо другого
альбома. Так что перед загрузкой полезно запросить список альбомов
и уточнить номер.

Многие команды позволяют задавать дополнительные параметры. Чтобы узнать,
какие именно, пользуйтесь встроенной справкой: `./yaploader --help` или
`./yaploader имя-команды --help`.


Настройки по-умолчанию
----------------------

Некоторые настройки "по-умолчанию" можно хранить в конфиге. Для этого
создайте в домашней директории файл .fotki.conf. Конфиг может содержать
такие опции:

    # доступ к фоточке может тах же быть friends или private
    access_type = public
    # закрыть доступ к фотографии по URL со страниц вне домена Яндекс.Фоток
    storage_private = no
    # отключить комментарии
    disable_comments = no
    # только для взрослых
    xxx = no
    # не показывать оригинал
    hide_original = no

Специальные спасибы
-------------------

  * [Григорию Бакунову](https://github.com/bobuk) - за многие доработки на начальном этапе развития проекта.
  * [Денису Барову](https://github.com/fordindin) — за пулл реквест с исправлением проблем с кодировкой и pyexiv2.

Как попасть в список специальных спасибов
-----------------------------------------

Сделать это очень просто. Достаточно форкнуть репозиторий, сделать полезные изменения,
проверить, что ничего при этом не сломалось, прислать pull-request.

Если кодить лень, а поблагодарить хочется, то можно [зафлэттерить этот проект](https://flattr.com/thing/672499) на сервисе Flattr:  
[![](http://media.svetlyak.ru/flattr.png)](https://flattr.com/thing/672499)

Список изменений:
----------------

### Версия 0.3.0

  * Авторизация по OAuth, с сохранением токена.
  * Все операции производятся через JSON API Яндекс.Фоток.
  * Библиотека переименована в `yafotki`, а сама утилита в `yaploader`.
  * Появились две дополнительные зависимости: [anyjson](http://pypi.python.org/pypi/anyjson/)
    и [requests](http://pypi.python.org/pypi/requests/).

### Версия 0.2.5

  * Код загрузчика выделен в отдельную библиотеку YaFotki,
    к которой можно "прикрутить" любой пользовательский интерфейс.
  * Сама консольная программа переименована в yafotki.
  * Параметр --upload больше не нужен, можно просто указывать
    список файлов или маску.
  * Номера альбомов приняли более человеческий вид, и теперь их
    легко запомнить.
  * Номер альбома, который будет использоваться по умолчанию,
    теперь можно указать в конфиге
  * Исправлена ошибка, возникающая при загрузке картинок с прописаными
    русскоязычными тегами или заголовком.

### Версия 0.2.4

  * Исправлена загрузка картинок, больших чем 128 килобайт.
  * Удалена лишняя зависимость от BeautifulSoup.

### Версия 0.2.3

  * Сохранение настроек в конфиге ~/.fotki.conf.
  * Запоминание куки, чтобы не вводить пароль каждый раз.
  * Запрос пароля в интерактивном режиме, через getpass.
  * Авторизация через HTTPS.

### Версия 0.2.2

  * Исправлена ошибка, возникающая при отсутствующем pyexiv2.
  * Скрипт больше не создает временных файлов на диске.