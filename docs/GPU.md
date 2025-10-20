# Использование GPU через WSL2

## Требования

- Windows 10/11 с включённой подсистемой Windows для Linux 2 (WSL2).
- Драйвер NVIDIA, поддерживающий WSL (см. https://developer.nvidia.com/cuda/wsl).
- Дистрибутив Ubuntu 22.04 в WSL2.

## Установка окружения внутри WSL2

```bash
wsl --install -d Ubuntu-22.04
wsl -d Ubuntu-22.04
sudo apt update && sudo apt install -y python3-pip ffmpeg
python3 -m pip install --upgrade pip
python3 -m pip install faster-whisper ctranslate2
```

## Запуск приложения

```bash
cd /mnt/c/Path/To/TRANSCRIBATORAUD
python3 -m app --device=cuda --compute-type=float16
```

## Советы

- На Windows без WSL2 CUDA не поддерживается — приложение автоматически переключится на CPU.
- Для оффлайн-режима установите переменную `TRANSCRIBATORAUD_OFFLINE=1` или используйте соответствующий флаг CLI/GUI.
- Убедитесь, что `ffmpeg` установлен внутри WSL2.
