from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _StubTqdm:
    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - trivial
        pass

    def __enter__(self):  # pragma: no cover - trivial
        return self

    def __exit__(self, *exc_info):  # pragma: no cover - trivial
        return False

    def update(self, _value: int) -> None:  # pragma: no cover - trivial
        pass


_tqdm_module = types.ModuleType("tqdm")
_tqdm_module.tqdm = _StubTqdm
sys.modules.setdefault("tqdm", _tqdm_module)

_tqdm_auto = types.ModuleType("tqdm.auto")
_tqdm_auto.tqdm = _StubTqdm
sys.modules.setdefault("tqdm.auto", _tqdm_auto)

