"""Shared download and validation helpers for YouTube Downloader."""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_COOKIES_PATH = BASE_DIR / "cookies.txt"
DEFAULT_OUTPUT_DIR = BASE_DIR / "downloads"


class DownloadCancelled(Exception):
    """Raised inside yt-dlp hooks when the user stops an active download."""


def ffmpeg_install_guide() -> str:
    """Return OS-specific instructions to install ffmpeg."""
    return (
        "Không tìm thấy `ffmpeg` trên máy.\n"
        "Cần cài `ffmpeg` để convert sang MP3 và ghép video/audio chất lượng cao:\n"
        "  - Ubuntu/Debian: sudo apt update && sudo apt install -y ffmpeg\n"
        "  - macOS (Homebrew): brew install ffmpeg\n"
        "  - Windows (winget): winget install Gyan.FFmpeg\n"
        "Sau khi cài xong, mở lại terminal/ứng dụng rồi thử lại."
    )


def has_ffmpeg() -> bool:
    """Return True if ffmpeg is available in PATH."""
    return shutil.which("ffmpeg") is not None


def validate_netscape_cookies(cookie_path: Path) -> tuple[bool, str]:
    """Validate basic Netscape cookies.txt format.

    Returns (is_ok, message).
    """
    if not cookie_path.is_file():
        return False, f"Không tìm thấy file cookie: {cookie_path}"

    try:
        lines = cookie_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return False, f"Không đọc được file cookie: {exc}"

    non_empty = [line.strip() for line in lines if line.strip()]
    if not non_empty:
        return False, f"File cookie đang rỗng: {cookie_path.name}"

    data_lines = [line for line in non_empty if not line.startswith("#")]
    if not data_lines:
        return False, f"File cookie chưa có dòng cookie nào: {cookie_path.name}"

    has_tab_fields = any(len(line.split("\t")) >= 7 for line in data_lines)
    if not has_tab_fields:
        return (
            False,
            "File cookie có vẻ không đúng chuẩn Netscape (.txt phân tách bằng Tab). "
            "Hãy export lại bằng extension (ví dụ: 'Get cookies.txt LOCALLY').",
        )

    return True, f"Cookie hợp lệ ({len(data_lines)} mục): {cookie_path.name}"


def update_yt_dlp() -> int:
    """Upgrade yt-dlp using the current Python interpreter."""
    cmd = [sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]"]
    result = subprocess.run(cmd, check=False)
    return result.returncode


def build_ydl_opts(
    mode: str,
    output_dir: Path,
    cookie_file: Path | None = None,
    bitrate: str = "192",
    quality: str = "1080",
    allow_playlist: bool = False,
    embed_thumbnail: bool = False,
    progress_hooks: list[Callable[[dict[str, Any]], None]] | None = None,
    postprocessor_hooks: list[Callable[[dict[str, Any]], None]] | None = None,
    quiet: bool = False,
) -> dict[str, Any]:
    """Build yt-dlp options dictionary for MP3 or MP4 downloads."""
    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / "%(title).180B [%(id)s].%(ext)s")

    opts: dict[str, Any] = {
        "outtmpl": outtmpl,
        "noplaylist": not allow_playlist,
        "windowsfilenames": True,
        "retries": 5,
        "fragment_retries": 5,
        "ignoreerrors": allow_playlist,
        "quiet": quiet,
        "no_warnings": quiet,
        "js_runtimes": {"deno": {"path": None}, "node": {"path": None}},
    }

    if cookie_file is not None:
        opts["cookiefile"] = str(cookie_file)

    if progress_hooks:
        opts["progress_hooks"] = progress_hooks

    if postprocessor_hooks:
        opts["postprocessor_hooks"] = postprocessor_hooks

    if mode == "mp3":
        postprocessors: list[dict[str, Any]] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": bitrate,
            },
            {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            },
        ]
        if embed_thumbnail:
            opts["writethumbnail"] = True
            postprocessors.append({"key": "EmbedThumbnail"})

        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = postprocessors
    else:
        if quality == "best":
            opts["format"] = "bestvideo+bestaudio/best"
        else:
            opts["format"] = (
                f"bestvideo[height<={quality}]+bestaudio/"
                f"best[height<={quality}]/best"
            )
        opts["merge_output_format"] = "mp4"

    return opts


def download_single_url(
    url: str,
    mode: str,
    output_dir: Path,
    cookie_file: Path | None = None,
    bitrate: str = "192",
    quality: str = "1080",
    allow_playlist: bool = False,
    embed_thumbnail: bool = False,
    cancel_event: threading.Event | None = None,
    on_progress: Callable[[int, str], None] | None = None,
    quiet: bool = True,
) -> None:
    """Download a single URL with cancellation and progress callback support."""
    import yt_dlp

    def check_cancelled() -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelled("Đã dừng theo yêu cầu người dùng.")

    def progress_hook(data: dict[str, Any]) -> None:
        check_cancelled()
        if on_progress is None:
            return

        status = data.get("status")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes") or 0
            percent = 0
            if total and total > 0:
                percent = max(0, min(100, int(downloaded * 100 / total)))

            info = data.get("info_dict") or {}
            vcodec = info.get("vcodec")
            acodec = info.get("acodec")
            if vcodec and vcodec != "none" and acodec == "none":
                stage = "Đang tải video"
            elif acodec and acodec != "none" and (not vcodec or vcodec == "none"):
                stage = "Đang tải audio"
            else:
                stage = "Đang tải"

            speed = (data.get("_speed_str") or "").strip()
            detail = f"{stage}... {percent}%"
            if speed and speed != "N/A":
                detail = f"{detail} ({speed})"
            on_progress(percent, detail)
        elif status == "finished":
            on_progress(100, "Đã tải xong luồng, đang xử lý...")

    def postprocessor_hook(data: dict[str, Any]) -> None:
        check_cancelled()
        if on_progress is None:
            return
        if data.get("status") == "started":
            pp = data.get("postprocessor") or ""
            if "ExtractAudio" in pp:
                on_progress(100, "Đang convert sang MP3...")
            elif "Merger" in pp:
                on_progress(100, "Đang ghép video & audio...")
            else:
                on_progress(100, "Đang xử lý hậu kỳ...")

    check_cancelled()

    ydl_opts = build_ydl_opts(
        mode=mode,
        output_dir=output_dir,
        cookie_file=cookie_file,
        bitrate=bitrate,
        quality=quality,
        allow_playlist=allow_playlist,
        embed_thumbnail=embed_thumbnail,
        progress_hooks=[progress_hook],
        postprocessor_hooks=[postprocessor_hook],
        quiet=quiet,
    )

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        error_code = ydl.download([url])

    check_cancelled()
    if error_code != 0:
        raise RuntimeError(f"yt-dlp kết thúc với mã lỗi {error_code}")
