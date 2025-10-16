# TRANSCRIBATORAUD

## Локальная сборка EXE (Windows)
1) Установи Python 3.11 x64.
2) В PowerShell в корне проекта:
   ```powershell
   .\build\build.ps1 -Device cuda -ComputeType float16   # или -Device cpu -ComputeType int8
   ```
   Скрипт сам:
   - создаст/активирует venv;
   - поставит зависимости + PyInstaller;
   - локально сгенерирует ffmpeg/ffprobe в `resources\ffmpeg` (без коммитов в репо);
   - соберёт EXE в `dist_TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe`.
3) Запуск:
   ```powershell
   .\dist_TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe --help
   ```


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
│   │   ├── main_window.py  # каркас основного окна
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

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app/main.py
```

По умолчанию запускается GUI-заготовка. Для CLI доступна полноценная утилита:

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
