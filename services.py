"""业务层：将界面输入转换为可保存的本地数据。"""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

from database import Database
from paths import data_dir, resource_dir


class LearningService:
    def __init__(self, database: Database) -> None:
        self.db = database

    def tags(self):
        return self.db.query("SELECT * FROM quick_tags ORDER BY id")

    def add_tag(self, name: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO quick_tags(name) VALUES (?)", (name.strip(),))

    def add_schedule(self, title: str, happened_at: datetime, notes: str = "", review_id: int | None = None) -> int:
        return self.db.execute(
            "INSERT INTO schedules(title, happened_at, notes, review_id) VALUES (?, ?, ?, ?)",
            (title.strip(), happened_at.isoformat(timespec="minutes"), notes.strip(), review_id),
        )

    def update_schedule(self, schedule_id: int, title: str, happened_at: datetime, notes: str, review_id: int | None) -> None:
        self.db.execute(
            "UPDATE schedules SET title=?, happened_at=?, notes=?, review_id=? WHERE id=?",
            (title.strip(), happened_at.isoformat(timespec="minutes"), notes.strip(), review_id, schedule_id),
        )

    def schedules(self, day: str):
        return self.db.query(
            "SELECT schedules.*, reviews.title AS review_title FROM schedules "
            "LEFT JOIN reviews ON reviews.id = schedules.review_id "
            "WHERE date(happened_at) = ? ORDER BY happened_at ASC", (day,)
        )

    def categories(self):
        return self.db.query("SELECT * FROM review_categories ORDER BY id")

    def add_category(self, name: str, fields: list[str]) -> None:
        self.db.execute("INSERT INTO review_categories(name, fields_json) VALUES (?, ?)", (name.strip(), json.dumps(fields, ensure_ascii=False)))

    def add_review(self, category_id: int, title: str, review_date: str, tags: str, content: dict[str, str]) -> int:
        return self.db.execute(
            "INSERT INTO reviews(category_id, title, review_date, tags, content_json) VALUES (?, ?, ?, ?, ?)",
            (category_id, title.strip(), review_date, tags.strip(), json.dumps(content, ensure_ascii=False)),
        )

    def update_review(self, review_id: int, category_id: int, title: str, review_date: str, tags: str, content: dict[str, str]) -> None:
        self.db.execute(
            "UPDATE reviews SET category_id=?, title=?, review_date=?, tags=?, content_json=? WHERE id=?",
            (category_id, title.strip(), review_date, tags.strip(), json.dumps(content, ensure_ascii=False), review_id),
        )

    def reviews(self, day: str = "", term: str = ""):
        sql = "SELECT reviews.*, review_categories.name AS category_name FROM reviews JOIN review_categories ON category_id = review_categories.id WHERE 1=1"
        params: list[str] = []
        if day:
            sql += " AND review_date = ?"
            params.append(day)
        if term:
            sql += " AND (title LIKE ? OR tags LIKE ? OR content_json LIKE ?)"
            params.extend([f"%{term}%"] * 3)
        return self.db.query(sql + " ORDER BY review_date DESC, id DESC", tuple(params))

    def log_video(self, action: str, keyword: str = "", title: str = "", url: str = "", duration: int = 0) -> None:
        self.db.execute(
            "INSERT INTO video_logs(action, keyword, video_title, video_url, started_at, duration_seconds) VALUES (?, ?, ?, ?, ?, ?)",
            (action, keyword, title, url, datetime.now().isoformat(timespec="seconds"), duration),
        )

    def video_logs_today(self):
        return self.db.query("SELECT * FROM video_logs WHERE date(started_at)=date('now','localtime') ORDER BY id DESC")

    @property
    def bili_bridge_path(self) -> Path:
        return data_dir() / "bili_events.jsonl"

    def launch_bili_learning_window(self, target: str) -> bool:
        """启动 Electron 受控学习窗口，不调用系统默认浏览器。"""
        root = resource_dir()
        executable = root / "node_modules" / "electron" / "dist" / "electron.exe"
        entry = root / "electron_bili" / "main.js"
        if not executable.exists() or not entry.exists():
            return False
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([str(executable), str(entry), str(self.bili_bridge_path), target], cwd=root, creationflags=flags)
        return True

    def import_bili_events(self) -> int:
        """读取 Electron 追加的事件，并转换为应用内的 SQLite 行为日志。"""
        bridge = self.bili_bridge_path
        if not bridge.exists() or not bridge.stat().st_size:
            return 0
        processing = bridge.with_suffix(".processing")
        try:
            os.replace(bridge, processing)
        except OSError:
            return 0
        imported = 0
        try:
            for line in processing.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                action = event.get("action", "")
                if action == "搜索":
                    self.log_video("搜索", keyword=event.get("keyword", ""))
                elif action == "开始学习":
                    self.log_video("开始学习", title=event.get("title", "未命名视频"), url=event.get("url", ""))
                elif action == "学习结束":
                    self.log_video("学习结束", title=event.get("title", "未命名视频"), url=event.get("url", ""), duration=int(event.get("duration", 0)))
                elif action == "拦截非学习视频":
                    self.log_video("拦截非学习视频", title=event.get("title", "未命名视频"), url=event.get("url", ""))
                else:
                    continue
                imported += 1
        finally:
            processing.unlink(missing_ok=True)
        return imported

    def fetch_bilibili_title(self, url: str) -> str:
        """使用公开视频信息接口取得标题；接口不可用时保留空标题。"""
        match = re.search(r"(?:video/|bvid=)(BV[\w]+)", url, re.IGNORECASE)
        if not match:
            return ""
        request = urllib.request.Request(
            f"https://api.bilibili.com/x/web-interface/view?bvid={match.group(1)}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return str(payload.get("data", {}).get("title", "")).strip()
        except (OSError, ValueError, json.JSONDecodeError):
            return ""
