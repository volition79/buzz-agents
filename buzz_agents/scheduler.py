"""Optional schedule -> native Buzz @mention. Delivery is never labeled task completion."""
from datetime import datetime, timedelta, timezone
import fcntl
import json
import logging
import os
from pathlib import Path
import re
import signal
import sqlite3
import threading
import time
from uuid import UUID
from zoneinfo import ZoneInfo
from .common import bounded, clean_env, ToolError
from .config import HEX, relay_url
from .policy import read_json


def schedule_spec(item):
    if not isinstance(item, dict) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,50}", item.get("id", "")):
        raise ToolError("invalid_schedule_id")
    if not HEX.fullmatch(item.get("bot_pubkey", "")):
        raise ToolError("invalid_schedule_bot")
    if str(UUID(item["channel_id"])) != item["channel_id"]:
        raise ToolError("invalid_schedule_channel")
    if not isinstance(item.get("prompt"), str) or not 1 <= len(item["prompt"].encode()) <= 16000:
        raise ToolError("invalid_schedule_prompt")
    if item.get("timezone", "Asia/Seoul") not in ("Asia/Seoul", "UTC"):
        raise ToolError("unsupported_schedule_timezone")
    if item.get("kind") == "daily":
        if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", item.get("time", "")):
            raise ToolError("invalid_schedule_time")
    elif item.get("kind") == "once":
        dt = datetime.fromisoformat(item["at"])
        if dt.tzinfo is None:
            raise ToolError("schedule_requires_timezone")
    else:
        raise ToolError("invalid_schedule_kind")
    return item


def due_at(item, now):
    if item["kind"] == "once":
        stamp = datetime.fromisoformat(item["at"]).timestamp()
    else:
        zone = ZoneInfo(item.get("timezone", "Asia/Seoul"))
        local = datetime.fromtimestamp(now, zone)
        hour, minute = map(int, item["time"].split(":"))
        stamp = local.replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp()
    return stamp if stamp <= now else None


def send(config, item, occurrence):
    env = clean_env()
    env.update(BUZZ_RELAY_URL=relay_url(config["relay"]), BUZZ_PRIVATE_KEY=config["private_key_hex"])
    if config.get("auth_tag"):
        env["BUZZ_AUTH_TAG"] = json.dumps(config["auth_tag"], separators=(",", ":"))
    content = f"[예약 {item['id']} / {int(occurrence)}]\n" + item["prompt"]
    code, raw, _ = bounded(["buzz", "--format", "json", "messages", "send", "--channel", item["channel_id"],
                            "--mention", item["bot_pubkey"], "--content", "-"],
                           data=content.encode(), env=env, timeout=40, limit=128 * 1024)
    result = json.loads(raw)
    if code or not isinstance(result, dict) or result.get("accepted") is not True:
        raise ToolError("schedule_delivery_unknown")


class Scheduler:
    def __init__(self, database, config, sender=send):
        self.config, self.sender = config, sender
        if not HEX.fullmatch(config.get("private_key_hex", "")):
            raise ToolError("scheduler_identity_required")
        relay_url(config["relay"])
        items = [schedule_spec(v) for v in config.get("schedules", [])]
        if len(items) > 100 or len({i["id"] for i in items}) != len(items):
            raise ToolError("duplicate_or_excessive_schedules")
        self.items = items
        self.db = sqlite3.connect(database)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS deliveries (schedule TEXT, at REAL, state TEXT, PRIMARY KEY(schedule, at))")
        self.db.execute("UPDATE deliveries SET state='unknown' WHERE state='prepared'")
        self.db.commit()

    def tick(self, now):
        if not self.config.get("enabled", False):
            return
        for item in self.items:
            if not item.get("enabled", True):
                continue
            stamp = due_at(item, now)
            if stamp is None:
                continue
            state = "skipped_late" if now - stamp > 120 else "prepared"
            with self.db:
                changed = self.db.execute("INSERT OR IGNORE INTO deliveries VALUES(?,?,?)", (item["id"], stamp, state)).rowcount
            if not changed or state != "prepared":
                continue
            try:
                self.sender(self.config, item, stamp)
                state = "delivered_not_completion"
            except Exception:
                state = "unknown"
            with self.db:
                self.db.execute("UPDATE deliveries SET state=? WHERE schedule=? AND at=?", (state, item["id"], stamp))
            logging.info("schedule:%s:%s", item["id"], state)


def main():
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    state = Path(os.environ.get("AUTOMATION_STATE", "/automation-state"))
    lock = os.open(state / "scheduler.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    config = read_json(os.environ.get("AUTOMATION_CONFIG", "/automation-config/config.json"))
    scheduler = Scheduler(state / "schedule.sqlite", config)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    while not stop.is_set():
        scheduler.tick(time.time())
        stop.wait(5)
    scheduler.db.close()
    os.close(lock)


if __name__ == "__main__":
    main()
