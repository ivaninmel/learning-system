"""SQLite 数据访问层：所有数据仅保存在本机 data/learning_system.db。"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from paths import data_dir


class Database:
    """负责建表及应用所需的轻量 CRUD 操作。"""

    def __init__(self) -> None:
        self.connection = sqlite3.connect(data_dir() / "learning_system.db")
        self.connection.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS quick_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                happened_at TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                review_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(review_id) REFERENCES reviews(id)
            );
            CREATE TABLE IF NOT EXISTS review_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                fields_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                review_date TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '',
                content_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(category_id) REFERENCES review_categories(id)
            );
            CREATE TABLE IF NOT EXISTS video_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                keyword TEXT NOT NULL DEFAULT '',
                video_title TEXT NOT NULL DEFAULT '',
                video_url TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        defaults = [
            ("生活复盘", '["具体时间", "事件简述", "我的做法", "我的复盘", "补充复盘"]'),
            ("信奥复盘", '["题目编号", "题目名称", "题目简述", "初始思路", "卡点/坑点记录", "AC 核心思路与复杂度"]'),
        ]
        self.connection.executemany(
            "INSERT OR IGNORE INTO review_categories(name, fields_json) VALUES (?, ?)", defaults
        )
        self.connection.commit()

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return self.connection.execute(sql, params).fetchall()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        cursor = self.connection.execute(sql, params)
        self.connection.commit()
        return cursor.lastrowid

    def close(self) -> None:
        self.connection.close()
