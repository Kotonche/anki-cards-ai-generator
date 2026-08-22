import argparse
import errno
import importlib.util
import json
import mimetypes
import threading
import urllib.error
import urllib.request
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from generator.webui.defaults import default_anki_media_directory, default_processing_directory
from generator.webui.input_parser import InputError, parse_text, parse_uploaded_file
from generator.webui.jobs import JobError, JobManager


ASSET_ROOT = Path(__file__).resolve().parent
MAX_REQUEST_BYTES = 15 * 1024 * 1024
MANAGER = JobManager()


class ApiError(ValueError):
    def __init__(self, message: str, status: int = HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


def _anki_health() -> dict:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765", timeout=1.5) as response:
            return {"ok": response.status == 200, "message": "AnkiConnect доступен"}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"ok": False, "message": "Запустите Anki и установите AnkiConnect"}


def health_payload() -> dict:
    required = {"openai": "openai", "requests": "requests", "dotenv": "python-dotenv"}
    missing = [package for module, package in required.items() if importlib.util.find_spec(module) is None]
    return {
        "anki": _anki_health(),
        "dependencies": {
            "ok": not missing,
            "missing": missing,
            "message": "Зависимости установлены" if not missing else f"Не установлены: {', '.join(missing)}",
        },
        "defaults": {
            "processing_directory": default_processing_directory(),
            "anki_media_directory": default_anki_media_directory(),
        },
    }


class WebUiHandler(BaseHTTPRequestHandler):
    server_version = "AnkiGeneratorWeb/0.1"

    def do_GET(self):
        try:
            path = urlparse(self.path).path
            if path == "/api/health":
                return self._json(health_payload())
            if path.startswith("/api/jobs/"):
                return self._handle_job_get(path)
            if path in {"/", "/index.html"}:
                return self._file(ASSET_ROOT / "templates" / "index.html")
            if path.startswith("/static/"):
                asset = (ASSET_ROOT / path.lstrip("/")).resolve()
                static_root = (ASSET_ROOT / "static").resolve()
                if static_root not in asset.parents:
                    raise ApiError("Файл не найден", HTTPStatus.NOT_FOUND)
                return self._file(asset)
            raise ApiError("Страница не найдена", HTTPStatus.NOT_FOUND)
        except (ApiError, JobError) as error:
            self._error(error)

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            payload = self._read_json()
            if path == "/api/parse":
                if payload.get("file_content") is not None:
                    cards = parse_uploaded_file(payload.get("filename", ""), payload["file_content"])
                else:
                    cards = parse_text(payload.get("content", ""))
                return self._json({"cards": cards})
            if path == "/api/jobs":
                job = MANAGER.create(payload.get("cards", []), payload.get("settings", {}))
                return self._json(job, HTTPStatus.CREATED)
            if path.startswith("/api/jobs/"):
                return self._handle_job_post(path)
            raise ApiError("Метод не найден", HTTPStatus.NOT_FOUND)
        except (ApiError, InputError, JobError) as error:
            self._error(error)
        except json.JSONDecodeError:
            self._error(ApiError("Некорректный JSON"))

    def _handle_job_get(self, path: str):
        parts = [part for part in path.split("/") if part]
        if len(parts) == 3:
            return self._json(MANAGER.snapshot(parts[2]))
        if len(parts) == 7 and parts[3] == "cards" and parts[5] == "media":
            job_id, card_id, kind = parts[2], parts[4], parts[6]
            media_path = MANAGER.media_path(job_id, card_id, kind)
            if not media_path:
                raise ApiError("Медиафайл ещё не создан", HTTPStatus.NOT_FOUND)
            media_file = Path(media_path).expanduser().resolve()
            processing_root = Path(MANAGER.private_settings(job_id).get("processing_directory", "")).expanduser().resolve()
            if processing_root not in media_file.parents:
                raise ApiError("Медиафайл находится вне рабочей папки", HTTPStatus.FORBIDDEN)
            return self._file(media_file)
        raise ApiError("Ресурс не найден", HTTPStatus.NOT_FOUND)

    def _handle_job_post(self, path: str):
        parts = [part for part in path.split("/") if part]
        if len(parts) != 4:
            raise ApiError("Ресурс не найден", HTTPStatus.NOT_FOUND)
        job_id, action = parts[2], parts[3]
        if action == "start":
            return self._json(MANAGER.start(job_id), HTTPStatus.ACCEPTED)
        if action == "cancel":
            return self._json(MANAGER.request_cancel(job_id), HTTPStatus.ACCEPTED)
        raise ApiError("Неизвестное действие", HTTPStatus.NOT_FOUND)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ApiError("Некорректный Content-Length") from error
        if length <= 0:
            return {}
        if length > MAX_REQUEST_BYTES:
            raise ApiError("Запрос слишком большой", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, payload: dict, status: int = HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path):
        path = path.resolve()
        if not path.is_file():
            raise ApiError("Файл не найден", HTTPStatus.NOT_FOUND)
        body = path.read_bytes()
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime_type}; charset=utf-8" if mime_type.startswith("text/") else mime_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, error):
        status = getattr(error, "status", HTTPStatus.BAD_REQUEST)
        self._json({"error": str(error)}, status)

    def log_message(self, format_string, *args):
        print(f"[web] {self.address_string()} - {format_string % args}")


def create_server(host: str = "127.0.0.1", port: int = 8766) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), WebUiHandler)


def create_server_with_fallback(host: str, preferred_port: int, attempts: int = 10, server_factory=None):
    factory = server_factory or create_server
    for offset in range(attempts):
        port = preferred_port + offset
        try:
            return factory(host, port), port
        except OSError as error:
            if error.errno != errno.EADDRINUSE or offset == attempts - 1:
                raise
    raise RuntimeError("Не удалось найти свободный локальный порт")


def main():
    parser = argparse.ArgumentParser(description="Local web interface for the Anki card generator")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: local computer only)")
    parser.add_argument("--port", type=int, default=8766, help="HTTP port")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically")
    args = parser.parse_args()

    try:
        server, selected_port = create_server_with_fallback(args.host, args.port)
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            parser.error(f"ports {args.port}-{args.port + 9} are already in use")
        raise

    if selected_port != args.port:
        print(f"Port {args.port} is busy; using {selected_port} instead")
    url = f"http://{args.host}:{server.server_port}"
    print(f"Anki Card Generator is available at {url}")
    print("Press Ctrl+C to stop it")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web interface")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
