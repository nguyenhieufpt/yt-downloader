# YouTube Downloader (GUI & CLI)

Tool tải video YouTube (**MP4**) hoặc tách nhạc (**MP3**) chạy trên **Ubuntu, macOS và Windows**, sử dụng `yt-dlp` + `ffmpeg` + `PySide6` và đọc file `cookies.txt` export từ Chrome.

## Tính năng giao diện (Desktop GUI)
- Nút **Chọn Cookie...** để trỏ tới file `cookies.txt` (tự nhận `./cookies.txt` nếu có sẵn).
- Chọn định dạng **Convert sang MP3** (128/192/256/320 kbps, tùy chọn nhúng ảnh bìa) hoặc **Giữ nguyên Video (MP4)** (1080p/720p/480p/360p/best).
- Nhập link YouTube, bấm **+ Thêm link** để thêm nhiều ô link.
- Thanh **ProgressBar** và trạng thái riêng cho từng link.
- Nút **Start** và **Dừng** để ngắt tải giữa chừng.

## 1. Cài đặt

### Bước 1: Cài `ffmpeg` (bắt buộc để chuyển sang MP3 và ghép video HD)
- **Ubuntu / Debian:**
  ```bash
  sudo apt update && sudo apt install -y ffmpeg
  ```
- **macOS (Homebrew):**
  ```bash
  brew install ffmpeg
  ```
- **Windows (PowerShell / CMD):**
  ```powershell
  winget install Gyan.FFmpeg
  ```
  *(Sau khi cài trên Windows, đóng và mở lại terminal để nhận lệnh `ffmpeg`.)*

> **Khuyến nghị:** Máy nên có sẵn **Node.js** hoặc **Deno** để `yt-dlp` xử lý challenge JS của YouTube ổn định hơn.

### Bước 2: Cài thư viện Python
```bash
python3 -m venv .venv

# Kích hoạt venv:
# Ubuntu / macOS:
source .venv/bin/activate
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

## 2. Export `cookies.txt` từ Chrome
1. Cài extension **Get cookies.txt LOCALLY** trên Chrome (hoặc extension xuất cookie chuẩn Netscape `.txt`).
2. Mở trang `youtube.com` đã đăng nhập tài khoản của bạn.
3. Bấm vào extension → chọn **Export** (định dạng **Netscape**).
4. Lưu file thành `cookies.txt` (đặt trong thư mục dự án hoặc chọn qua nút **Chọn Cookie...** trên app).

## 3. Cách sử dụng

### Mở giao diện Desktop (GUI):
```bash
python gui.py
# hoặc:
python main.py --gui
```

### Dùng qua dòng lệnh (CLI):
- **Tải MP3 (192 kbps):**
  ```bash
  python main.py --mp3 "https://www.youtube.com/watch?v=VIDEO_ID"
  ```
- **Tải Video MP4 (tối đa 1080p):**
  ```bash
  python main.py "https://www.youtube.com/watch?v=VIDEO_ID"
  ```
- **Cập nhật `yt-dlp` lên bản mới nhất khi gặp lỗi `403`:**
  ```bash
  python main.py --update
  ```
