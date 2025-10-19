import sys
import logging


class _LogStream:
    """Поток-пустышка для библиотек, которые пишут в sys.stderr/sys.stdout."""

    def write(self, s: str) -> None:
        s = (s or "").rstrip()
        if s:
            logging.getLogger("ext.stderr").debug(s)

    def flush(self) -> None:
        """Поддержка вызовов flush() от tqdm и других библиотек."""

        # Нам не нужно предпринимать никаких действий, но метод должен существовать.
        return


def hook_gui_streams() -> None:
    """Перенаправляет stderr/stdout в лог, если приложение запущено без консоли."""

    if sys.stderr is None:
        sys.stderr = _LogStream()  # type: ignore[assignment]
    if sys.stdout is None:
        sys.stdout = _LogStream()  # type: ignore[assignment]
