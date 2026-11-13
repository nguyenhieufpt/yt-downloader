"""FastAPI Web UI backend for YouTube Downloader (MP4 / MP3)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from downloader import (
    BASE_DIR,
    DEFAULT_OUTPUT_DIR,
    DownloadCancelled,
    download_single_url,
    ffmpeg_install_guide,
    has_ffmpeg,
    validate_netscape_cookies,
)

DATA_DIR = BASE_DIR / "data"
STORED_COOKIE_PATH = DATA_DIR / "cookies.txt"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="YouTube Downloader")
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class LinkItemRequest(BaseModel):
    id: str
    url: str


class StartRequest(BaseModel):
    items: list[LinkItemRequest] = Field(min_length=1)
    mode: Literal["mp3", "mp4"] = "mp3"
    bitrate: Literal["128", "192", "256", "320"] = "192"
    quality: Literal["best", "2160", "1440", "1080", "720", "480", "360"] = "1080"
    embed_thumbnail: bool = False


class JobManager:
    """Thread-safe coordinator for sequential YouTube download tasks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = False
        self._cancel_event = threading.Event()
        self._summary = "Sẵn sàng"
        self._items: list[dict[str, Any]] = []
        self._item_map: dict[str, dict[str, Any]] = {}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "summary": self._summary,
                "ffmpeg_ok": has_ffmpeg(),
                "items": [dict(item) for item in self._items],
            }

    def start(self, req: StartRequest) -> dict[str, Any]:
        clean_items = [
            {"id": item.id, "url": item.url.strip()}
            for item in req.items
            if item.url.strip()
        ]
        if not clean_items:
            raise HTTPException(status_code=400, detail="Hãy nhập ít nhất 1 link YouTube.")

        if req.mode == "mp3" and not has_ffmpeg():
            raise HTTPException(status_code=500, detail=ffmpeg_install_guide())

        with self._lock:
            if self._running:
                raise HTTPException(status_code=409, detail="Đang có tiến trình tải chạy.")

            self._running = True
            self._cancel_event = threading.Event()
            self._summary = f"Đang tải {len(clean_items)} link ({req.mode.upper()})..."
            self._items = [
                {
                    "id": item["id"],
                    "url": item["url"],
                    "state": "queued",
                    "percent": 0,
                    "status": "Đang chờ...",
                }
                for item in clean_items
            ]
            self._item_map = {item["id"]: item for item in self._items}

        cookie_file = STORED_COOKIE_PATH if STORED_COOKIE_PATH.is_file() else None
        worker = threading.Thread(
            target=self._run_tasks,
            args=(clean_items, req, cookie_file),
            daemon=True,
        )
        worker.start()
        return self.snapshot()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if self._running:
                self._cancel_event.set()
                self._summary = "Đang dừng tiến trình tải..."
        return self.snapshot()

    def _update_item(self, item_id: str, **fields: Any) -> None:
        with self._lock:
            target = self._item_map.get(item_id)
            if target is not None:
                target.update(fields)

    def _run_tasks(
        self,
        clean_items: list[dict[str, str]],
        req: StartRequest,
        cookie_file: Path | None,
    ) -> None:
        was_cancelled = False

        try:
            for idx, item in enumerate(clean_items):
                item_id = item["id"]
                url = item["url"]

                if self._cancel_event.is_set():
                    was_cancelled = True
                    for rem in clean_items[idx:]:
                        self._update_item(rem["id"], state="cancelled", status="Đã hủy")
                    break

                self._update_item(
                    item_id,
                    state="running",
                    percent=0,
                    status="Đang lấy thông tin video...",
                )

                def on_progress(percent: int, message: str, target_id: str = item_id) -> None:
                    self._update_item(target_id, percent=percent, status=message)

                try:
                    download_single_url(
                        url=url,
                        mode=req.mode,
                        output_dir=DEFAULT_OUTPUT_DIR,
                        cookie_file=cookie_file,
                        bitrate=req.bitrate,
                        quality=req.quality,
                        allow_playlist=False,
                        embed_thumbnail=req.embed_thumbnail,
                        cancel_event=self._cancel_event,
                        on_progress=on_progress,
                        quiet=True,
                    )
                    self._update_item(item_id, state="done", percent=100, status="Hoàn thành")
                except DownloadCancelled:
                    was_cancelled = True
                    self._update_item(item_id, state="cancelled", status="Đã dừng giữa chừng")
                    for rem in clean_items[idx + 1 :]:
                        self._update_item(rem["id"], state="cancelled", status="Đã hủy")
                    break
                except Exception as exc:
                    if self._cancel_event.is_set():
                        was_cancelled = True
                        self._update_item(item_id, state="cancelled", status="Đã dừng giữa chừng")
                        for rem in clean_items[idx + 1 :]:
                            self._update_item(rem["id"], state="cancelled", status="Đã hủy")
                        break
                    self._update_item(item_id, state="error", status=f"Lỗi: {exc}")
        finally:
            with self._lock:
                self._running = False
                self._summary = "Đã dừng tải." if was_cancelled else "Hoàn tất!"


manager = JobManager()


def _cookie_status() -> dict[str, Any]:
    if not STORED_COOKIE_PATH.is_file():
        return {
            "has_cookie": False,
            "valid": False,
            "message": "Chưa chọn file cookie (sẽ thử tải không cookie).",
        }
    ok, msg = validate_netscape_cookies(STORED_COOKIE_PATH)
    return {
        "has_cookie": True,
        "valid": ok,
        "message": msg,
    }


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/cookie")
def get_cookie_status() -> dict[str, Any]:
    return _cookie_status()


@app.post("/api/cookie")
async def upload_cookie(file: UploadFile = File(...)) -> dict[str, Any]:
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File cookie quá lớn (tối đa 5MB).")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORED_COOKIE_PATH.write_bytes(content)
    return _cookie_status()


@app.delete("/api/cookie")
def delete_cookie() -> dict[str, Any]:
    if STORED_COOKIE_PATH.is_file():
        STORED_COOKIE_PATH.unlink()
    return _cookie_status()


@app.get("/api/status")
def get_status() -> dict[str, Any]:
    return manager.snapshot()


@app.post("/api/start")
def start_downloads(req: StartRequest) -> dict[str, Any]:
    return manager.start(req)


@app.post("/api/stop")
def stop_downloads() -> dict[str, Any]:
    return manager.stop()


@app.get("/api/downloads")
def list_downloads() -> dict[str, Any]:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = [
        p for p in DEFAULT_OUTPUT_DIR.iterdir() if p.is_file() and not p.name.endswith(".part")
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return {
        "files": [
            {"name": f.name, "size": f.stat().st_size}
            for f in files[:30]
        ]
    }


@app.get("/api/downloads/{filename}")
def download_file(filename: str) -> FileResponse:
    base = DEFAULT_OUTPUT_DIR.resolve()
    target = (base / filename).resolve()
    if target.parent != base or not target.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy file.")
    return FileResponse(target, filename=target.name)
