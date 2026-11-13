"""PySide6 Desktop GUI for YouTube Downloader (MP4 / MP3)."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from downloader import (
    DEFAULT_COOKIES_PATH,
    DEFAULT_OUTPUT_DIR,
    DownloadCancelled,
    download_single_url,
    ffmpeg_install_guide,
    has_ffmpeg,
    validate_netscape_cookies,
)


class DownloadWorker(QObject):
    """Background worker that processes queued URLs sequentially."""

    row_progress = Signal(int, int, str)
    row_finished = Signal(int, str)
    row_cancelled = Signal(int, str)
    row_error = Signal(int, str)
    all_done = Signal(bool)

    def __init__(
        self,
        tasks: list[tuple[int, str]],
        mode: str,
        output_dir: Path,
        cookie_file: Path | None,
        bitrate: str,
        quality: str,
        embed_thumbnail: bool,
    ) -> None:
        super().__init__()
        self.tasks = tasks
        self.mode = mode
        self.output_dir = output_dir
        self.cookie_file = cookie_file
        self.bitrate = bitrate
        self.quality = quality
        self.embed_thumbnail = embed_thumbnail
        self.cancel_event = threading.Event()

    def stop(self) -> None:
        """Signal the active and pending downloads to stop."""
        self.cancel_event.set()

    def run(self) -> None:
        """Execute each URL download task until finished or cancelled."""
        was_cancelled = False

        for idx, (row_index, url) in enumerate(self.tasks):
            if self.cancel_event.is_set():
                was_cancelled = True
                for rem_index, _ in self.tasks[idx:]:
                    self.row_cancelled.emit(rem_index, "Đã hủy")
                break

            self.row_progress.emit(row_index, 0, "Đang lấy thông tin video...")

            def handle_progress(percent: int, message: str, r_idx: int = row_index) -> None:
                self.row_progress.emit(r_idx, percent, message)

            try:
                download_single_url(
                    url=url,
                    mode=self.mode,
                    output_dir=self.output_dir,
                    cookie_file=self.cookie_file,
                    bitrate=self.bitrate,
                    quality=self.quality,
                    allow_playlist=False,
                    embed_thumbnail=self.embed_thumbnail,
                    cancel_event=self.cancel_event,
                    on_progress=handle_progress,
                    quiet=True,
                )
                self.row_finished.emit(row_index, "Hoàn thành")
            except DownloadCancelled:
                was_cancelled = True
                self.row_cancelled.emit(row_index, "Đã dừng giữa chừng")
                for rem_index, _ in self.tasks[idx + 1 :]:
                    self.row_cancelled.emit(rem_index, "Đã hủy")
                break
            except Exception as exc:
                if self.cancel_event.is_set():
                    was_cancelled = True
                    self.row_cancelled.emit(row_index, "Đã dừng giữa chừng")
                    for rem_index, _ in self.tasks[idx + 1 :]:
                        self.row_cancelled.emit(rem_index, "Đã hủy")
                    break
                self.row_error.emit(row_index, f"Lỗi: {exc}")

        self.all_done.emit(was_cancelled)


class LinkRowWidget(QWidget):
    """Single YouTube URL input row with its own progress bar and status."""

    remove_requested = Signal(object)

    def __init__(self, index_label: int = 1) -> None:
        super().__init__()
        self.completed = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.index_lbl = QLabel(f"#{index_label}")
        self.index_lbl.setMinimumWidth(28)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Dán link YouTube vào đây (https://www.youtube.com/watch?v=...)")
        self.url_input.textChanged.connect(self._on_text_changed)

        self.remove_btn = QPushButton("✕")
        self.remove_btn.setFixedWidth(32)
        self.remove_btn.setToolTip("Xóa ô link này")
        self.remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))

        top_row.addWidget(self.index_lbl)
        top_row.addWidget(self.url_input, 1)
        top_row.addWidget(self.remove_btn)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(18)

        self.status_lbl = QLabel("Sẵn sàng")
        self.status_lbl.setMinimumWidth(210)
        self.status_lbl.setStyleSheet("color: #666;")

        bottom_row.addWidget(self.progress_bar, 1)
        bottom_row.addWidget(self.status_lbl)

        outer.addLayout(top_row)
        outer.addLayout(bottom_row)

        self.setStyleSheet(
            "LinkRowWidget { border: 1px solid #d0d7de; border-radius: 6px; background: #fafbfc; }"
        )

    def _on_text_changed(self) -> None:
        self.completed = False
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Sẵn sàng")
        self.status_lbl.setStyleSheet("color: #666;")

    def set_index(self, number: int) -> None:
        self.index_lbl.setText(f"#{number}")

    def set_editable(self, editable: bool) -> None:
        self.url_input.setReadOnly(not editable)
        self.remove_btn.setEnabled(editable)

    def set_progress(self, percent: int, status: str) -> None:
        self.progress_bar.setValue(percent)
        self.status_lbl.setText(status)
        self.status_lbl.setStyleSheet("color: #0969da;")

    def set_done(self, status: str) -> None:
        self.completed = True
        self.progress_bar.setValue(100)
        self.status_lbl.setText(status)
        self.status_lbl.setStyleSheet("color: #1a7f37; font-weight: bold;")

    def set_cancelled(self, status: str) -> None:
        self.completed = False
        self.status_lbl.setText(status)
        self.status_lbl.setStyleSheet("color: #9a6700; font-weight: bold;")

    def set_error(self, message: str) -> None:
        self.completed = False
        short_msg = message if len(message) <= 60 else f"{message[:57]}..."
        self.status_lbl.setText(short_msg)
        self.status_lbl.setToolTip(message)
        self.status_lbl.setStyleSheet("color: #cf222e; font-weight: bold;")


class MainWindow(QMainWindow):
    """Main desktop window for YouTube Downloader."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("YouTube Downloader (MP4 / MP3)")
        self.resize(780, 620)

        self.rows: list[LinkRowWidget] = []
        self.worker_thread: QThread | None = None
        self.worker: DownloadWorker | None = None

        self._build_ui()
        self._load_default_cookie()
        self.add_link_row()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # 1. Cookie section
        cookie_group = QGroupBox("1. Cookie Chrome (cookies.txt)")
        cookie_layout = QVBoxLayout(cookie_group)

        cookie_row = QHBoxLayout()
        self.cookie_input = QLineEdit()
        self.cookie_input.setReadOnly(True)
        self.cookie_input.setPlaceholderText("Chưa chọn file cookies.txt (tùy chọn)")

        self.choose_cookie_btn = QPushButton("Chọn Cookie...")
        self.choose_cookie_btn.clicked.connect(self.choose_cookie_file)

        self.clear_cookie_btn = QPushButton("Xóa")
        self.clear_cookie_btn.clicked.connect(self.clear_cookie_file)

        cookie_row.addWidget(self.cookie_input, 1)
        cookie_row.addWidget(self.choose_cookie_btn)
        cookie_row.addWidget(self.clear_cookie_btn)

        self.cookie_status_lbl = QLabel("Chưa chọn cookie (sẽ thử tải không cookie).")
        self.cookie_status_lbl.setStyleSheet("color: #666; font-size: 12px;")

        cookie_layout.addLayout(cookie_row)
        cookie_layout.addWidget(self.cookie_status_lbl)
        root.addWidget(cookie_group)

        # 2. Format & Output options
        opt_group = QGroupBox("2. Định dạng & Thư mục lưu")
        opt_layout = QVBoxLayout(opt_group)

        mode_row = QHBoxLayout()
        self.mp3_radio = QRadioButton("Convert sang MP3 (Audio)")
        self.mp3_radio.setChecked(True)
        self.mp3_radio.toggled.connect(self._sync_option_controls)

        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(["128", "192", "256", "320"])
        self.bitrate_combo.setCurrentText("192")

        self.thumb_checkbox = QCheckBox("Nhúng ảnh bìa")

        self.mp4_radio = QRadioButton("Giữ nguyên Video (MP4)")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["1080", "720", "480", "360", "best"])
        self.quality_combo.setCurrentText("1080")

        mode_row.addWidget(self.mp3_radio)
        mode_row.addWidget(QLabel("Bitrate:"))
        mode_row.addWidget(self.bitrate_combo)
        mode_row.addWidget(QLabel("kbps"))
        mode_row.addWidget(self.thumb_checkbox)
        mode_row.addSpacing(20)
        mode_row.addWidget(self.mp4_radio)
        mode_row.addWidget(QLabel("Max:"))
        mode_row.addWidget(self.quality_combo)
        mode_row.addStretch()

        out_row = QHBoxLayout()
        self.output_input = QLineEdit(str(DEFAULT_OUTPUT_DIR))
        self.choose_output_btn = QPushButton("Chọn thư mục...")
        self.choose_output_btn.clicked.connect(self.choose_output_dir)
        self.open_output_btn = QPushButton("Mở thư mục")
        self.open_output_btn.clicked.connect(self.open_output_dir)

        out_row.addWidget(QLabel("Lưu tại:"))
        out_row.addWidget(self.output_input, 1)
        out_row.addWidget(self.choose_output_btn)
        out_row.addWidget(self.open_output_btn)

        opt_layout.addLayout(mode_row)
        opt_layout.addLayout(out_row)
        root.addWidget(opt_group)

        # 3. Links list section
        links_group = QGroupBox("3. Danh sách link YouTube")
        links_group_layout = QVBoxLayout(links_group)

        links_header = QHBoxLayout()
        links_hint = QLabel("Nhập link vào ô bên dưới. Bấm + để thêm nhiều link cùng lúc.")
        links_hint.setStyleSheet("color: #555;")
        self.add_row_btn = QPushButton("+ Thêm link")
        self.add_row_btn.clicked.connect(self.add_link_row)

        links_header.addWidget(links_hint)
        links_header.addStretch()
        links_header.addWidget(self.add_row_btn)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(4, 4, 4, 4)
        self.rows_layout.setSpacing(8)
        self.rows_layout.addStretch()
        self.scroll_area.setWidget(self.rows_container)

        links_group_layout.addLayout(links_header)
        links_group_layout.addWidget(self.scroll_area, 1)
        root.addWidget(links_group, 1)

        # 4. Control bar
        controls = QHBoxLayout()
        self.summary_lbl = QLabel("Sẵn sàng")
        self.summary_lbl.setStyleSheet("color: #444;")

        self.start_btn = QPushButton("Start")
        self.start_btn.setMinimumSize(110, 36)
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #1f883d; color: white; font-weight: bold; border-radius: 6px; }"
            "QPushButton:disabled { background-color: #94d3a2; }"
        )
        self.start_btn.clicked.connect(self.start_downloads)

        self.stop_btn = QPushButton("Dừng")
        self.stop_btn.setMinimumSize(100, 36)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(
            "QPushButton { background-color: #cf222e; color: white; font-weight: bold; border-radius: 6px; }"
            "QPushButton:disabled { background-color: #e5989e; }"
        )
        self.stop_btn.clicked.connect(self.stop_downloads)

        controls.addWidget(self.summary_lbl, 1)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        root.addLayout(controls)

        self._sync_option_controls()

    def _sync_option_controls(self) -> None:
        is_mp3 = self.mp3_radio.isChecked()
        self.bitrate_combo.setEnabled(is_mp3)
        self.thumb_checkbox.setEnabled(is_mp3)
        self.quality_combo.setEnabled(not is_mp3)

    def _load_default_cookie(self) -> None:
        if DEFAULT_COOKIES_PATH.is_file():
            self._apply_cookie_path(DEFAULT_COOKIES_PATH)

    def _apply_cookie_path(self, path: Path) -> None:
        self.cookie_input.setText(str(path))
        ok, msg = validate_netscape_cookies(path)
        self.cookie_status_lbl.setText(msg)
        if ok:
            self.cookie_status_lbl.setStyleSheet("color: #1a7f37; font-size: 12px;")
        else:
            self.cookie_status_lbl.setStyleSheet("color: #9a6700; font-size: 12px;")

    def choose_cookie_file(self) -> None:
        start_dir = str(DEFAULT_COOKIES_PATH.parent)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file cookies.txt",
            start_dir,
            "Cookie files (*.txt);;All files (*)",
        )
        if file_path:
            self._apply_cookie_path(Path(file_path))

    def clear_cookie_file(self) -> None:
        self.cookie_input.clear()
        self.cookie_status_lbl.setText("Chưa chọn cookie (sẽ thử tải không cookie).")
        self.cookie_status_lbl.setStyleSheet("color: #666; font-size: 12px;")

    def choose_output_dir(self) -> None:
        current = self.output_input.text().strip() or str(DEFAULT_OUTPUT_DIR)
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu file", current)
        if folder:
            self.output_input.setText(folder)

    def open_output_dir(self) -> None:
        out_path = Path(self.output_input.text().strip() or str(DEFAULT_OUTPUT_DIR)).expanduser()
        out_path.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(str(out_path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(out_path)])
        else:
            subprocess.Popen(["xdg-open", str(out_path)])

    def add_link_row(self) -> None:
        row = LinkRowWidget(len(self.rows) + 1)
        row.remove_requested.connect(self.remove_link_row)
        self.rows.append(row)
        # Insert right before the trailing stretch item.
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
        row.url_input.setFocus()

    def remove_link_row(self, row: LinkRowWidget) -> None:
        if len(self.rows) <= 1:
            row.url_input.clear()
            return
        self.rows.remove(row)
        self.rows_layout.removeWidget(row)
        row.deleteLater()
        for idx, item in enumerate(self.rows, start=1):
            item.set_index(idx)

    def _set_running_state(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.stop_btn.setText("Dừng")
        self.choose_cookie_btn.setEnabled(not running)
        self.clear_cookie_btn.setEnabled(not running)
        self.mp3_radio.setEnabled(not running)
        self.mp4_radio.setEnabled(not running)
        self.choose_output_btn.setEnabled(not running)
        self.output_input.setReadOnly(running)
        self.add_row_btn.setEnabled(not running)
        for row in self.rows:
            row.set_editable(not running)
        if not running:
            self._sync_option_controls()
        else:
            self.bitrate_combo.setEnabled(False)
            self.thumb_checkbox.setEnabled(False)
            self.quality_combo.setEnabled(False)

    def start_downloads(self) -> None:
        mode = "mp3" if self.mp3_radio.isChecked() else "mp4"
        if mode == "mp3" and not has_ffmpeg():
            QMessageBox.warning(self, "Thiếu ffmpeg", ffmpeg_install_guide())
            return

        cookie_text = self.cookie_input.text().strip()
        cookie_file: Path | None = None
        if cookie_text:
            cookie_file = Path(cookie_text).expanduser()
            if not cookie_file.is_file():
                QMessageBox.warning(
                    self,
                    "Không tìm thấy file cookie",
                    f"File cookie không tồn tại:\n{cookie_file}",
                )
                return

        tasks: list[tuple[int, str]] = []
        for idx, row in enumerate(self.rows):
            url = row.url_input.text().strip()
            if not url:
                continue
            if row.completed:
                continue
            row.set_progress(0, "Đang chờ...")
            tasks.append((idx, url))

        if not tasks:
            QMessageBox.information(
                self,
                "Chưa có link mới",
                "Hãy nhập ít nhất 1 link YouTube (hoặc sửa link cũ) để bắt đầu tải.",
            )
            return

        output_dir = Path(self.output_input.text().strip() or str(DEFAULT_OUTPUT_DIR)).expanduser()

        self._set_running_state(True)
        self.summary_lbl.setText(f"Đang tải {len(tasks)} link ({mode.upper()})...")

        self.worker_thread = QThread()
        self.worker = DownloadWorker(
            tasks=tasks,
            mode=mode,
            output_dir=output_dir,
            cookie_file=cookie_file,
            bitrate=self.bitrate_combo.currentText(),
            quality=self.quality_combo.currentText(),
            embed_thumbnail=self.thumb_checkbox.isChecked(),
        )
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.row_progress.connect(self._on_row_progress)
        self.worker.row_finished.connect(self._on_row_finished)
        self.worker.row_cancelled.connect(self._on_row_cancelled)
        self.worker.row_error.connect(self._on_row_error)
        self.worker.all_done.connect(self._on_all_done)

        self.worker_thread.start()

    def stop_downloads(self) -> None:
        if self.worker is not None:
            self.stop_btn.setEnabled(False)
            self.stop_btn.setText("Đang dừng...")
            self.summary_lbl.setText("Đang dừng tiến trình tải...")
            self.worker.stop()

    def _on_row_progress(self, row_index: int, percent: int, status: str) -> None:
        if 0 <= row_index < len(self.rows):
            self.rows[row_index].set_progress(percent, status)

    def _on_row_finished(self, row_index: int, status: str) -> None:
        if 0 <= row_index < len(self.rows):
            self.rows[row_index].set_done(status)

    def _on_row_cancelled(self, row_index: int, status: str) -> None:
        if 0 <= row_index < len(self.rows):
            self.rows[row_index].set_cancelled(status)

    def _on_row_error(self, row_index: int, message: str) -> None:
        if 0 <= row_index < len(self.rows):
            self.rows[row_index].set_error(message)

    def _on_all_done(self, was_cancelled: bool) -> None:
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread.deleteLater()
            self.worker_thread = None
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

        self._set_running_state(False)
        self.summary_lbl.setText("Đã dừng tải." if was_cancelled else "Hoàn tất!")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.worker is not None and self.worker_thread is not None:
            self.worker.stop()
            self.worker_thread.quit()
            self.worker_thread.wait(3000)
        super().closeEvent(event)


def launch_gui() -> int:
    """Start the Qt desktop application."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(launch_gui())
