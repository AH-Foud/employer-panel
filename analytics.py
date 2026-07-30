# -*- coding: utf-8 -*-
# ماژول آنالیز و گزارش‌گیری هوشمند

import json, os, re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

STOP_WORDS = set(
    "و یا به از که با را این آن در برای یک است شد شود می های تا اما "
    "اگر نیز خواهد بود دارد دارند شده کرد کنید شما ما خود باید چگونه "
    "چه چرا چون هیچ همه برخی بیشتر کمتر خیلی بسیار هر همه کسی چیزی "
    "کردن کردن انجام مورد نظر دیگر حتی درباره مثل مثل".split()
)

class Analytics:
    def __init__(self, log_file="data/messages_log.json"):
        self.log_file = log_file
        self._ensure_file()

    def _ensure_file(self):
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        if not os.path.exists(self.log_file):
            self._save([])

    def _load(self):
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self, data):
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def log_message(self, user_id, first_name, text, timestamp=None):
        if not text or not text.strip():
            return
        messages = self._load()
        messages.append({
            "user_id": user_id, "first_name": first_name,
            "text": text.strip(), "timestamp": timestamp or datetime.now().isoformat()
        })
        self._save(messages)

    def log_contact(self, user_id, first_name, phone_number):
        messages = self._load()
        messages.append({
            "user_id": user_id, "first_name": first_name,
            "text": f"[اشتراک شماره تماس] {phone_number}",
            "timestamp": datetime.now().isoformat(), "type": "contact"
        })
        self._save(messages)

    def log_admin_reply(self, user_id, first_name, text):
        messages = self._load()
        messages.append({
            "user_id": user_id, "first_name": first_name,
            "text": text.strip(), "timestamp": datetime.now().isoformat(),
            "type": "admin_reply", "direction": "outgoing"
        })
        self._save(messages)

    def _extract_keywords(self, text):
        words = re.sub(r"[^\w\s]", " ", text).split()
        words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
        return Counter(words).most_common(50)

    def get_all_messages(self, limit=200, offset=0):
        messages = self._load()
        messages.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
        return messages[offset:offset + limit]

    def get_user_conversation(self, user_id):
        messages = self._load()
        conv = [m for m in messages if str(m.get("user_id")) == str(user_id)]
        conv.sort(key=lambda m: m.get("timestamp", ""))
        return conv

    def get_daily_stats(self, date_str=None):
        if date_str is None:
            date_str = datetime.now().date().isoformat()
        messages = self._load()
        day_msgs = [m for m in messages if m["timestamp"].startswith(date_str)]
        if not day_msgs:
            return {"date": date_str, "total_messages": 0, "unique_users": 0, "contacts_shared": 0, "user_counts": {}, "top_keywords": []}
        users = set(str(m["user_id"]) for m in day_msgs)
        user_counts = Counter(str(m["user_id"]) for m in day_msgs)
        contacts = sum(1 for m in day_msgs if m.get("type") == "contact")
        all_text = " ".join(m["text"] for m in day_msgs if m.get("type") != "contact")
        keywords = self._extract_keywords(all_text) if all_text else []
        user_report = {}
        for uid, count in user_counts.most_common(20):
            name = next((m["first_name"] for m in day_msgs if str(m["user_id"]) == uid), "ناشناس")
            user_report[f"{name} ({uid})"] = count
        return {"date": date_str, "total_messages": len(day_msgs), "unique_users": len(users), "contacts_shared": contacts, "user_counts": user_report, "top_keywords": [{"word": w, "count": c} for w, c in keywords[:20]]}

    def get_weekly_report(self):
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        week_start = week_ago.isoformat()
        messages = self._load()
        week_msgs = [m for m in messages if m["timestamp"] >= week_start]
        if not week_msgs:
            return {"period": f"{week_ago.date()} تا {today.date()}", "total_messages": 0, "unique_users": 0, "daily_breakdown": {}, "top_keywords": [], "active_users": []}
        daily = defaultdict(list)
        for m in week_msgs:
            daily[m["timestamp"][:10]].append(m)
        day_stats = {}
        for day, msgs in sorted(daily.items()):
            day_stats[day] = {"count": len(msgs), "users": len(set(str(m["user_id"]) for m in msgs))}
        user_msg_count = Counter(str(m["user_id"]) for m in week_msgs)
        active_users = []
        for uid, count in user_msg_count.most_common(10):
            name = next((m["first_name"] for m in week_msgs if str(m["user_id"]) == uid), "ناشناس")
            active_users.append({"user_id": uid, "name": name, "message_count": count})
        all_text = " ".join(m["text"] for m in week_msgs if m.get("type") != "contact")
        keywords = self._extract_keywords(all_text) if all_text else []
        return {"period": f"{week_ago.date()} تا {today.date()}", "total_messages": len(week_msgs), "unique_users": len(set(str(m["user_id"]) for m in week_msgs)), "daily_breakdown": day_stats, "top_keywords": [{"word": w, "count": c} for w, c in keywords[:30]], "active_users": active_users}
