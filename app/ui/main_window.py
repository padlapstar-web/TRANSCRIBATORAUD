"""Main window implementation for the TRANSCRIBATORAUD GUI."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from app.core.batch import discover_inputs
from app.core.ffmpeg import find_ffmpeg
from app.core.models import resolve_repo_id
from app.core.paths import MODELS_DIR
from app.core.worker import JobConfig, TranscribeWorker
from app.diagnostics.runtime_info import check_hf_cdn

try:  # pragma: no cover - optional dependency at runtime
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
except ImportError:  # pragma: no cover - executed when PySide6 is not installed
    QtCore = QtGui = QtWidgets = QDesktopServices = QUrl = None  # type: ignore[misc,assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "out"
_LOGGER = logging.getLogger(__name__)


if QtWidgets is None or QtCore is None or QtGui is None:  # pragma: no cover

    def launch_gui(argv: Optional[Sequence[str]] = None) -> int:
        """Fallback when PySide6 is unavailable."""

        print(
            "PySide6 не найден. Установите зависимости (pip install -r requirements.txt) "
            "или используйте CLI: python app/cli.py ...",
            file=sys.stderr,
        )
        return 1


else:

    class ModelPrefetchThread(QtCore.QThread):
        finished = QtCore.Signal(bool, str)
        status = QtCore.Signal(str)
        progress = QtCore.Signal(int, int)

        def __init__(self, model_selector: str, parent: Optional[QtCore.QObject] = None) -> None:
            super().__init__(parent)
            self._model_selector = model_selector

        def run(self) -> None:  # type: ignore[override]
            try:
                repo_id = resolve_repo_id(self._model_selector)
                target_dir = MODELS_DIR / repo_id.replace("/", "__")

                from app.core.model_prefetch import ensure_model

                def _status(message: str) -> None:
                    self.status.emit(message)

                def _progress(done: int, total: int) -> None:
                    self.progress.emit(int(done), int(total))

                local_path = ensure_model(
                    repo_id,
                    str(target_dir),
                    on_status=_status,
                    on_progress=_progress,
                )
                self.finished.emit(True, str(local_path))
            except Exception:  # pragma: no cover - network/filesystem issues
                import traceback

                self.finished.emit(False, traceback.format_exc())


    class MainWindow(QtWidgets.QMainWindow):
        """Main GUI window for TRANSCRIBATORAUD."""

        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("TRANSCRIBATORAUD")
            self.resize(920, 680)

            self._worker: Optional[TranscribeWorker] = None
            self._prefetch_thread: Optional[ModelPrefetchThread] = None
            self._ffmpeg_checked = False
            self._ffmpeg_path: Optional[Path] = None
            self._worker_had_errors = False
            self._log_file_path: Optional[Path] = None
            self._open_logs_action: Optional[QtGui.QAction] = None
            self._cdn_checked = False
            self._showing_download_progress = False
            self._pending_progress_reset = False

            self._build_ui()
            self._ensure_output_dir()
            self.statusBar().showMessage("Готово к запуску")

        def _build_ui(self) -> None:
            central = QtWidgets.QWidget(self)
            self.setCentralWidget(central)
            layout = QtWidgets.QVBoxLayout(central)

            form_layout = QtWidgets.QFormLayout()
            layout.addLayout(form_layout)

            # Input controls
            self.input_edit = QtWidgets.QLineEdit()
            self.input_edit.setPlaceholderText("Путь к файлу/папке или glob-маска (*.wav)")
            self.browse_input_button = QtWidgets.QPushButton("Browse…")
            input_row = QtWidgets.QHBoxLayout()
            input_row.addWidget(self.input_edit)
            input_row.addWidget(self.browse_input_button)
            form_layout.addRow("Вход:", input_row)

            self.recursive_checkbox = QtWidgets.QCheckBox("Искать рекурсивно")
            form_layout.addRow("", self.recursive_checkbox)

            # Model & inference options
            self.model_combo = QtWidgets.QComboBox()
            for value in ["tiny", "base", "small", "medium", "large"]:
                self.model_combo.addItem(value)
            self.model_combo.setCurrentText("small")
            self.prefetch_button = QtWidgets.QPushButton("Скачать модель сейчас")
            self.prefetch_status = QtWidgets.QCheckBox("Модель скачана локально")
            self.prefetch_status.setEnabled(False)
            model_row = QtWidgets.QHBoxLayout()
            model_row.addWidget(self.model_combo)
            model_row.addWidget(self.prefetch_button)
            model_row.addWidget(self.prefetch_status)
            form_layout.addRow("Модель:", model_row)

            self.device_combo = QtWidgets.QComboBox()
            for value in ["cpu", "cuda", "auto"]:
                self.device_combo.addItem(value)
            self.device_combo.setCurrentText("auto")
            form_layout.addRow("Устройство:", self.device_combo)

            self.compute_combo = QtWidgets.QComboBox()
            for value in ["int8", "int8_float32", "float16"]:
                self.compute_combo.addItem(value)
            self.compute_combo.setCurrentText("int8")
            form_layout.addRow("Compute type:", self.compute_combo)

            self.language_combo = QtWidgets.QComboBox()
            for value in ["auto", "ru", "en"]:
                self.language_combo.addItem(value)
            form_layout.addRow("Язык:", self.language_combo)

            # Local model override
            self.local_model_checkbox = QtWidgets.QCheckBox("Использовать локальную модель (без загрузки)")
            form_layout.addRow("", self.local_model_checkbox)

            self.local_model_edit = QtWidgets.QLineEdit()
            self.local_model_edit.setPlaceholderText("Каталог модели (model.bin*)")
            self.local_model_browse = QtWidgets.QPushButton("Browse…")
            local_row = QtWidgets.QHBoxLayout()
            local_row.addWidget(self.local_model_edit)
            local_row.addWidget(self.local_model_browse)
            form_layout.addRow("Папка модели:", local_row)
            self.local_model_edit.setEnabled(False)
            self.local_model_browse.setEnabled(False)

            # Output formats
            self.format_checkboxes: dict[str, QtWidgets.QCheckBox] = {}
            formats_layout = QtWidgets.QHBoxLayout()
            for fmt in ["jsonl", "csv", "vtt", "srt"]:
                checkbox = QtWidgets.QCheckBox(fmt.upper())
                checkbox.setChecked(fmt == "jsonl")
                formats_layout.addWidget(checkbox)
                self.format_checkboxes[fmt] = checkbox
            formats_layout.addStretch(1)
            form_layout.addRow("Форматы:", formats_layout)

            # Output directory
            self.output_edit = QtWidgets.QLineEdit(str(DEFAULT_OUTPUT_DIR))
            self.output_browse_button = QtWidgets.QPushButton("Browse…")
            output_row = QtWidgets.QHBoxLayout()
            output_row.addWidget(self.output_edit)
            output_row.addWidget(self.output_browse_button)
            form_layout.addRow("Папка вывода:", output_row)

            # Run/cancel controls
            self.run_button = QtWidgets.QPushButton("Transcribe")
            self.cancel_button = QtWidgets.QPushButton("Отмена")
            self.cancel_button.setEnabled(False)
            run_row = QtWidgets.QHBoxLayout()
            run_row.addWidget(self.run_button)
            run_row.addWidget(self.cancel_button)
            layout.addLayout(run_row)

            # Progress and log
            self.progress_bar = QtWidgets.QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setVisible(False)
            layout.addWidget(self.progress_bar)

            self.log_output = QtWidgets.QPlainTextEdit()
            self.log_output.setReadOnly(True)
            layout.addWidget(self.log_output, stretch=1)

            self._interactive_widgets: List[QtWidgets.QWidget] = [
                self.input_edit,
                self.browse_input_button,
                self.recursive_checkbox,
                self.model_combo,
                self.prefetch_button,
                self.device_combo,
                self.compute_combo,
                self.language_combo,
                self.local_model_checkbox,
                self.local_model_edit,
                self.local_model_browse,
                self.output_edit,
                self.output_browse_button,
                *self.format_checkboxes.values(),
            ]

            # Signals
            self.browse_input_button.clicked.connect(self._choose_input)
            self.output_browse_button.clicked.connect(self._choose_output)
            self.run_button.clicked.connect(self._start_transcription)
            self.cancel_button.clicked.connect(self._cancel_transcription)
            self.prefetch_button.clicked.connect(self._prefetch_model)
            self.local_model_checkbox.toggled.connect(self._toggle_local_model_mode)
            self.local_model_browse.clicked.connect(self._choose_local_model_dir)

            if hasattr(self, "menuBar"):
                menu_bar = self.menuBar()
                help_menu = menu_bar.addMenu("Help")
                self._open_logs_action = help_menu.addAction("Open logs folder")
                self._open_logs_action.triggered.connect(self._open_logs_folder)
                self._open_logs_action.setEnabled(False)

        def showEvent(self, event: QtGui.QShowEvent) -> None:  # type: ignore[override]
            super().showEvent(event)
            if not self._ffmpeg_checked:
                self._ffmpeg_checked = True
                self._check_ffmpeg()

        def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
            if self._worker and self._worker.isRunning():
                self._worker.stop()
                self._worker.wait(3000)
            super().closeEvent(event)

        def _update_status(self, message: str, timeout: int = 0) -> None:
            self.statusBar().showMessage(message, timeout)

        def _toggle_local_model_mode(self, checked: bool) -> None:
            self._apply_local_model_enabled_state(checked)
            if checked:
                self._append_log("Включён режим использования локальной модели.")
            else:
                self._append_log("Локальная модель отключена, разрешена загрузка из Hugging Face.")

        def _apply_local_model_enabled_state(self, base_enabled: bool | None = None) -> None:
            if base_enabled is None:
                base_enabled = True
            enabled = bool(base_enabled and self.local_model_checkbox.isChecked())
            self.local_model_edit.setEnabled(enabled)
            self.local_model_browse.setEnabled(enabled)

        def _choose_input(self) -> None:
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Выбор аудиофайла",
                str(PROJECT_ROOT),
                "Audio files (*.wav *.mp3 *.flac *.m4a *.ogg);;Все файлы (*)",
            )
            if file_path:
                self.input_edit.setText(file_path)
                return
            directory = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Выбор папки",
                str(PROJECT_ROOT),
            )
            if directory:
                self.input_edit.setText(directory)

        def _choose_output(self) -> None:
            directory = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Папка для результатов",
                str(DEFAULT_OUTPUT_DIR),
            )
            if directory:
                self.output_edit.setText(directory)

        def _choose_local_model_dir(self) -> None:
            directory = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Каталог модели",
                str(PROJECT_ROOT),
            )
            if directory:
                self.local_model_edit.setText(directory)

        def _ensure_output_dir(self) -> None:
            try:
                DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self._append_log(f"Не удалось создать папку вывода: {exc}")

        def _check_ffmpeg(self) -> None:
            self._ffmpeg_path = find_ffmpeg()
            if self._ffmpeg_path:
                self._append_log(f"FFmpeg обнаружен: {self._ffmpeg_path}")
            else:
                self._append_log(
                    "FFmpeg не найден. Установите ffmpeg и добавьте его в PATH или переменные окружения."
                )

        def _append_log(self, message: str) -> None:
            self.log_output.appendPlainText(message)
            _LOGGER.info(message)

        def set_log_file_path(self, path: Path) -> None:
            self._log_file_path = path
            if self._open_logs_action is not None:
                self._open_logs_action.setEnabled(True)

        def _set_controls_enabled(self, enabled: bool) -> None:
            for widget in self._interactive_widgets:
                widget.setEnabled(enabled)
            self.run_button.setEnabled(enabled)
            if enabled:
                self.cancel_button.setEnabled(False)
            else:
                self.cancel_button.setEnabled(True)
            self._apply_local_model_enabled_state(enabled)

        def _open_logs_folder(self) -> None:
            if not self._log_file_path or QDesktopServices is None or QUrl is None:
                return
            directory = self._log_file_path.parent
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

        def _set_download_progress_mode(self, enabled: bool) -> None:
            self._showing_download_progress = enabled
            if enabled:
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setVisible(True)
            elif not (self._worker and self._worker.isRunning()):
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setVisible(False)

        def _handle_prefetch_status(self, message: str) -> None:
            self._append_log(message)
            self._update_status(message)

        def _handle_prefetch_progress(self, done: int, total: int) -> None:
            self._set_download_progress_mode(True)
            if total > 0:
                percent = max(0, min(100, int(done * 100 / total)))
            else:
                percent = 0
            self.progress_bar.setValue(percent)

        def _cancel_transcription(self) -> None:
            if self._worker and self._worker.isRunning():
                self._append_log("Отмена запрошена пользователем…")
                self._update_status("Отмена запрошена…", 3000)
                self._worker.stop()
                self.cancel_button.setEnabled(False)

        def _prefetch_model(self) -> None:
            if self._prefetch_thread and self._prefetch_thread.isRunning():
                return
            selector = self.model_combo.currentText()
            self.prefetch_status.setChecked(False)
            message = f"Скачивание модели {selector}: подключение к Hugging Face…"
            self._append_log(message)
            self._update_status(message)
            self.prefetch_button.setEnabled(False)
            logging.getLogger("huggingface_hub").setLevel(logging.INFO)
            logging.getLogger("app.core.model_prefetch").setLevel(logging.INFO)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self._set_download_progress_mode(True)
            self._prefetch_thread = ModelPrefetchThread(selector, self)
            self._prefetch_thread.status.connect(self._handle_prefetch_status)
            self._prefetch_thread.progress.connect(self._handle_prefetch_progress)
            self._prefetch_thread.finished.connect(self._on_prefetch_finished)
            self._prefetch_thread.start()

        def _on_prefetch_finished(self, success: bool, payload: str) -> None:
            self.prefetch_button.setEnabled(True)
            thread = self._prefetch_thread
            self._prefetch_thread = None
            if thread is not None:
                thread.deleteLater()
            self._set_download_progress_mode(False)
            if not (self._worker and self._worker.isRunning()):
                self.progress_bar.setVisible(False)
                self.progress_bar.setValue(0)
            if success:
                self.prefetch_status.setChecked(True)
                self.progress_bar.setValue(100)
                self._append_log(f"Модель загружена: {payload}")
                self._update_status("Модель готова локально", 5000)
                QtWidgets.QMessageBox.information(
                    self,
                    "Загрузка модели",
                    f"Модель сохранена в {payload}",
                )
            else:
                self.prefetch_status.setChecked(False)
                self._append_log("Ошибка загрузки модели")
                self._append_log(payload)
                self._update_status("Ошибка загрузки модели", 5000)
                QtWidgets.QMessageBox.critical(
                    self,
                    "Загрузка модели",
                    f"Не удалось загрузить модель. Подробности в консоли.",
                )

        def _start_transcription(self) -> None:
            if self._worker and self._worker.isRunning():
                QtWidgets.QMessageBox.information(
                    self,
                    "Транскрибация",
                    "Обработка уже выполняется.",
                )
                return

            source = self.input_edit.text().strip()
            if not source:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Транскрибация",
                    "Укажите путь к файлу, папке или маске.",
                )
                return

            formats = [fmt for fmt, checkbox in self.format_checkboxes.items() if checkbox.isChecked()]
            if not formats:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Транскрибация",
                    "Выберите хотя бы один формат вывода.",
                )
                return

            output_dir = Path(self.output_edit.text().strip() or DEFAULT_OUTPUT_DIR)

            if not self._ffmpeg_path or not self._ffmpeg_path.exists():
                QtWidgets.QMessageBox.critical(
                    self,
                    "FFmpeg",
                    "FFmpeg не найден. Установите ffmpeg и повторите попытку.",
                )
                return

            local_model_dir: Optional[Path] = None
            allow_download = True
            if self.local_model_checkbox.isChecked():
                candidate = Path(self.local_model_edit.text().strip())
                if not candidate.exists():
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Локальная модель",
                        "Каталог модели не найден.",
                    )
                    return
                if not list(candidate.glob("model.bin*")):
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Локальная модель",
                        "В каталоге не найдено файлов model.bin*.",
                    )
                    return
                local_model_dir = candidate
                allow_download = False

            inputs = discover_inputs(Path(source), recursive=self.recursive_checkbox.isChecked())
            if not inputs:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Транскрибация",
                    "Не найдено аудиофайлов для заданного пути.",
                )
                return

            if not self._cdn_checked and allow_download:
                self._append_log("Проверка доступности Hugging Face CDN…")
                cdn_status = check_hf_cdn()
                self._cdn_checked = True
                cdn_issue = False
                for url, status in cdn_status.items():
                    self._append_log(f"{url}: {status}")
                    if status.startswith("ERR") or " 200 " not in status and not status.startswith("200"):
                        if "cdn-lfs" in url:
                            cdn_issue = True
                if cdn_issue:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Hugging Face CDN",
                        "CDN Hugging Face недоступен. Загрузка модели может зависнуть.",
                    )

            self._append_log("Запуск транскрибации (последовательный режим)…")
            self._pending_progress_reset = False
            self.progress_bar.setValue(0)
            self._set_download_progress_mode(True)
            self._set_controls_enabled(False)
            self._update_status("Инициализация модели…")

            init_message = ("Инициализация модели (%s/%s)…" % (self.device_combo.currentText(), self.compute_combo.currentText()))
            self._append_log(init_message)
            self._update_status(init_message)

            config = JobConfig(
                ffmpeg=self._ffmpeg_path,
                files=inputs,
                formats=formats,
                model_name=self.model_combo.currentText(),
                device=self.device_combo.currentText(),
                compute_type=self.compute_combo.currentText(),
                language=self.language_combo.currentText(),
                output_dir=output_dir,
                beam_size=1,
                local_model_dir=local_model_dir,
                allow_download=allow_download,
                offline=not allow_download,
            )

            logging.getLogger("huggingface_hub").setLevel(logging.INFO)
            logging.getLogger("app.core.model_prefetch").setLevel(logging.INFO)

            self._worker_had_errors = False
            self._worker = TranscribeWorker(config, self)
            self._worker.log.connect(self._append_log)
            self._worker.status.connect(self._on_worker_status)
            self._worker.download_progress.connect(self._on_worker_download_progress)
            self._worker.progress.connect(self._on_worker_progress)
            self._worker.done_file.connect(lambda p: self._append_log(f"Готово: {Path(p).name}"))
            self._worker.error.connect(self._handle_worker_error)
            self._worker.finished_all.connect(self._on_worker_finished)
            self._worker.start()

        def _handle_worker_error(self, message: str) -> None:
            first_error = not self._worker_had_errors
            self._worker_had_errors = True
            self._append_log(message)
            self._update_status("Ошибка обработки", 5000)
            if first_error:
                QtWidgets.QMessageBox.critical(self, "Ошибка", message)

        def _on_worker_status(self, message: str) -> None:
            self._append_log(message)
            self._update_status(message)

        def _on_worker_download_progress(self, percent: int) -> None:
            self._set_download_progress_mode(True)
            self.progress_bar.setValue(percent)
            if percent >= 100:
                self._pending_progress_reset = True

        def _on_worker_progress(self, percent: int) -> None:
            if self._pending_progress_reset:
                self._pending_progress_reset = False
                self.progress_bar.setValue(0)
            self._set_download_progress_mode(False)
            self.progress_bar.setValue(percent)

        def _on_worker_finished(self) -> None:
            self._set_controls_enabled(True)
            self.cancel_button.setEnabled(False)
            self._set_download_progress_mode(False)
            self._pending_progress_reset = False
            if self._worker:
                had_error = self._worker.had_error
            else:
                had_error = False
            self.progress_bar.setValue(100 if not had_error else self.progress_bar.value())
            if self._worker:
                self._worker.deleteLater()
            self._worker = None
            if self._worker_had_errors:
                self._append_log("Выполнено с ошибками. Проверьте лог выше.")
                self._update_status("Завершено с ошибками", 5000)
                QtWidgets.QMessageBox.warning(
                    self,
                    "Транскрибация",
                    "Обработка завершилась с ошибками. Детали см. в логе.",
                )
            else:
                self._append_log("Готово: все файлы обработаны успешно")
                self._update_status("Готово", 5000)
                QtWidgets.QMessageBox.information(
                    self,
                    "Транскрибация",
                    "Обработка завершена успешно.",
                )


    def launch_gui(argv: Optional[Sequence[str]] = None) -> int:
        app = QtWidgets.QApplication(list(argv or sys.argv))
        window = MainWindow()
        window.show()
        return app.exec()


__all__ = ["launch_gui"]
