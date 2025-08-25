import json
import os
from typing import Dict, List, TypedDict

class Message(TypedDict):
    role: str
    content: str

class Memory:
    def __init__(self, storage_path: str = "data/memory.json"):
        self.storage_path = storage_path
        self.history: Dict[str, List[Message]] = self._load()
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)

    def _load(self) -> Dict[str, List[Message]]:
        if not os.path.exists(self.storage_path):
            return {}
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self):
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=4, ensure_ascii=False)

    def add_message(self, user_id: str, role: str, content: str):
        if user_id not in self.history:
            self.history[user_id] = []
        
        self.history[user_id].append({"role": role, "content": content})
        self._save()

    def get_history(self, user_id: str) -> List[Message]:
        return self.history.get(user_id, [])

    def clear_history(self, user_id: str):
        if user_id in self.history:
            self.history[user_id] = []
            self._save()
