"""Main window implementation for the TRANSCRIBATORAUD GUI."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from app.core.batch import BatchOptions, BatchResult, discover_inputs, process_batch
from app.core.logging import setup_logging

try:  # pragma: no cover - optional dependency at runtime
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover - executed when PySide6 is not installed
    QtCore = QtGui = QtWidgets = None  # type: ignore[misc,assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "out"
_FFMPEG_DIR = PROJECT_ROOT / "resources" / "ffmpeg"
_LOGGER = setup_logging().getChild("gui")


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

    class TranscriptionWorker(QtCore.QObject):
        """Background worker that performs batch transcription."""

        progress = QtCore.Signal(int)
        message = QtCore.Signal(str)
        finished = QtCore.Signal(bool)

        def __init__(
            self,
            source: str,
            recursive: bool,
            output_dir: Path,
            formats: Iterable[str],
            model: str,
            device: str,
            compute_type: str,
            language: str,
            parent: Optional[QtCore.QObject] = None,
        ) -> None:
            super().__init__(parent)
            self._source = Path(source)
            self._recursive = recursive
            self._output_dir = Path(output_dir)
            self._formats = list(formats)
            self._model = model
            self._device = device
            self._compute_type = compute_type
            self._language = language

        @QtCore.Slot()
        def run(self) -> None:
            try:
                inputs = discover_inputs(self._source, recursive=self._recursive)
                if not inputs:
                    raise ValueError("Не найдено аудиофайлов для заданного пути")

                self._output_dir.mkdir(parents=True, exist_ok=True)

                options = BatchOptions(
                    output_dir=self._output_dir,
                    formats=list(self._formats),
                    model=self._model,
                    device=self._device,
                    compute_type=self._compute_type,
                    language=None if self._language.lower() == "auto" else self._language,
                    keep_punct=True,
                    vad=False,
                    beam_size=5,
                    parallel=1,
                    skip_existing=False,
                )

                total = len(inputs)
                processed = 0

                def _emit_status(message: str) -> None:
                    self.message.emit(message)
                    _LOGGER.info(message)

                _emit_status(f"Найдено файлов для обработки: {total}")

                def _progress(path: Path, status: str) -> None:
                    nonlocal processed
                    if status == "queued":
                        _emit_status(f"В очереди: {path.name}")
                    elif status == "processing":
                        _emit_status(f"Обработка: {path.name}")
                    elif status in {"completed", "failed", "skipped"}:
                        processed += 1
                        percent = int(processed * 100 / max(total, 1))
                        self.progress.emit(percent)
                        _emit_status(f"{status.upper()}: {path.name}")

                results = process_batch(inputs, options, progress=_progress)

                failures = [result for result in results if not result.success]
                self._report_results(results)
                self.progress.emit(100)
                self.finished.emit(not failures)
            except Exception as exc:  # pragma: no cover - defensive branch for GUI usage
                self.message.emit(f"Ошибка: {exc}")
                _LOGGER.exception("GUI batch processing failed")
                self.finished.emit(False)

        def _report_results(self, results: List[BatchResult]) -> None:
            for item in results:
                if item.success:
                    exported = ", ".join(
                        f"{fmt} → {path.name}" for fmt, path in item.outputs.items()
                    )
                    self.message.emit(f"✔ {item.source.name}: {exported}")
                elif item.status == "skipped":
                    self.message.emit(f"↷ {item.source.name}: пропущен (файлы уже существуют)")
                else:
                    self.message.emit(
                        f"✖ {item.source.name}: {item.error or 'ошибка обработки'}"
                    )


    class MainWindow(QtWidgets.QMainWindow):
        """Main GUI window for TRANSCRIBATORAUD."""

        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("TRANSCRIBATORAUD")
            self.resize(900, 640)

            self._thread: Optional[QtCore.QThread] = None
            self._worker: Optional[TranscriptionWorker] = None
            self._ffmpeg_checked = False

            self._build_ui()
            self._ensure_output_dir()

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
            form_layout.addRow("Модель:", self.model_combo)

            self.device_combo = QtWidgets.QComboBox()
            for value in ["cpu", "cuda"]:
                self.device_combo.addItem(value)
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

            # Output formats
            self.format_checkboxes: Dict[str, QtWidgets.QCheckBox] = {}
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

            # Run button
            self.run_button = QtWidgets.QPushButton("Transcribe")
            layout.addWidget(self.run_button)

            # Progress and log
            self.progress_bar = QtWidgets.QProgressBar()
            self.progress_bar.setRange(0, 100)
            layout.addWidget(self.progress_bar)

            self.log_output = QtWidgets.QPlainTextEdit()
            self.log_output.setReadOnly(True)
            layout.addWidget(self.log_output, stretch=1)

            self._interactive_widgets: List[QtWidgets.QWidget] = [
                self.input_edit,
                self.browse_input_button,
                self.recursive_checkbox,
                self.model_combo,
                self.device_combo,
                self.compute_combo,
                self.language_combo,
                self.output_edit,
                self.output_browse_button,
                *self.format_checkboxes.values(),
            ]

            # Signals
            self.browse_input_button.clicked.connect(self._choose_input)
            self.output_browse_button.clicked.connect(self._choose_output)
            self.run_button.clicked.connect(self._start_transcription)

        def showEvent(self, event: QtGui.QShowEvent) -> None:  # type: ignore[override]
            super().showEvent(event)
            if not self._ffmpeg_checked:
                self._ffmpeg_checked = True
                self._check_ffmpeg()

        def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
            if self._thread and self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(3000)
            super().closeEvent(event)

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

        def _ensure_output_dir(self) -> None:
            try:
                DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self._append_log(f"Не удалось создать папку вывода: {exc}")

        def _check_ffmpeg(self) -> None:
            if self._ffmpeg_present():
                self._append_log("FFmpeg найден в resources/ffmpeg")
                return

            self._append_log("FFmpeg не найден. Можно скачать локально через fetch_assets.py")
            response = QtWidgets.QMessageBox.question(
                self,
                "FFmpeg",
                "FFmpeg не обнаружен. Скачать и установить?",
            )
            if response == QtWidgets.QMessageBox.StandardButton.Yes:
                self._fetch_ffmpeg()
            else:
                self._append_log("Пропущена загрузка FFmpeg — некоторые файлы могут не обрабатываться")

        def _fetch_ffmpeg(self) -> None:
            script = PROJECT_ROOT / "scripts" / "fetch_assets.py"
            if not script.exists():
                self._append_log("Скрипт fetch_assets.py не найден")
                QtWidgets.QMessageBox.warning(
                    self,
                    "FFmpeg",
                    "Скрипт scripts/fetch_assets.py не найден. Скачивание невозможно.",
                )
                return

            self._append_log("Запуск scripts/fetch_assets.py…")
            try:
                result = subprocess.run(
                    [sys.executable, str(script)],
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=str(PROJECT_ROOT),
                )
                for line in result.stdout.splitlines():
                    self._append_log(line)
                if result.stderr:
                    for line in result.stderr.splitlines():
                        self._append_log(line)
            except subprocess.CalledProcessError as exc:
                self._append_log("Ошибка загрузки FFmpeg")
                if exc.stdout:
                    for line in exc.stdout.splitlines():
                        self._append_log(line)
                if exc.stderr:
                    for line in exc.stderr.splitlines():
                        self._append_log(line)
                QtWidgets.QMessageBox.critical(
                    self,
                    "FFmpeg",
                    "Не удалось скачать FFmpeg. Подробности в логе.",
                )
            else:
                self._append_log("FFmpeg загружен. Проверьте папку resources/ffmpeg")

        def _ffmpeg_present(self) -> bool:
            if not _FFMPEG_DIR.exists():
                return False
            for name in os.listdir(_FFMPEG_DIR):
                if name.lower().startswith("ffmpeg") or name.lower().startswith("ffprobe"):
                    return True
            return False

        def _append_log(self, message: str) -> None:
            self.log_output.appendPlainText(message)

        def _set_controls_enabled(self, enabled: bool) -> None:
            for widget in self._interactive_widgets:
                widget.setEnabled(enabled)
            self.run_button.setEnabled(enabled)

        def _start_transcription(self) -> None:
            if self._thread and self._thread.isRunning():
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

            self._append_log("Запуск транскрибации…")
            self.progress_bar.setValue(0)
            self._set_controls_enabled(False)

            self._thread = QtCore.QThread(self)
            self._worker = TranscriptionWorker(
                source=source,
                recursive=self.recursive_checkbox.isChecked(),
                output_dir=output_dir,
                formats=formats,
                model=self.model_combo.currentText(),
                device=self.device_combo.currentText(),
                compute_type=self.compute_combo.currentText(),
                language=self.language_combo.currentText(),
            )
            self._worker.moveToThread(self._thread)
            self._thread.started.connect(self._worker.run)
            self._worker.progress.connect(self.progress_bar.setValue)
            self._worker.message.connect(self._append_log)
            self._worker.finished.connect(self._on_transcription_finished)
            self._worker.finished.connect(self._thread.quit)
            self._worker.finished.connect(self._worker.deleteLater)
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread.finished.connect(self._clear_thread_references)
            self._thread.start()

        def _clear_thread_references(self) -> None:
            self._thread = None
            self._worker = None

        def _on_transcription_finished(self, success: bool) -> None:
            self._set_controls_enabled(True)
            if success:
                self._append_log("Готово: все файлы обработаны успешно")
                QtWidgets.QMessageBox.information(
                    self,
                    "Транскрибация",
                    "Обработка завершена успешно.",
                )
            else:
                self._append_log("Выполнено с ошибками. Проверьте лог выше.")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Транскрибация",
                    "Обработка завершилась с ошибками. Детали см. в логе.",
                )


    def launch_gui(argv: Optional[Sequence[str]] = None) -> int:
        app = QtWidgets.QApplication(list(argv or sys.argv))
        window = MainWindow()
        window.show()
        return app.exec()


__all__ = ["launch_gui"]
