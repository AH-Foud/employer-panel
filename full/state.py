# -*- coding: utf-8 -*-
# ماشین وضعیت (State Machine) برای مدیریت وضعیت هر کاربر

import json
import os


class StateMachine:
    def __init__(self):
        self._states = {}
        self._data = {}

    def get_state(self, user_id):
        return self._states.get(str(user_id), "IDLE")

    def set_state(self, user_id, state):
        self._states[str(user_id)] = state

    def get_data(self, user_id):
        return self._data.get(str(user_id), {})

    def set_data(self, user_id, key, value):
        uid = str(user_id)
        if uid not in self._data:
            self._data[uid] = {}
        self._data[uid][key] = value

    def reset(self, user_id):
        uid = str(user_id)
        self._states[uid] = "IDLE"
        if uid in self._data:
            del self._data[uid]

    def save(self, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = {"states": self._states, "data": self._data}
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._states = data.get("states", {})
            self._data = data.get("data", {})
        except (FileNotFoundError, json.JSONDecodeError):
            pass
