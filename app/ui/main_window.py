"""Main window implementation for the TRANSCRIBATORAUD GUI."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from app.core.batch import discover_inputs
from app.core.logging import setup_logging
from app.core.ffmpeg import find_ffmpeg
from app.core.worker import JobConfig, TranscribeWorker

try:  # pragma: no cover - optional dependency at runtime
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover - executed when PySide6 is not installed
    QtCore = QtGui = QtWidgets = None  # type: ignore[misc,assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "out"
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

    class MainWindow(QtWidgets.QMainWindow):
        """Main GUI window for TRANSCRIBATORAUD."""

        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("TRANSCRIBATORAUD")
            self.resize(900, 640)

            self._worker: Optional[TranscribeWorker] = None
            self._ffmpeg_checked = False
            self._ffmpeg_path: Optional[Path] = None
            self._worker_had_errors = False

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
            if self._worker and self._worker.isRunning():
                self._worker.stop()
                self._worker.wait(3000)
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
            self._ffmpeg_path = find_ffmpeg()
            if self._ffmpeg_path:
                self._append_log(f"FFmpeg обнаружен: {self._ffmpeg_path}")
            else:
                self._append_log(
                    "FFmpeg не найден. Установите ffmpeg и добавьте его в PATH или переменные окружения."
                )

        def _append_log(self, message: str) -> None:
            self.log_output.appendPlainText(message)

        def _set_controls_enabled(self, enabled: bool) -> None:
            for widget in self._interactive_widgets:
                widget.setEnabled(enabled)
            self.run_button.setEnabled(enabled)

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

            inputs = discover_inputs(Path(source), recursive=self.recursive_checkbox.isChecked())
            if not inputs:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Транскрибация",
                    "Не найдено аудиофайлов для заданного пути.",
                )
                return

            self._append_log("Запуск транскрибации (последовательный режим)…")
            self.progress_bar.setValue(0)
            self._set_controls_enabled(False)

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
            )

            self._worker_had_errors = False
            self._worker = TranscribeWorker(config, self)
            self._worker.log.connect(self._append_log)
            self._worker.progress.connect(self.progress_bar.setValue)
            self._worker.done_file.connect(lambda p: self._append_log(f"Готово: {Path(p).name}"))
            self._worker.error.connect(self._handle_worker_error)
            self._worker.finished_all.connect(self._on_worker_finished)
            self._worker.start()

        def _handle_worker_error(self, message: str) -> None:
            first_error = not self._worker_had_errors
            self._worker_had_errors = True
            self._append_log(message)
            if first_error:
                QtWidgets.QMessageBox.critical(self, "Ошибка", message)

        def _on_worker_finished(self) -> None:
            self._set_controls_enabled(True)
            self.progress_bar.setValue(100)
            if self._worker:
                self._worker.deleteLater()
            self._worker = None
            if self._worker_had_errors:
                self._append_log("Выполнено с ошибками. Проверьте лог выше.")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Транскрибация",
                    "Обработка завершилась с ошибками. Детали см. в логе.",
                )
            else:
                self._append_log("Готово: все файлы обработаны успешно")
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
