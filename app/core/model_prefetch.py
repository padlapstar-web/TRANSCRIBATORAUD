import os
import logging
from typing import Callable, Optional
from huggingface_hub import snapshot_download

log = logging.getLogger(__name__)

# Порядок нужных файлов в снэпшоте
FILES = ["model.bin", "tokenizer.json", "config.json", "README.md"]


def _make_tqdm_class(on_progress: Optional[Callable[[int, int], None]]):
    """
    Возвращает корректный tqdm_class для huggingface_hub.
    Класс (НЕ инстанс!), с update/close, контекст-менеджером и write().
    По update(...) прокидываем прогресс в UI.
    """
    if on_progress is None:
        return None  # пусть hub сам выберет дефолтный tqdm

    class UiTqdm:
        def __init__(self, total: Optional[int] = None, **kwargs):
            self.total = int(total or 0)
            self.n = 0

        # то, на что рассчитывает hub при логах
        @classmethod
        def write(cls, s: str, **kwargs):
            # без вывода — все сообщения видны в нашем логе
            log.debug(str(s))

        def update(self, n: int = 1):
            self.n += int(n or 0)
            if self.total > 0:
                try:
                    on_progress(self.n, self.total)
                except Exception:  # не роняем загрузку из-за UI
                    log.exception("progress callback failed")

        def close(self):
            pass

        # контекст-менеджер
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False

    return UiTqdm


def ensure_model(
    repo_id: str,
    local_dir: str,
    on_status: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> str:
    # ускорители скачивания
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
    os.environ.setdefault("HF_HUB_ENABLE_XET", "1")

    os.makedirs(local_dir, exist_ok=True)

    def _status(msg: str):
        if on_status:
            try:
                on_status(msg)
            except Exception:
                log.exception("status callback failed")
        log.info(msg)

    _status("Подключение к Hugging Face…")

    try:
        path = snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            local_dir_use_symlinks=False,
            allow_patterns=FILES,
            resume_download=True,
            max_workers=4,
            tqdm_class=_make_tqdm_class(on_progress),
        )
    except Exception as e:
        log.exception("snapshot_download failed")
        raise

    # контроль целостности
    missing = [
        f for f in ("model.bin", "tokenizer.json", "config.json")
        if not os.path.isfile(os.path.join(path, f))
    ]
    if missing:
        raise RuntimeError(
            "Модель скачана не полностью: " + ", ".join(missing)
        )

    return path
