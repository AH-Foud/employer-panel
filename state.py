import json
import database as db

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
        self._data.pop(uid, None)

    def save(self, filepath):
        for uid in self._states:
            db.save_state(uid, self._states[uid], self._data.get(uid, {}))

    def load(self, filepath):
        self._states, self._data = db.load_all_states()
