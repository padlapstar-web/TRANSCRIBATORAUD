# TRANSCRIBATORAUD

TRANSCRIBATORAUD — офлайн-приложение для пакетной транскрибации аудио с
таймкодами слов. Репозиторий подготовлен для дальнейшей реализации CLI и GUI
на базе PySide6 и faster-whisper.

## Возможности MVP

- Пакетная обработка отдельных файлов, папок и масок с опцией рекурсивного
  поиска.
- Работа с локальными моделями Whisper (без сети).
- Экспорт результатов в форматы JSONL, CSV, WebVTT, SRT и LRC.
- Параллельная обработка и отчёт об ошибках.

## Структура проекта

```
TRANSCRIBATORAUD/
├── app/
│   ├── main.py             # запуск GUI по умолчанию, CLI при наличии аргументов
│   ├── cli.py              # полноценный CLI для пакетной транскрибации
│   ├── ui/
│   │   ├── main_window.py  # полноценное окно PySide6 с запуском батчей
│   │   └── dialogs.py      # вспомогательные диалоги (заготовка)
│   └── core/
│       ├── asr.py          # интеграция faster-whisper с таймкодами слов
│       ├── exporter.py     # сохранение слов в JSONL/CSV/VTT/SRT/LRC
│       ├── batch.py        # сканирование входов и параллельная обработка
│       ├── audio.py        # утилиты ffprobe и фильтр форматов
│       ├── models.py       # поиск локальных моделей
│       ├── config.py       # YAML-конфиг последних настроек
│       └── logging.py      # ротация логов по дням
├── resources/
│   └── ffmpeg/
│       └── .gitkeep        # место для ffmpeg и ffprobe
├── requirements.txt        # основные зависимости
├── LICENSE                 # MIT
└── .github/workflows/build.yml
```

## Быстрый старт (разработка)

> Требуется Python 3.12 из [python.org](https://www.python.org). Дистрибутивы Anaconda/Miniconda не поддерживаются.

### Один скрипт

Bootstrap-скрипты создают виртуальное окружение `.venv`, устанавливают зависимости, скачивают ffmpeg (через
`scripts/fetch_assets.py`, файлы остаются вне git) и выполняют smoke-сборку PyInstaller.

```bash
# Linux / macOS
bash scripts/bootstrap.sh
```

```powershell
# Windows
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -PythonBin "C:\Python312\python.exe"
```

После завершения активируйте окружение и запускайте приложение вручную:

```bash
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
python app/main.py               # GUI запускается по умолчанию
```

## Сборка EXE локально

Если Windows жалуется на исполнение скриптов, перед запуском можно разово выполнить
`Set-ExecutionPolicy Bypass -Scope Process -Force`.

Для сборки десктопного EXE используется скрипт `build/RunMe.ps1` (для двойного клика есть обёртка `build/RunMe.bat`).
Скрипт строго ищет Python 3.12 из python.org, собирает проект через bootstrap и оставляет готовый бинарь в `dist/`.
Каталог `dist/` находится в `.gitignore`, поэтому артефакты сборки нельзя коммитить.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build\RunMe.ps1

# Полная пересборка
powershell -NoProfile -ExecutionPolicy Bypass -File .\build\RunMe.ps1 -Clean
```

После выполнения EXE доступен по пути `dist\TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe`. Проверь работу, но не добавляй артефакты
в историю репозитория.

> После каждой сборки выполняй `git status` — рабочее дерево должно оставаться чистым.

## GUI (минимально рабочий)

Готовый EXE (`dist/TRANSCRIBATORAUD/TRANSCRIBATORAUD.exe`) или запуск `python app/main.py`
открывают окно с минимальным набором настроек:

- **Вход** — путь к файлу, папке или маске (`*.wav`). Вручную можно прописать glob.
- **Recursive** — рекурсивный обход подпапок.
- **Model / Device / Compute type / Language** — параметры faster-whisper.
- **Output formats** — галочки форматов (JSONL, CSV, WebVTT, SRT; минимум один).
- **Output directory** — целевая папка, по умолчанию `out/` в корне проекта.
- **Transcribe** — запускает обработку в отдельном потоке, прогресс отражается в статус-баре и логе.
- **Log** — текстовое поле, куда попадают сообщения об очереди, прогрессе, ошибках и итогах.

При первом запуске приложение проверяет `resources/ffmpeg`. Если бинарники отсутствуют,
GUI предложит скачать их через `scripts/fetch_assets.py` и покажет вывод команды в лог.

Результаты сохраняются в выбранной папке под именем `<исходник>.words.<формат>`. После завершения
все элементы управления снова становятся активными.

## GPU/CPU режимы

`faster-whisper` автоматически определяет доступность GPU через `--device`. На чистой ветке оставлены оба сценария:

- **GPU (CUDA)** — укажи `--device cuda` и подходящий `--compute_type float16`, чтобы использовать видеокарту NVIDIA.
- **CPU** — используй `--device cpu` и `--compute_type int8_float16` или `int8`, если памяти немного.

Переключение доступно как в CLI (`python app/cli.py --device ...`), так и в GUI через соответствующие выпадающие списки. При отсутствии GPU приложение автоматически падает обратно на CPU.

## FFmpeg — только локальная загрузка

FFmpeg и ffprobe нужны для проверки и конвертации аудио, но бинарники запрещено хранить в git. Скрипт `scripts/fetch_assets.py`
скачивает и проверяет SHA256 нужных архивов, распаковывает их в `resources/ffmpeg/` и оставляет единственный отслеживаемый файл
`.gitkeep`. Если потребуется обновление версии, измени URL и контрольные суммы в скрипте — пользователи чистой ветки всегда
получат свежие бинарники локально, не засоряя историю.


По умолчанию запускается рабочий GUI. Для CLI доступна полноценная утилита:

```bash
python app/cli.py --input ./samples --recursive --formats jsonl,csv,vtt \
  --model small --device cuda --compute_type float16 --language ru --parallel 2
```

Ключевые флаги CLI:

- `--input` — файл, папка или маска (`*.wav`).
- `--out` — папка для результатов (по умолчанию рядом с входом).
- `--recursive` — рекурсивный поиск в каталогах.
- `--formats` — перечисление форматов экспорта (`jsonl,csv,vtt,srt,lrc`).
- `--model`, `--device`, `--compute_type`, `--language` — параметры ASR.
- `--beam-size`, `--parallel` — управление качеством и параллельностью.
- `--keep-punct/--no-keep-punct`, `--vad`, `--skip-existing` — дополнительные опции.

Форматы вывода:

- **JSONL** — одна строка = одно слово: `{"i":1,"start":0.512,"end":0.840,"word":"пример","prob":0.93}`.
- **CSV** — заголовок `i,start,end,word,prob` и строки со значениями.
- **WebVTT** — по одному слову на cue (`00:00:00.000 --> 00:00:00.500`).
- **SRT** — одно слово на субтитр (`00:00:00,000 --> 00:00:00,500`).
- **LRC** — enhanced LRC с метками `[mm:ss.xx]` и переносом строк до 5 секунд.

## PR-флоу

1. Создайте новую ветку с префиксом `codex/` для каждой задачи.
2. Вносите правки и запускайте тесты (по мере их появления) локально.
3. Зафиксируйте изменения в git (`git commit`).
4. Вызовите `make_pr` и передайте заголовок и описание PR.

Если `make_pr` запущен до коммита, инструмент вернёт ошибку и PR создан не
будет.

## Лицензия

Проект распространяется на условиях лицензии MIT. См. файл [LICENSE](LICENSE).
