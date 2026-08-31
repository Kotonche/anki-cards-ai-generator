import copy
import threading
import uuid
from datetime import datetime, timezone

from generator.api_costs import empty_cost_summary


TERMINAL_CARD_STATUSES = {"generated", "imported", "skipped", "error"}
TERMINAL_JOB_STATUSES = {"completed", "completed_with_errors", "cancelled", "error"}
SECRET_SETTING_NAMES = {"openai_api_key", "replicate_api_key"}


class JobError(ValueError):
    pass


class JobManager:
    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._active_job_id: str | None = None

    def create(self, cards: list[dict], settings: dict) -> dict:
        if not cards:
            raise JobError("Добавьте хотя бы одну карточку")

        job_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        normalized_cards = []
        for index, card in enumerate(cards):
            word = str(card.get("word", "")).strip()
            if not word:
                continue
            normalized_cards.append(
                {
                    "id": str(index + 1),
                    "word": word,
                    "context": str(card.get("context", "")).strip(),
                    "phrase": str(card.get("phrase", "")).strip(),
                    "status": "queued",
                    "message": "Ожидает запуска",
                    "card_text": None,
                    "image_prompt": None,
                    "dictionary_url": None,
                    "has_image": False,
                    "has_audio": False,
                    "has_context_audio": False,
                }
            )
        if not normalized_cards:
            raise JobError("Добавьте хотя бы одну карточку")

        job = {
            "id": job_id,
            "created_at": now,
            "updated_at": now,
            "status": "ready",
            "message": "Задание готово к запуску",
            "settings": copy.deepcopy(settings),
            "cards": normalized_cards,
            "cost": empty_cost_summary(),
            "cancel_requested": False,
        }
        with self._lock:
            self._jobs[job_id] = job
        return self.snapshot(job_id)

    def snapshot(self, job_id: str) -> dict:
        with self._lock:
            job = copy.deepcopy(self._require(job_id))

        for name in SECRET_SETTING_NAMES:
            job["settings"].pop(name, None)
        job.pop("cancel_requested", None)
        for card in job["cards"]:
            card.pop("image_path", None)
            card.pop("audio_path", None)
            card.pop("context_audio_path", None)

        finished = sum(card["status"] in TERMINAL_CARD_STATUSES for card in job["cards"])
        total = len(job["cards"])
        job["progress"] = {
            "finished": finished,
            "total": total,
            "percent": round(finished / total * 100) if total else 0,
        }
        return job

    def private_settings(self, job_id: str) -> dict:
        with self._lock:
            return copy.deepcopy(self._require(job_id)["settings"])

    def cards_for_runner(self, job_id: str) -> list[dict]:
        with self._lock:
            return copy.deepcopy(self._require(job_id)["cards"])

    def update_card(self, job_id: str, card_id: str, **changes) -> None:
        with self._lock:
            job = self._require(job_id)
            card = next((item for item in job["cards"] if item["id"] == card_id), None)
            if card is None:
                raise JobError("Карточка не найдена")
            card.update(changes)
            job["updated_at"] = datetime.now(timezone.utc).isoformat()

    def media_path(self, job_id: str, card_id: str, kind: str) -> str | None:
        field = {
            "image": "image_path",
            "audio": "audio_path",
            "context-audio": "context_audio_path",
        }.get(kind)
        if not field:
            return None
        with self._lock:
            job = self._require(job_id)
            card = next((item for item in job["cards"] if item["id"] == card_id), None)
            return card.get(field) if card else None

    def set_job(self, job_id: str, **changes) -> None:
        with self._lock:
            job = self._require(job_id)
            job.update(changes)
            if job.get("status") in TERMINAL_JOB_STATUSES:
                for name in SECRET_SETTING_NAMES:
                    job["settings"].pop(name, None)
            job["updated_at"] = datetime.now(timezone.utc).isoformat()

    def start(self, job_id: str) -> dict:
        with self._lock:
            job = self._require(job_id)
            if job["status"] != "ready":
                raise JobError("Это задание уже было запущено")
            if self._active_job_id is not None:
                raise JobError("Другое задание уже выполняется")
            self._active_job_id = job_id
            job["status"] = "running"
            job["message"] = "Подготовка генерации"

        worker = threading.Thread(target=self._run_worker, args=(job_id,), daemon=True)
        worker.start()
        return self.snapshot(job_id)

    def _run_worker(self, job_id: str) -> None:
        try:
            from generator.webui.runner import run_generation_job

            run_generation_job(self, job_id)
        except Exception as error:
            self.set_job(job_id, status="error", message=str(error))
        finally:
            with self._lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None

    def request_cancel(self, job_id: str) -> dict:
        with self._lock:
            job = self._require(job_id)
            if job["status"] != "running":
                raise JobError("Отменить можно только выполняющееся задание")
            job["cancel_requested"] = True
            job["message"] = "Остановка после текущей карточки"
        return self.snapshot(job_id)

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            return bool(self._require(job_id)["cancel_requested"])

    def _require(self, job_id: str) -> dict:
        try:
            return self._jobs[job_id]
        except KeyError as error:
            raise JobError("Задание не найдено") from error
