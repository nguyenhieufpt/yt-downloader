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
2. Cài **Deno** (khuyên dùng) hoặc **Node.js bản mới** để `yt-dlp` giải mã JS challenge của YouTube.
3. Cài thư viện:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-desktop.txt
   python gui.py        # mở Desktop GUI
   # hoặc:
   python main.py --mp3 "https://www.youtube.com/watch?v=VIDEO_ID"
   ```

---

## Xử lý sự cố thường gặp (Troubleshooting)

### 1. Xem log chi tiết khi giao diện báo lỗi bị rút gọn
```bash
docker logs --tail 50 yt-downloader
```
Hoặc chạy kiểm tra trực tiếp 1 video bên trong container để xem dòng `WARNING` / `[debug]`:
```bash
docker exec yt-downloader yt-dlp -F -v --cookies /app/data/cookies.txt "https://www.youtube.com/watch?v=VIDEO_ID"
```

### 2. Lỗi `Requested format is not available` / `Signature solving failed` / `n challenge solving failed`
- **Nguyên nhân:** `yt-dlp` hoặc JS runtime (`deno` / `node`) đã cũ so với player JS mới của YouTube (hoặc dùng bản Node cũ bị `yt-dlp` báo `unsupported`).
- **Cách xử lý (Docker):** Rebuild không cache để kéo `yt-dlp`, `yt-dlp-ejs` và `deno` mới nhất:
  ```bash
  docker compose build --no-cache && docker compose up -d
  ```
- **Cách xử lý (chạy trực tiếp không qua Docker):**
  ```bash
  python main.py --update
  ```
  Và đảm bảo máy đã cài **Deno** (hoặc **Node.js >= 22/24**) nằm trong `PATH`.

### 3. Lỗi `HTTP Error 403: Forbidden`
1. Cập nhật `yt-dlp` mới nhất (`docker compose build --no-cache && docker compose up -d` hoặc `python main.py --update`).
2. Nếu vẫn lỗi, export lại file `cookies.txt` mới từ Chrome và upload lại.

### 4. Lỗi `Sign in to confirm you're not a bot` hoặc Cookie hết hạn
- Mở Chrome đang đăng nhập YouTube → export lại `cookies.txt` mới (chuẩn Netscape) → bấm **Chọn Cookie...** để nạp lại.
- Nếu tải quá nhiều video liên tục trong thời gian ngắn, nên nghỉ một lúc hoặc dùng một tài khoản Google phụ trên profile Chrome riêng.
