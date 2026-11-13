#!/usr/bin/env python3
"""CLI entry point for YouTube Downloader (MP4 / MP3)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from downloader import (
    DEFAULT_COOKIES_PATH,
    DEFAULT_OUTPUT_DIR,
    build_ydl_opts,
    ffmpeg_install_guide,
    has_ffmpeg,
    update_yt_dlp,
    validate_netscape_cookies,
)


def resolve_cookie_file(cookie_arg: str | None) -> Path | None:
    """Resolve explicit or default cookies.txt path."""
    if cookie_arg:
        cookie_path = Path(cookie_arg).expanduser().resolve()
        ok, msg = validate_netscape_cookies(cookie_path)
        if not cookie_path.is_file():
            print(f"[LỖI] {msg}")
            sys.exit(1)
        if not ok:
            print(f"[CẢNH BÁO] {msg}")
        return cookie_path

    if DEFAULT_COOKIES_PATH.is_file():
        ok, msg = validate_netscape_cookies(DEFAULT_COOKIES_PATH)
        if not ok:
            print(f"[CẢNH BÁO] {msg}")
        return DEFAULT_COOKIES_PATH

    print(
        f"[THÔNG BÁO] Chưa thấy `{DEFAULT_COOKIES_PATH.name}` trong thư mục tool. "
        "Sẽ thử tải không cần cookie (nếu bị YouTube chặn bot, hãy export cookies.txt đặt vào đây)."
    )
    return None


def load_batch_urls(batch_file: Path) -> list[str]:
    """Read URLs from a text file, ignoring empty lines and comments."""
    if not batch_file.is_file():
        print(f"[LỖI] Không tìm thấy file danh sách URL: {batch_file}")
        sys.exit(1)

    urls: list[str] = []
    for raw_line in batch_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def prompt_interactive() -> tuple[list[str], str, str, str]:
    """Prompt user for URL and download format when no CLI URL is passed."""
    print("=== YouTube Downloader (MP4 / MP3) ===")
    url = input("Dán link YouTube: ").strip()
    if not url:
        print("Chưa nhập link. Thoát.")
        sys.exit(0)

    choice = input("Chọn định dạng [1: MP3 (mặc định), 2: MP4]: ").strip()
    if choice == "2":
        mode = "mp4"
        quality = input("Độ phân giải tối đa (best / 1080 / 720 / 480) [1080]: ").strip() or "1080"
        bitrate = "192"
    else:
        mode = "mp3"
        bitrate = input("Bitrate MP3 (128 / 192 / 256 / 320) [192]: ").strip() or "192"
        quality = "1080"

    return [url], mode, bitrate, quality


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Tải video YouTube (MP4) hoặc tách nhạc (MP3) dùng cookies.txt.",
    )
    parser.add_argument("urls", nargs="*", help="Một hoặc nhiều URL YouTube")
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Mở giao diện Desktop (GUI)",
    )
    parser.add_argument(
        "-a",
        "--mp3",
        action="store_true",
        help="Chuyển sang chế độ tải audio và convert MP3",
    )
    parser.add_argument(
        "-b",
        "--bitrate",
        default="192",
        choices=["128", "192", "256", "320"],
        help="Chất lượng MP3 (kbps), mặc định: 192",
    )
    parser.add_argument(
        "-q",
        "--quality",
        default="1080",
        choices=["best", "2160", "1440", "1080", "720", "480", "360"],
        help="Độ phân giải video MP4 tối đa, mặc định: 1080",
    )
    parser.add_argument(
        "-c",
        "--cookies",
        help="Đường dẫn tới file cookies.txt (mặc định tìm ./cookies.txt)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Thư mục lưu file tải về (mặc định: ./downloads)",
    )
    parser.add_argument(
        "--batch",
        help="Đường dẫn file text chứa danh sách URL (mỗi dòng 1 link)",
    )
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Cho phép tải cả playlist nếu URL thuộc playlist (mặc định chỉ tải 1 video)",
    )
    parser.add_argument(
        "--thumbnail",
        action="store_true",
        help="Nhúng ảnh bìa video vào file MP3",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Cập nhật yt-dlp lên bản mới nhất rồi thoát",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.gui:
        from gui import launch_gui

        return launch_gui()

    if args.update:
        print("Đang cập nhật yt-dlp lên phiên bản mới nhất...")
        return update_yt_dlp()

    if args.urls or args.batch:
        urls = list(args.urls)
        if args.batch:
            urls.extend(load_batch_urls(Path(args.batch).expanduser().resolve()))
        mode = "mp3" if args.mp3 else "mp4"
        bitrate = args.bitrate
        quality = args.quality
    else:
        urls, mode, bitrate, quality = prompt_interactive()

    if not urls:
        print("[LỖI] Không có URL nào để tải.")
        return 1

    if mode == "mp3" and not has_ffmpeg():
        print(f"\n[LỖI] {ffmpeg_install_guide()}\n")
        return 1

    if mode == "mp4" and not has_ffmpeg():
        print("[CẢNH BÁO] Chưa có `ffmpeg`, video có thể chỉ tải được định dạng gộp sẵn (thường <= 720p).")

    try:
        import yt_dlp
    except ImportError:
        print("[LỖI] Chưa cài thư viện `yt-dlp`. Hãy chạy: pip install -r requirements.txt")
        return 1

    cookie_file = resolve_cookie_file(args.cookies)
    output_dir = Path(args.output).expanduser().resolve()
    ydl_opts = build_ydl_opts(
        mode=mode,
        output_dir=output_dir,
        cookie_file=cookie_file,
        bitrate=bitrate,
        quality=quality,
        allow_playlist=args.playlist,
        embed_thumbnail=args.thumbnail,
        quiet=False,
    )

    print(f"\nChế độ: {mode.upper()} | Lưu tại: {output_dir}")
    if cookie_file:
        print(f"Cookie: {cookie_file}")
    print("-" * 50)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download(urls)
    except yt_dlp.utils.DownloadError as exc:
        print(f"\n[LỖI TẢI] {exc}")
        print(
            "Gợi ý xử lý:\n"
            "  1. Chạy `python main.py --update` để cập nhật yt-dlp mới nhất.\n"
            "  2. Nếu báo lỗi bot/đăng nhập, hãy export lại file `cookies.txt` mới từ Chrome."
        )
        return 1

    if error_code == 0:
        print(f"\n[XONG] File đã lưu trong: {output_dir}")
    return int(error_code)


if __name__ == "__main__":
    raise SystemExit(main())
