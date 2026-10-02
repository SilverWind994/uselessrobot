import os
from typing import List, Optional


class QQNumberFileManager:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data: List[int] = []
        self._load()

    def _load(self) -> None:
        try:
            with open(self.file_path, 'r') as f:
                content = f.read().strip()
                if content:
                    self.data = [int(num.strip()) for num in content.split(',') if num.strip()]
                else:
                    self.data = []
        except FileNotFoundError:
            self.data = []
            self._save()
        except ValueError as e:
            print(f"文件包含非整数数据: {e}")
            self.data = []
        except Exception as e:
            print(f"读取文件错误: {e}")
            self.data = []

    def find(self, number: int) -> bool:
        try:
            return int(number) in self.data
        except (ValueError, TypeError):
            return False

    def add(self, number: int) -> bool:
        try:
            target = int(number)
            if target not in self.data:
                self.data.append(target)
                self._save()
                return True
            return False
        except (ValueError, TypeError):
            return False

    def remove(self, number: int) -> bool:
        try:
            target = int(number)
            if target in self.data:
                self.data.remove(target)
                self._save()
                return True
            return False
        except (ValueError, TypeError):
            return False

    def _save(self) -> None:
        try:
            content = ','.join(str(num) for num in self.data)
            with open(self.file_path, 'w') as f:
                f.write(content)
        except Exception as e:
            print(f"保存文件错误: {e}")
