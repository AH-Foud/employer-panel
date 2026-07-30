# -*- coding: utf-8 -*-
# ماژول همگام‌سازی با سایت و هوش مصنوعی برای تطبیق هوشمند SOP

import requests
import config
from datetime import datetime


def sync_data(endpoint, payload):
    if not config.SYNC_BASE_URL:
        return
    url = f"{config.SYNC_BASE_URL.rstrip('/')}/{endpoint}"
    headers = {"Content-Type": "application/json", "X-API-Key": config.SYNC_API_KEY}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code in (200, 201):
            return resp.json()
    except Exception as e:
        print(f"[Sync] Error: {endpoint} -> {e}")


def sync_user(user_id, first_name, phone, registered_at):
    sync_data("users", {"user_id": user_id, "first_name": first_name, "phone": phone, "registered_at": registered_at})

def sync_message(user_id, first_name, text, timestamp):
    sync_data("messages", {"user_id": user_id, "first_name": first_name, "text": text, "timestamp": timestamp})

def sync_sop(sop):
    sync_data("sops", sop)


def ai_match_sop(user_message, sops):
    if not config.AI_BASE_URL or not sops:
        return None
    sops_text = "\n".join([f"- {s['name']}: {s['response'][:100]}" for s in sops])
    prompt = config.AI_PROMPT.format(sops=sops_text, message=user_message)
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config.AI_API_KEY}"}
    payload = {"model": config.AI_MODEL, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": user_message}], "temperature": 0.1, "max_tokens": 50}
    try:
        resp = requests.post(config.AI_BASE_URL, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            ai_text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip().lower()
            for sop in sops:
                if sop["name"].lower() == ai_text or sop["name"].lower() in ai_text:
                    return sop
            if ai_text == "none":
                return None
    except Exception as e:
        print(f"[AI] Error: {e}")
    return None
