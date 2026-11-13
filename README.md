# YouTube Downloader (Docker Web UI / Desktop GUI / CLI)

Tool tải video YouTube (**MP4**) hoặc tách nhạc (**MP3**) dùng file `cookies.txt` export từ Chrome. Chạy đồng nhất trên **Ubuntu, macOS và Windows**.

## Cách chạy nhanh nhất bằng Docker (1 lệnh duy nhất)

Yêu cầu máy chỉ cần cài sẵn **Docker** (Docker Desktop trên Windows/macOS hoặc Docker Engine + Compose trên Ubuntu). Không cần cài Python hay `ffmpeg` trên máy.

```bash
docker compose up -d --build
```

Sau khi chạy xong, mở trình duyệt vào địa chỉ:
- **http://localhost:8000**

File tải về tự động lưu vào thư mục `./downloads` ngay trên máy của bạn.

### Các lệnh Docker hay dùng:
- **Dừng tool:**
  ```bash
  docker compose down
  ```
- **Cập nhật `yt-dlp` bản mới nhất (khi YouTube đổi player):**
  ```bash
  docker compose build --no-cache && docker compose up -d
  ```

---

## Tính năng trên giao diện
- **Chọn Cookie...:** Upload file `cookies.txt` chuẩn Netscape (tự động kiểm tra và lưu vào `./data/cookies.txt` để dùng lại cho những lần sau).
- **Tùy chọn định dạng:** **Convert sang MP3** (`128/192/256/320` kbps, tùy chọn nhúng ảnh bìa) hoặc **Giữ nguyên Video (MP4)** (`1080p/720p/480p/360p/best`).
- **Danh sách link:** Nhập link vào ô, bấm **+ Thêm ô** (hoặc nút `+` trên dòng) để thêm nhiều link.
- **Start / Dừng:** ProgressBar và trạng thái riêng cho từng link; bấm **Dừng** để ngắt tải giữa chừng.

## Export `cookies.txt` từ Chrome
1. Cài extension **Get cookies.txt LOCALLY** trên Chrome (hoặc extension xuất cookie chuẩn Netscape `.txt`).
2. Mở trang `youtube.com` đã đăng nhập tài khoản của bạn.
3. Bấm vào extension → **Export** (định dạng **Netscape**) ra file `cookies.txt`.
4. Chọn file đó bằng nút **Chọn Cookie...** trên giao diện.

---

## (Tùy chọn) Chạy trực tiếp không qua Docker
Nếu muốn chạy bản Desktop GUI (`PySide6`) hoặc CLI trực tiếp trên máy:
1. Cài `ffmpeg` (`sudo apt install ffmpeg` / `brew install ffmpeg` / `winget install Gyan.FFmpeg`).
2. Cài thư viện:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-desktop.txt
   python gui.py        # mở Desktop GUI
   # hoặc:
   python main.py --mp3 "https://www.youtube.com/watch?v=VIDEO_ID"
   ```
