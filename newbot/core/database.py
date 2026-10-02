import psycopg2
from contextlib import contextmanager
from typing import Optional, List, Tuple, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Reminder:
    user_id: int
    is_group: bool
    group_id: int
    content: str
    time_remind: datetime


class Database:
    def __init__(self, db_config: dict):
        self._config = db_config

    @contextmanager
    def connection(self):
        conn = psycopg2.connect(
            database=self._config["name"],
            user=self._config["user"],
            password=self._config["password"],
            host=self._config["host"],
            port=self._config["port"]
        )
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _execute(self, sql: str, params: tuple = None):
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor

    def insert_reminder(self, user_id: int, is_group: bool, group_id: int,
                        content: str, time_remind: str) -> None:
        self._execute(
            "INSERT INTO reminder(user_id, is_group, group_id, content, time_remind) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, is_group, group_id, content, time_remind)
        )

class JSONRepository:
    def __init__(self, json_dir: str):
        self._json_dir = json_dir

    def _get_path(self, user_id: int, is_group: bool, group_id: int) -> str:
        if is_group:
            return f"{self._json_dir}/g_{group_id}.json"
        return f"{self._json_dir}/p_{user_id}.json"

    def get(self, user_id: int, is_group: bool, group_id: int) -> dict:
        file_path = self._get_path(user_id, is_group, group_id)
        import os
        import json
        if not os.path.exists(file_path):
            return self.reset(user_id, is_group, group_id)
        with open(file_path, "r") as f:
            return json.load(f)

    def reset(self, user_id: int, is_group: bool, group_id: int) -> dict:
        file_path = self._get_path(user_id, is_group, group_id)
        import json
        status_data = {"status": "none", "data": {}, "group_bind": False}
        with open(file_path, "w") as f:
            json.dump(status_data, f)
        return status_data

    def set(self, user_id: int, is_group: bool, group_id: int, data: dict) -> None:
        file_path = self._get_path(user_id, is_group, group_id)
        import json
        with open(file_path, "w") as f:
            json.dump(data, f)
