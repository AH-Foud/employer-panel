# -*- coding: utf-8 -*-
# وب سرور + API + پنل مدیریت
# اجرا: python web_server.py

import json, os, time, threading
from datetime import datetime
import aiofiles

import config
import bot_core
from analytics import Analytics

analytics_bot = bot_core.analytics

# ===================== FastAPI =====================
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="پنل مدیریت ربات بله", version="2.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ===================== API =====================

@app.get("/api/status")
def api_status():
    registered = bot_core.load_registered()
    sops = bot_core.load_sops()
    msgs = analytics_bot._load()
    return {
        "online": True,
        "bot_token": config.BOT_TOKEN[:12] + "..." if config.BOT_TOKEN else "تنظیم نشده",
        "admin_id": config.ADMIN_ID,
        "total_users": len(registered),
        "total_sops": len(sops),
        "total_messages": len(msgs),
        "last_updated": datetime.now().isoformat()
    }

@app.get("/api/stats")
def api_stats():
    daily = analytics_bot.get_daily_stats()
    weekly = analytics_bot.get_weekly_report()
    registered = bot_core.load_registered()
    sops = bot_core.load_sops()
    msgs = analytics_bot._load()
    msgs_sorted = sorted(msgs, key=lambda m: m.get("timestamp", ""), reverse=True)
    return {
        "daily": daily,
        "weekly": weekly,
        "users_count": len(registered),
        "sops_count": len(sops),
        "messages_count": len(msgs),
        "last_message": msgs_sorted[0] if msgs_sorted else None
    }

@app.get("/api/messages")
def api_messages(limit: int = 100, offset: int = 0, user_id: str = None):
    msgs = analytics_bot._load()
    if user_id:
        msgs = [m for m in msgs if str(m.get("user_id")) == str(user_id)]
    msgs.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
    result = msgs[offset:offset + limit]
    return {"messages": result, "total": len(msgs), "has_more": (offset + limit) < len(msgs)}

@app.get("/api/conversation/{user_id}")
def api_conversation(user_id: str):
    conv = analytics_bot.get_user_conversation(user_id)
    user_info = bot_core.load_registered().get(user_id, {})
    return {"user_id": user_id, "user_name": user_info.get("first_name", "ناشناس"), "phone": user_info.get("phone", ""), "messages": conv}

@app.get("/api/users")
def api_users():
    registered = bot_core.load_registered()
    users = []
    for uid, info in registered.items():
        msgs = analytics_bot._load()
        user_msgs = sum(1 for m in msgs if str(m.get("user_id")) == uid)
        last_msg = None
        for m in reversed(msgs):
            if str(m.get("user_id")) == uid:
                last_msg = m
                break
        users.append({
            "user_id": uid,
            "first_name": info.get("first_name", "کاربر"),
            "phone": info.get("phone", ""),
            "registered_at": info.get("registered_at", ""),
            "total_messages": user_msgs,
            "last_message": last_msg["text"][:80] if last_msg else "",
            "last_message_time": last_msg["timestamp"] if last_msg else ""
        })
    users.sort(key=lambda u: u.get("registered_at", ""), reverse=True)
    return {"users": users, "total": len(users)}

@app.get("/api/sops")
def api_sops():
    return {"sops": bot_core.load_sops()}

@app.post("/api/sops")
def api_add_sop(data: dict):
    name = data.get("name", "").strip()
    response = data.get("response", "").strip()
    if len(name) < 2 or len(response) < 5:
        raise HTTPException(400, "نام و پاسخ SOP معتبر نیست")
    sop = bot_core.add_sop(name, response, data.get("keywords", ""))
    return {"ok": True, "sop": sop}

@app.put("/api/sops/{sop_id}")
def api_update_sop(sop_id: int, data: dict):
    sop = bot_core.update_sop(sop_id, data.get("name"), data.get("response"), data.get("keywords"), data.get("smart_enabled"))
    if not sop:
        raise HTTPException(404, "SOP یافت نشد")
    return {"ok": True, "sop": sop}

@app.delete("/api/sops/{sop_id}")
def api_delete_sop(sop_id: int):
    if bot_core.delete_sop(sop_id):
        return {"ok": True}
    raise HTTPException(404, "SOP یافت نشد")

@app.delete("/api/users/{user_id}")
def api_delete_user(user_id: str):
    registered = bot_core.load_registered()
    if user_id not in registered:
        raise HTTPException(404, "کاربر یافت نشد")
    name = registered[user_id].get("first_name", "کاربر")
    bot_core.unregister_user(user_id)
    return {"ok": True, "message": f"{name} حذف شد"}

@app.post("/api/reply")
def api_reply(data: dict):
    user_id = str(data.get("user_id", ""))
    text = data.get("text", "").strip()
    if not user_id or not text:
        raise HTTPException(400, "اطلاعات ناقص")
    ok, msg = bot_core.reply_to_user(user_id, text)
    if ok:
        return {"ok": True, "message": msg}
    raise HTTPException(400, msg)

@app.post("/api/broadcast")
def api_broadcast(data: dict):
    text = data.get("text", "").strip()
    targets = data.get("targets", [])
    if len(text) < 2:
        raise HTTPException(400, "متن پیام کوتاه است")
    sent = bot_core.broadcast_message(targets if targets else None, text)
    return {"ok": True, "sent": sent}

@app.post("/api/broadcast-sop")
def api_broadcast_sop(data: dict):
    sop_id = data.get("sop_id", 0)
    targets = data.get("targets", [])
    sent = bot_core.broadcast_sop(sop_id, targets if targets else None)
    return {"ok": True, "sent": sent}

@app.get("/api/voice-url/{file_id}")
def api_voice_url(file_id: str):
    """دریافت لینک مستقیم ویس برای پخش در مرورگر"""
    url = bot_core.get_voice_file_url(file_id)
    if url:
        return {"url": url}
    raise HTTPException(404, "فایل صوتی یافت نشد")

@app.get("/api/voice-proxy/{file_id}")
def api_voice_proxy(file_id: str):
    """پراکسی فایل - پخش/نمایش فایل در مرورگر بدون افشای توکن"""
    import requests as req_lib
    file_path_obj = bot_core.api_request("getFile", {"file_id": file_id})
    if not file_path_obj or "file_path" not in file_path_obj:
        raise HTTPException(404, "فایل یافت نشد")
    fp = file_path_obj["file_path"]
    file_url = f"https://tapi.bale.ai/file/bot{config.BOT_TOKEN}/{fp}"
    try:
        resp = req_lib.get(file_url, timeout=30)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            if not ct or ct == "application/octet-stream":
                ext = fp.split(".")[-1].lower() if "." in fp else ""
                ct_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp", "ogg": "audio/ogg", "oga": "audio/ogg", "mp3": "audio/mpeg", "mp4": "video/mp4", "pdf": "application/pdf", "zip": "application/zip", "doc": "application/msword", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
                ct = ct_map.get(ext, "application/octet-stream")
            return Response(content=resp.content, media_type=ct)
    except Exception as e:
        print(f"[File Proxy] Error: {e}")
    raise HTTPException(502, "خطا در دریافت فایل")

@app.post("/api/send-voice")
async def api_send_voice(data: dict):
    """ارسال ویس از پنل ادمین به کاربر (با file_id که قبلاً از بات گرفته شده)"""
    user_id = str(data.get("user_id", ""))
    file_id = data.get("file_id", "")
    if not user_id or not file_id:
        raise HTTPException(400, "اطلاعات ناقص")
    ok, msg = bot_core.reply_voice_to_user(user_id, file_id)
    if ok:
        return {"ok": True, "message": msg}
    raise HTTPException(400, msg)

@app.post("/api/upload-voice")
async def api_upload_voice(user_id: str = Form(...), voice: UploadFile = File(...)):
    """آپلود فایل ویس ضبط شده در مرورگر و ارسال به کاربر"""
    if not user_id or not voice:
        raise HTTPException(400, "اطلاعات ناقص")
    os.makedirs(config.VOICE_DIR, exist_ok=True)
    ext = voice.filename.split(".")[-1] if voice.filename and "." in voice.filename else "ogg"
    tmp_path = os.path.join(config.VOICE_DIR, f"voice_{user_id}_{int(time.time())}.{ext}")
    content = await voice.read()
    async with aiofiles.open(tmp_path, "wb") as f:
        await f.write(content)
    ok, msg = bot_core.reply_voice_to_user(user_id, tmp_path)
    try:
        os.remove(tmp_path)
    except:
        pass
    if ok:
        return {"ok": True, "message": msg}
    raise HTTPException(400, msg)

@app.post("/api/upload-photo")
async def api_upload_photo(user_id: str = Form(...), photo: UploadFile = File(...), caption: str = Form("")):
    if not user_id or not photo:
        raise HTTPException(400, "اطلاعات ناقص")
    os.makedirs(config.VOICE_DIR, exist_ok=True)
    ext = photo.filename.split(".")[-1] if photo.filename and "." in photo.filename else "jpg"
    tmp_path = os.path.join(config.VOICE_DIR, f"photo_{user_id}_{int(time.time())}.{ext}")
    content = await photo.read()
    async with aiofiles.open(tmp_path, "wb") as f:
        await f.write(content)
    ok, msg = bot_core.reply_photo_to_user(user_id, tmp_path, caption)
    try:
        os.remove(tmp_path)
    except:
        pass
    if ok:
        return {"ok": True, "message": msg}
    raise HTTPException(400, msg)

@app.post("/api/upload-document")
async def api_upload_document(user_id: str = Form(...), document: UploadFile = File(...)):
    if not user_id or not document:
        raise HTTPException(400, "اطلاعات ناقص")
    os.makedirs(config.VOICE_DIR, exist_ok=True)
    ext = document.filename.split(".")[-1] if document.filename and "." in document.filename else "bin"
    tmp_path = os.path.join(config.VOICE_DIR, f"doc_{user_id}_{int(time.time())}.{ext}")
    content = await document.read()
    async with aiofiles.open(tmp_path, "wb") as f:
        await f.write(content)
    ok, msg = bot_core.reply_document_to_user(user_id, tmp_path)
    try:
        os.remove(tmp_path)
    except:
        pass
    if ok:
        return {"ok": True, "message": msg}
    raise HTTPException(400, msg)

@app.post("/api/upload-file")
async def api_upload_file(user_id: str = Form(...), file: UploadFile = File(...)):
    if not user_id or not file:
        raise HTTPException(400, "اطلاعات ناقص")
    os.makedirs(config.VOICE_DIR, exist_ok=True)
    content = await file.read()
    mime = file.content_type or ""
    ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "bin"
    tmp_path = os.path.join(config.VOICE_DIR, f"file_{user_id}_{int(time.time())}.{ext}")
    async with aiofiles.open(tmp_path, "wb") as f:
        await f.write(content)
    try:
        if mime.startswith("image/"):
            ok, msg = bot_core.reply_photo_to_user(user_id, tmp_path)
        elif mime.startswith("video/"):
            ok, msg = bot_core.reply_video_to_user(user_id, tmp_path)
        elif mime.startswith("audio/"):
            ok, msg = bot_core.reply_audio_to_user(user_id, tmp_path)
        else:
            ok, msg = bot_core.reply_document_to_user(user_id, tmp_path)
    finally:
        try: os.remove(tmp_path)
        except: pass
    if ok:
        return {"ok": True, "message": msg}
    raise HTTPException(400, msg)

# ===================== داشبورد =====================

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>پنل مدیریت ربات بله</title>
<link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css" rel="stylesheet">
<script>var t=localStorage.getItem('zaro-theme');if(t)document.documentElement.setAttribute('data-theme',t);var a=localStorage.getItem('zaro-accent');if(a)document.documentElement.setAttribute('data-accent',a);</script>
<script>var BASE=typeof __BASE_PATH__ !== 'undefined' ? __BASE_PATH__ : '';</script>
<style>
:root {
  --bg-primary: #121216;
  --bg-secondary: #1a1a20;
  --bg-card: rgba(26, 26, 32, 0.88);
  --bg-card-hover: rgba(32, 32, 38, 0.92);
  --bg-sidebar: rgba(14, 14, 18, 0.96);
  --border: rgba(255,255,255,0.07);
  --border-light: rgba(255,255,255,0.04);
  --border-glow: rgba(91,154,255,0.15);
  --accent: #5b9aff;
  --accent-hover: #7ab0ff;
  --accent-glow: rgba(91, 154, 255, 0.2);
  --accent-soft: rgba(91, 154, 255, 0.06);
  --accent-rgb: 91, 154, 255;
  --gold: #f0a500;
  --gold-glow: rgba(240, 165, 0, 0.18);
  --success: #0ecb81;
  --success-glow: rgba(14, 203, 129, 0.15);
  --danger: #f6465d;
  --danger-glow: rgba(246, 70, 93, 0.18);
  --text-primary: #e8e8ed;
  --text-secondary: #a0a0aa;
  --text-muted: #6e6e76;
  --radius: 12px;
  --radius-sm: 8px;
  --radius-xs: 5px;
  --shadow: 0 4px 24px rgba(0,0,0,0.5);
  --shadow-sm: 0 2px 10px rgba(0,0,0,0.4);
  --transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1.2);
}
/* ========== ACCENT THEMES ========== */
[data-accent="orange"] {
  --accent: #f97316;
  --accent-hover: #fb923c;
  --accent-glow: rgba(249, 115, 22, 0.2);
  --accent-soft: rgba(249, 115, 22, 0.06);
  --accent-rgb: 249, 115, 22;
  --border-glow: rgba(249,115,22,0.15);
}
[data-accent="red"] {
  --accent: #ef4444;
  --accent-hover: #f87171;
  --accent-glow: rgba(239, 68, 68, 0.2);
  --accent-soft: rgba(239, 68, 68, 0.06);
  --accent-rgb: 239, 68, 68;
  --border-glow: rgba(239,68,68,0.15);
}
[data-accent="purple"] {
  --accent: #8b5cf6;
  --accent-hover: #a78bfa;
  --accent-glow: rgba(139, 92, 246, 0.2);
  --accent-soft: rgba(139, 92, 246, 0.06);
  --accent-rgb: 139, 92, 246;
  --border-glow: rgba(139,92,246,0.15);
}
[data-accent="yellow"] {
  --accent: #eab308;
  --accent-hover: #facc15;
  --accent-glow: rgba(234, 179, 8, 0.2);
  --accent-soft: rgba(234, 179, 8, 0.06);
  --accent-rgb: 234, 179, 8;
  --border-glow: rgba(234,179,8,0.15);
}
[data-accent="green"] {
  --accent: #22c55e;
  --accent-hover: #4ade80;
  --accent-glow: rgba(34, 197, 94, 0.2);
  --accent-soft: rgba(34, 197, 94, 0.06);
  --accent-rgb: 34, 197, 94;
  --border-glow: rgba(34,197,94,0.15);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Vazirmatn', 'Tahoma', 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg-primary);
  background-image: radial-gradient(ellipse at 20% 50%, rgba(var(--accent-rgb),0.04) 0%, transparent 60%);
  color: var(--text-primary);
  display: flex;
  min-height: 100vh;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  transition: background 0.4s ease, color 0.4s ease;
}
[data-accent] body, [data-accent] * { transition: border-color 0.35s ease, box-shadow 0.35s ease, background 0.35s ease, color 0.25s ease; }
/* ========== PARTICLES CANVAS ========== */
#particles-canvas {
  position: fixed; inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.3;
}
/* ========== SIDEBAR ========== */
.sidebar {
  width: 268px;
  min-width: 268px;
  background: rgba(8,8,10,0.96);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 100;
  transition: var(--transition);
}
.logo-area {
  padding: 24px 20px;
  display: flex;
  align-items: center;
  gap: 14px;
  border-bottom: 1px solid var(--border);
}
.logo-icon {
  width: 48px; height: 48px;
  background: rgba(8,12,22,0.95);
  border: 1px solid rgba(var(--accent-rgb),0.2);
  border-radius: 16px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: inset 0 0 20px rgba(var(--accent-rgb),0.04);
  flex-shrink: 0;
}
.logo-icon svg { width: 40px; height: 40px; }
.logo-ring-outer { animation: logoSpinCW 14s linear infinite; }
.logo-ring-mid { animation: logoSpinCCW 8s linear infinite; }
.logo-ring-dots { animation: logoSpinCW 12s linear infinite; }
.logo-ring-core { animation: logoSpinCCW 6s linear infinite; }
@keyframes logoSpinCW { to { transform: rotate(360deg); } }
@keyframes logoSpinCCW { to { transform: rotate(-360deg); } }
.logo-text {
  font-size: 17px;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: -0.3px;
  line-height: 1.3;
  font-family: 'Vazirmatn', 'Tahoma', 'Segoe UI', system-ui, sans-serif;
  background: linear-gradient(135deg, #ffffff 0%, #c4d5f0 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.logo-sub {
  font-size: 10px;
  color: var(--accent);
  font-weight: 600;
  letter-spacing: 2px;
  font-family: 'Vazirmatn', 'Tahoma', 'Segoe UI', system-ui, sans-serif;
  text-transform: uppercase;
}

.nav-list { list-style: none; padding: 12px 12px; flex: 1; }
.nav-item {
  margin-bottom: 4px;
  border-radius: var(--radius-sm);
  transition: var(--transition);
  cursor: pointer;
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px;
  color: var(--text-secondary);
  font-size: 14px; font-weight: 500;
  position: relative;
  border: none; background: none;
  width: 100%; text-align: right;
  font-family: 'Vazirmatn', system-ui, sans-serif;
}
.nav-item:hover { background: rgba(var(--accent-rgb),0.03); color: var(--text-primary); }
.nav-item {
  transition: all 0.3s cubic-bezier(0.25,0.8,0.25,1.2);
  position: relative; overflow: hidden;
}
.nav-item::before {
  content: '';
  position: absolute; right: 0; top: 50%;
  width: 3px; height: 0;
  background: linear-gradient(180deg, var(--accent), #a78bfa);
  border-radius: 0 3px 3px 0;
  transform: translateY(-50%);
  transition: height 0.3s cubic-bezier(0.25,0.8,0.25,1.2);
}
.nav-item:hover::before { height: 60%; }
.nav-item.active::before { height: 75%; opacity: 1; }
.nav-item.active {
  background: rgba(255,255,255,0.05);
  color: #ffffff;
}
.nav-icon { width: 20px; height: 20px; text-align: center; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
.nav-icon svg { width: 20px; height: 20px; color: var(--text-secondary); }
.nav-item.active .nav-icon svg { color: #ffffff; }
.nav-item:hover .nav-icon svg { color: var(--text-primary); }
.nav-badge {
  margin-right: auto;
  background: var(--accent);
  color: #fff; font-size: 11px;
  padding: 2px 8px; border-radius: 10px; font-weight: 600;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid var(--border);
}
/* ========== THEME TOGGLE ========== */
.theme-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.theme-btn {
  width: 40px; height: 40px;
  border-radius: 50%;
  border: 1.5px solid rgba(255,255,255,0.15);
  background: rgba(255,255,255,0.06);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
  transition: all 0.35s cubic-bezier(0.25,0.8,0.25,1.2);
  flex-shrink: 0;
  position: relative;
  overflow: visible;
}
.theme-btn:hover {
  border-color: var(--accent);
  background: rgba(var(--accent-rgb),0.12);
  box-shadow: 0 0 18px rgba(var(--accent-rgb),0.25);
  transform: scale(1.08);
}
.theme-btn:active { transform: scale(0.92); }
.theme-icon-sun, .theme-icon-moon {
  transition: opacity 0.35s ease, transform 0.4s cubic-bezier(0.25,0.8,0.25,1.2);
  pointer-events: none;
  display: flex; align-items: center; justify-content: center;
}
.theme-icon-moon { opacity: 1; transform: scale(1) rotate(0deg); position: static; color: #ffffff; }
.theme-icon-sun { opacity: 0; transform: scale(0.3) rotate(-90deg); position: absolute; color: #f59e0b; }
[data-theme="light"] .theme-icon-moon { opacity: 0; transform: scale(0.3) rotate(90deg); position: absolute; }
[data-theme="light"] .theme-icon-sun { opacity: 1; transform: scale(1) rotate(0deg); position: static; color: #f59e0b; }

/* ========== THEME PICKER ========== */
.theme-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 16px 8px;
  border-radius: var(--radius-sm);
  border: 1.5px solid var(--border);
  background: var(--bg-secondary);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.25,0.8,0.25,1.2);
  position: relative;
  overflow: hidden;
}
.theme-option:hover {
  border-color: var(--accent);
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.15);
}
.theme-option.active {
  border-color: var(--accent);
  background: rgba(var(--accent-rgb),0.08);
  box-shadow: 0 0 0 1px var(--accent);
}
.theme-option:active { transform: scale(0.96); }
.theme-swatch {
  width: 38px; height: 38px;
  border-radius: 50%;
  display: block;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.theme-option:hover .theme-swatch { transform: scale(1.15); box-shadow: 0 4px 16px rgba(0,0,0,0.2); }
.theme-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: 'Vazirmatn', 'Tahoma', system-ui, sans-serif;
}
.theme-badge {
  font-size: 9px;
  color: var(--accent);
  background: rgba(var(--accent-rgb),0.12);
  padding: 1px 8px;
  border-radius: 20px;
  font-weight: 500;
  line-height: 1.6;
  font-family: 'Vazirmatn', 'Tahoma', system-ui, sans-serif;
}
/* ========== THEME PREVIEW ========== */
.theme-preview-area {
  margin-top: 12px;
  padding: 20px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  transition: all 0.3s ease;
}
.preview-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  transition: all 0.3s ease;
}
.preview-header {
  padding: 12px 16px;
  font-weight: 700;
  font-size: 14px;
  color: var(--text-primary);
  border-bottom: 1.5px solid var(--accent);
  background: rgba(var(--accent-rgb),0.04);
  font-family: 'Vazirmatn', 'Tahoma', system-ui, sans-serif;
}
.preview-body {
  padding: 16px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.7;
}
.preview-actions {
  padding: 12px 16px;
  display: flex;
  gap: 10px;
  border-top: 1px solid var(--border);
}
.theme-picker-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-top: 14px;
}
@media (max-width: 900px) {
  .theme-picker-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 500px) {
  .theme-picker-grid { grid-template-columns: repeat(2, 1fr); }
}

/* ========== LIGHT THEME ========== */
[data-theme="light"] {
  --bg-primary: #f5f4f0;
  --bg-secondary: #ffffff;
  --bg-card: rgba(255,255,255,0.92);
  --bg-card-hover: rgba(255,255,255,1);
  --bg-sidebar: rgba(248,247,243,0.96);
  --border: rgba(0,0,0,0.07);
  --border-light: rgba(0,0,0,0.03);
  --border-glow: rgba(var(--accent-rgb),0.08);
  --text-primary: #1d1d1f;
  --text-secondary: #6e6e73;
  --text-muted: #aeaeb2;
  --shadow: 0 2px 16px rgba(0,0,0,0.05);
  --shadow-sm: 0 1px 6px rgba(0,0,0,0.04);
  --accent-soft: rgba(var(--accent-rgb),0.07);
}
[data-theme="light"] body { background: #f7f6f3; }
[data-theme="light"] .sidebar { background: rgba(250,249,246,0.95); }
[data-theme="light"] .logo-icon { background: rgba(255,255,255,0.95); border-color: rgba(var(--accent-rgb),0.1); }
[data-theme="light"] .logo-text { background: linear-gradient(135deg, #1d1d1f 0%, var(--accent) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
[data-theme="light"] .logo-sub { color: var(--accent); }
[data-theme="light"] .nav-item { color: #6e6e73; }
[data-theme="light"] .nav-item:hover { background: rgba(0,0,0,0.03); color: #2c2c2e; }
[data-theme="light"] .nav-item.active { background: rgba(var(--accent-rgb),0.06); color: #2c2c2e; }
[data-theme="light"] .stat-card { background: rgba(255,255,255,0.85); box-shadow: 0 2px 12px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04); }
[data-theme="light"] .chart-card { background: rgba(255,255,255,0.8); box-shadow: 0 2px 12px rgba(0,0,0,0.05), 0 0 0 1px rgba(0,0,0,0.03); }
[data-theme="light"] .sop-card { background: rgba(255,255,255,0.8); box-shadow: 0 2px 12px rgba(0,0,0,0.05), 0 0 0 1px rgba(0,0,0,0.03); }
[data-theme="light"] .users-panel { background: rgba(255,255,255,0.85); box-shadow: 0 2px 16px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04); }
[data-theme="light"] .chat-panel { background: rgba(255,255,255,0.85); box-shadow: 0 2px 16px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04); }
[data-theme="light"] .modal { background: rgba(255,255,255,0.96); box-shadow: 0 8px 40px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.05); }
[data-theme="light"] .toast { background: rgba(255,255,255,0.94); box-shadow: 0 4px 24px rgba(0,0,0,0.1), 0 0 0 1px rgba(0,0,0,0.04); }
[data-theme="light"] .sidebar { box-shadow: 0 0 30px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04); }
[data-theme="light"] .stat-card:hover { box-shadow: 0 8px 30px rgba(0,0,0,0.1), 0 0 0 1px rgba(var(--accent-rgb),0.15) !important; }
[data-theme="light"] .chart-card:hover { border-color: rgba(var(--accent-rgb),0.2); box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
[data-theme="light"] .page-header { background: linear-gradient(180deg, rgba(247,246,243,0.9) 30%, rgba(247,246,243,0.3) 85%, transparent 100%); }
[data-theme="light"] .page-title { color: #2c2c2e; }
[data-theme="light"] .stat-value { color: #2c2c2e; }
[data-theme="light"] .chat-input { background: rgba(0,0,0,0.03); color: #2c2c2e; border-color: rgba(0,0,0,0.06); }
[data-theme="light"] .sop-response { background: rgba(0,0,0,0.02); }
[data-theme="light"] .sop-title { color: #b8860b; }
[data-theme="light"] .stat-card::before { background: linear-gradient(90deg, var(--accent), #818cf8, #f0a500); }
[data-theme="light"] #particles-canvas { opacity: 0.12; }
[data-theme="light"] .theme-btn { border-color: rgba(0,0,0,0.12); background: rgba(0,0,0,0.03); }
[data-theme="light"] .theme-btn:hover { border-color: var(--accent); background: rgba(var(--accent-rgb),0.1); }

/* ========== MAIN ========== */
/* ========== DASHBOARD BANNER ========== */
.dashboard-banner {
  position: relative;
  border-radius: var(--radius);
  overflow: hidden;
  margin-bottom: 28px;
  padding: 32px 36px;
  background: linear-gradient(135deg, rgba(22,24,32,0.95) 0%, rgba(14,16,26,0.95) 50%, rgba(22,18,32,0.95) 100%);
  border: 1px solid rgba(var(--accent-rgb),0.12);
  box-shadow: 0 4px 30px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.03);
}
.banner-glow {
  position: absolute;
  top: -50%; left: -50%; width: 200%; height: 200%;
  background: radial-gradient(ellipse at 30% 20%, rgba(var(--accent-rgb),0.08) 0%, transparent 50%),
              radial-gradient(ellipse at 70% 80%, rgba(167,139,250,0.06) 0%, transparent 50%);
  animation: bannerShift 8s ease-in-out infinite;
  pointer-events: none; z-index: 0;
}
@keyframes bannerShift {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(1%, -1%) scale(1.02); }
  66% { transform: translate(-1%, 1%) scale(1.01); }
}
.banner-content { position: relative; z-index: 1; }
.banner-greeting {
  font-size: 15px; font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 16px;
}
.banner-stats { display: flex; align-items: center; gap: 24px; }
.banner-stat { display: flex; flex-direction: column; gap: 2px; }
.banner-stat-val {
  font-size: 28px; font-weight: 900;
  color: #ffffff;
  letter-spacing: -0.5px;
  font-family: 'Vazirmatn', 'Tahoma', system-ui, sans-serif;
}
.banner-stat-label { font-size: 11px; color: var(--text-muted); font-weight: 400; }
.banner-stat-divider { width: 1px; height: 36px; background: rgba(255,255,255,0.08); flex-shrink: 0; }
[data-theme="light"] .dashboard-banner {
  background: linear-gradient(135deg, rgba(245,243,240,0.95) 0%, rgba(255,255,255,0.95) 50%, rgba(245,240,248,0.95) 100%);
  border-color: rgba(var(--accent-rgb),0.1);
  box-shadow: 0 4px 24px rgba(0,0,0,0.06), inset 0 1px 0 rgba(0,0,0,0.03);
}
[data-theme="light"] .banner-stat-val { color: #2c2c2e; }
[data-theme="light"] .banner-stat-divider { background: rgba(0,0,0,0.08); }

/* ========== MAIN ========== */
.main {
  flex: 1;
  margin-right: 268px;
  padding: 36px 40px;
  min-height: 100vh;
  max-width: 1200px;
  position: relative;
  z-index: 1;
}
.page { display: none; animation: fadeInUp 0.3s ease; }
.page.active { display: block; }

@keyframes fadeIn { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(32px); } to { opacity: 1; transform: translateY(0); } }
@keyframes slideIn { from { opacity: 0; transform: translateX(-30px); } to { opacity: 1; transform: translateX(0); } }
@keyframes slideInRight { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes popIn {
  0% { transform: scale(0.85); opacity: 0; }
  50% { transform: scale(1.04); }
  100% { transform: scale(1); opacity: 1; }
}
@keyframes countUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes glowPulse {
  0%, 100% { box-shadow: 0 0 4px var(--success); }
  50% { box-shadow: 0 0 16px var(--success), 0 0 32px rgba(14,203,129,0.3); }
}
@keyframes shimmerBg {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
@keyframes barGrow {
  from { width: 0% !important; }
}

/* ========== HEADER ========== */
.page-header {
  position: sticky;
  top: 0;
  z-index: 50;
  margin-bottom: 32px;
  margin-left: -40px;
  margin-right: -40px;
  padding: 20px 40px 18px 40px;
  background: linear-gradient(180deg, var(--bg-primary) 30%, rgba(18,18,22,0.3) 85%, transparent 100%);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(6px);
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
/* header — subtle top accent line, right-to-left reveal */
.page-header::before {
  content: '';
  position: absolute;
  top: -2px; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent 0%, transparent 30%, var(--accent) 50%, transparent 70%, transparent 100%);
  opacity: 0;
  transition: opacity 0.5s ease, transform 0.5s cubic-bezier(0.25,0.8,0.25,1.2);
  pointer-events: none;
  transform: scaleX(0.2);
  transform-origin: right center;
  border-radius: 0 0 2px 2px;
}
.nav-dashboard .page-header::before,
.nav-messages .page-header::before,
.nav-users .page-header::before,
.nav-sops .page-header::before,
.nav-analytics .page-header::before,
.nav-broadcast .page-header::before,
.nav-themes .page-header::before {
  opacity: 0.8;
  transform: scaleX(1);
}
/* on hover over the page, full brightness */
.page-header:hover::before { opacity: 1; }
/* extra glow below the line */
.page-header::after {
  content: '';
  position: absolute;
  bottom: -1px; left: 0;
  width: 100px; height: 2.5px;
  background-size: 200% 100%;
  border-radius: 3px;
  background-image: linear-gradient(90deg, var(--accent), rgba(var(--accent-rgb),0.3), var(--accent));
  opacity: 0.7;
  animation: headerLine 3s ease-in-out infinite;
}
@keyframes headerLine {
  0%, 100% { background-position: 0% 50%; opacity: 0.5; width: 60px; }
  50% { background-position: 100% 50%; opacity: 1; width: 120px; }
}
.page-title {
  font-size: 28px;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: -0.4px;
  line-height: 1.3;
  transition: all 0.4s ease;
}
.page-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 6px;
  font-weight: 400;
  transition: all 0.4s ease;
}

/* ========== DOPAMINE MICRO-INTERACTIONS ========== */
.btn { position: relative; overflow: hidden; }
.btn::after {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(circle at center, rgba(255,255,255,0.3) 0%, transparent 70%);
  opacity: 0; transition: opacity 0.4s ease; pointer-events: none;
}
.btn:active::after { opacity: 1; transition: opacity 0s; }
.btn:active { transform: scale(0.96); }
.nav-item {
  position: relative;
  transition: all 0.35s cubic-bezier(0.25,0.8,0.25,1.2);
  overflow: hidden;
}
.nav-item::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at var(--mx,50%) var(--my,50%), rgba(var(--accent-rgb),0.08) 0%, transparent 70%);
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}
.nav-item:hover::after { opacity: 1; }
.nav-item.active { transition: all 0.35s cubic-bezier(0.25,0.8,0.25,1.2); }
.nav-item.active .nav-icon { transform: scale(1.15) translateX(-2px); transition: transform 0.3s ease; }
.nav-item .nav-icon { transition: transform 0.3s ease, color 0.3s ease; }
.nav-item:hover .nav-icon { transform: scale(1.08); }
.msg-bubble { animation: popIn 0.35s cubic-bezier(0.25,0.8,0.25,1.2); }

/* ========== MICRO EFFECTS (LIGHT) ========== */
/* elegant card hover — soft lift + border glow */
.stat-card { transition: transform 0.35s cubic-bezier(0.25,0.8,0.25,1.2), border-color 0.3s ease, box-shadow 0.3s ease; }
.stat-card:hover { transform: translateY(-2px); border-color: rgba(var(--accent-rgb),0.2); box-shadow: 0 8px 32px rgba(0,0,0,0.08), 0 0 0 1px rgba(var(--accent-rgb),0.08); }
.chart-card { transition: border-color 0.3s ease, box-shadow 0.3s ease, transform 0.3s ease; }
.chart-card:hover { border-color: rgba(var(--accent-rgb),0.2); box-shadow: 0 4px 24px rgba(0,0,0,0.06), 0 0 20px rgba(var(--accent-rgb),0.06); }

/* page enter — gentle reveal */
.page.active {
  animation: pageReveal 0.45s cubic-bezier(0.22,0.61,0.36,1);
}
@keyframes pageReveal {
  0% { opacity: 0; transform: translateY(12px); }
  100% { opacity: 1; transform: translateY(0); }
}

/* stat value — soft counter pulse */
@keyframes valueGlow {
  0%, 100% { filter: brightness(1); }
  50% { filter: brightness(1.08); }
}

/* smooth user/item interaction */
.user-item { transition: transform 0.2s ease, background 0.15s ease; }
.user-item:hover { background: rgba(var(--accent-rgb),0.04); transform: translateX(-2px); }
.users-table tr td { transition: background 0.12s ease; }
.users-table tr:hover td { background: rgba(var(--accent-rgb),0.03); }
.form-input:hover, .form-textarea:hover { border-color: rgba(var(--accent-rgb),0.2); }
.modal-overlay { transition: opacity 0.15s ease; }
.modal-overlay:not(.show) { opacity: 0; pointer-events: none; }

/* ========== CARDS ========== */
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 18px; margin-bottom: 28px; }
.stat-card {
  background: rgba(26,26,32,0.9);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px 28px;
  transition: all 0.35s cubic-bezier(0.25,0.8,0.25,1.2);
  position: relative; overflow: hidden;
  cursor: default;
  animation: fadeInUp 0.35s ease backwards;
  box-shadow: 0 2px 12px rgba(0,0,0,0.2);
}
.stat-card:hover { transform: translateY(-3px); border-color: rgba(var(--accent-rgb),0.2); box-shadow: 0 8px 32px rgba(0,0,0,0.3), 0 0 0 1px rgba(var(--accent-rgb),0.08); }
.stat-card:nth-child(1) { animation-delay: 0.03s; }
.stat-card:nth-child(2) { animation-delay: 0.08s; }
.stat-card:nth-child(3) { animation-delay: 0.13s; }
.stat-card:nth-child(4) { animation-delay: 0.18s; }
.stat-card::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, var(--accent), #6c5ce7, var(--gold));
  opacity: 0; transition: var(--transition);
}
.stat-card::after {
  content: '';
  position: absolute;
  bottom: 0; right: 0;
  width: 100px; height: 100px;
  background: radial-gradient(circle at bottom right, rgba(79,143,255,0.06), transparent 70%);
  opacity: 0;
  transition: var(--transition);
}
.stat-card:hover::before { opacity: 1; }
.stat-card:hover::after { opacity: 1; }
.stat-icon {
  width: 32px; height: 32px;
  margin-bottom: 16px;
  display: flex; align-items: center; justify-content: center;
  color: var(--accent);
  opacity: 0.8;
}
.stat-icon svg { width: 28px; height: 28px; }
.stat-value {
  font-size: 38px;
  font-weight: 900;
  color: #ffffff;
  letter-spacing: -0.5px;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  font-family: 'Vazirmatn', 'Tahoma', -apple-system, sans-serif;
}
.stat-label { font-size: 12px; color: var(--text-muted); margin-top: 6px; font-weight: 400; letter-spacing: -0.1px; }

/* ========== MESSAGES ========== */
.messages-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
  height: calc(100vh - 180px);
}
.users-panel {
  background: rgba(22,22,24,0.85);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  display: flex; flex-direction: column;
}
.panel-header {
  padding: 16px;
  border-bottom: 1px solid var(--border);
  font-weight: 700; font-size: 15px;
  color: var(--text-primary);
}
.user-list { flex: 1; overflow-y: auto; }
.user-item {
  padding: 14px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  cursor: pointer;
  transition: var(--transition);
  display: flex; align-items: center; gap: 12px;
  border: none; background: none;
  width: 100%; text-align: right;
  font-family: 'Vazirmatn', system-ui, sans-serif;
  color: var(--text-primary);
}
.user-item:hover { background: var(--bg-card-hover); }
.user-item.selected { background: rgba(59,130,246,0.1); border-right: 3px solid var(--accent); }
.user-avatar {
  width: 40px; height: 40px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), #6366f1);
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 700; color: #fff; flex-shrink: 0;
}
.user-info { flex: 1; min-width: 0; }
.user-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.user-last-msg { font-size: 11px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.user-time { font-size: 10px; color: var(--text-muted); flex-shrink: 0; }

.chat-panel {
  background: rgba(22,22,24,0.85);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: flex; flex-direction: column;
  overflow: hidden;
}
.chat-header {
  padding: 16px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 12px;
}
.chat-avatar {
  width: 40px; height: 40px; border-radius: 50%;
  background: linear-gradient(135deg, var(--gold), var(--accent));
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; color: #fff; flex-shrink: 0;
}
.chat-user-detail { flex: 1; }
.chat-user-name { font-size: 15px; font-weight: 700; }
.chat-user-meta { font-size: 11px; color: var(--text-muted); }
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex; flex-direction: column; gap: 8px;
}
.chat-empty {
  flex: 1;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-muted); font-size: 14px;
  flex-direction: column; gap: 12px;
}
.chat-empty-icon { font-size: 48px; opacity: 0.3; }
.msg-bubble {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 13px; line-height: 1.7;
  position: relative;
  animation: slideIn 0.3s ease;
  box-shadow: 0 1px 4px rgba(0,0,0,0.12);
}
.msg-incoming {
  align-self: flex-end;
  background: linear-gradient(135deg, #4f8fff, #3b6fdd);
  color: #fff;
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 10px rgba(79,143,255,0.15);
}
.msg-outgoing {
  align-self: flex-start;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  color: var(--text-primary);
  border-bottom-right-radius: 4px;
}
.msg-system {
  align-self: center;
  background: rgba(245,158,11,0.1);
  color: var(--gold);
  font-size: 11px; padding: 6px 12px; border-radius: 20px;
}
.msg-time { font-size: 10px; opacity: 0.6; margin-top: 4px; }

.chat-input-area {
  padding: 16px;
  border-top: 1px solid var(--border);
  display: flex; gap: 8px; align-items: flex-end;
}
.chat-input {
  flex: 1;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  color: var(--text-primary);
  font-family: 'Vazirmatn', sans-serif;
  font-size: 13px;
  resize: none; min-height: 44px; max-height: 120px;
  transition: var(--transition);
}
.chat-input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent), 0 0 24px rgba(var(--accent-rgb),0.2); }

/* ========== BUTTONS ========== */
.btn {
  padding: 11px 22px;
  border-radius: var(--radius-sm);
  font-family: 'Vazirmatn', system-ui, sans-serif;
  font-size: 13px; font-weight: 600;
  cursor: pointer; border: none;
  transition: var(--transition);
  display: inline-flex; align-items: center; gap: 8px;
  white-space: nowrap;
  letter-spacing: -0.1px;
}
.btn:active { transform: scale(0.96); }
.btn:disabled { opacity: 0.45; cursor: not-allowed; filter: grayscale(30%); }
.btn-primary { background: linear-gradient(135deg, var(--accent), #3b6fdd); color: #fff; box-shadow: 0 2px 8px rgba(79,143,255,0.15); }
.btn-primary:hover:not(:disabled) { background: linear-gradient(135deg, #5d99ff, var(--accent)); box-shadow: 0 4px 18px var(--accent-glow); transform: translateY(-1px); }
.btn-gold { background: linear-gradient(135deg, var(--gold), #d48900); color: #1a1200; box-shadow: 0 2px 8px rgba(240,165,0,0.15); }
.btn-gold:hover:not(:disabled) { box-shadow: 0 4px 18px var(--gold-glow); transform: translateY(-1px); }
.btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text-secondary); }
.btn-outline:hover:not(:disabled) { border-color: var(--accent); color: var(--text-primary); background: rgba(79,143,255,0.06); }
.btn-danger { background: linear-gradient(135deg, #f6465d, #d63850); color: #fff; box-shadow: 0 2px 10px rgba(246,70,93,0.2); }
.btn-danger:hover:not(:disabled) { background: linear-gradient(135deg, #ff5a70, #e0334a); box-shadow: 0 4px 20px rgba(246,70,93,0.35); transform: translateY(-1px); }
.btn-sm { padding: 7px 14px; font-size: 11px; }
.btn-icon { padding: 8px; }

/* ========== SOPs ========== */
.sops-list { display: flex; flex-direction: column; gap: 12px; }
.sop-card {
  background: rgba(22,22,24,0.8);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  transition: all 0.3s cubic-bezier(0.25,0.8,0.25,1.2);
}
.sop-card:hover { transform: translateY(-3px); box-shadow: 0 12px 32px rgba(0,0,0,0.5); border-color: var(--accent); }
.sop-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 8px; }
.sop-title { font-size: 16px; font-weight: 700; color: var(--gold); }
.sop-meta { font-size: 11px; color: var(--text-muted); }
.sop-response {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.8;
  white-space: pre-wrap;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  padding: 12px;
  margin-bottom: 12px;
}
.sop-actions { display: flex; gap: 8px; }
.sop-keywords { font-size: 11px; color: var(--text-secondary); padding: 6px 0 10px; }
.kw-badge { display: inline-block; font-size: 10px; padding: 1px 6px; border-radius: 4px; background: rgba(var(--accent-rgb),0.1); color: var(--accent); margin-left: 4px; }

/* ========== FORMS ========== */
.form-group { margin-bottom: 18px; }
.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
  display: block;
  letter-spacing: -0.1px;
}
.form-input, .form-textarea {
  width: 100%;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 13px 16px;
  color: var(--text-primary);
  font-family: 'Vazirmatn', system-ui, sans-serif;
  font-size: 13px;
  transition: var(--transition);
  line-height: 1.7;
}
.form-input:focus, .form-textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(79,143,255,0.15); }
.form-textarea { min-height: 110px; resize: vertical; }
select.form-input { cursor: pointer; appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%2399a8bb' stroke-width='2' fill='none' stroke-linecap='round'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: left 14px center; padding-left: 40px; }

/* ========== BROADCAST ========== */
.broadcast-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.broadcast-card { padding: 28px 30px; }
.broadcast-icon-wrap {
  width: 36px; height: 36px;
  display: inline-flex; align-items: center; justify-content: center;
  background: rgba(79,143,255,0.1);
  border-radius: var(--radius-xs);
  font-size: 18px;
}
.broadcast-icon-wrap.gold { background: rgba(240,165,0,0.1); }
.broadcast-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 20px;
  line-height: 1.7;
}
.broadcast-hint strong {
  color: var(--text-secondary);
  font-weight: 700;
}
.broadcast-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 4px;
}
.broadcast-char-count {
  font-size: 11px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  font-family: 'Vazirmatn', system-ui, sans-serif;
}
.broadcast-sop-preview {
  font-size: 11px;
  color: var(--text-muted);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .broadcast-layout { grid-template-columns: 1fr; }
  .broadcast-footer { flex-direction: column; align-items: flex-start; }
}

/* ========== ANALYTICS ========== */
.chart-card {
  background: rgba(26,26,32,0.85);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px 30px;
  margin-bottom: 20px;
  transition: all 0.3s cubic-bezier(0.25,0.8,0.25,1.2);
  animation: fadeInUp 0.35s ease backwards;
  box-shadow: 0 2px 10px rgba(0,0,0,0.15);
}
.chart-card:nth-child(1) { animation-delay: 0.03s; }
.chart-card:nth-child(2) { animation-delay: 0.1s; }
.chart-card:nth-child(3) { animation-delay: 0.17s; }
.chart-card:hover { border-color: rgba(var(--accent-rgb),0.12); box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
.chart-title {
  font-size: 16px;
  font-weight: 700;
  color: #ffffff;
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.bar-chart { display: flex; flex-direction: column; gap: 10px; }
.bar-row { display: flex; align-items: center; gap: 10px; }
.bar-label { width: 65px; font-size: 12px; color: var(--text-secondary); text-align: left; flex-shrink: 0; }
.bar-track { flex: 1; height: 28px; background: var(--bg-secondary); border-radius: 7px; overflow: hidden; }
.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #6366f1);
  border-radius: 7px;
  transition: width 0.6s cubic-bezier(0.25, 0.8, 0.25, 1.2);
  min-width: 0;
}
.bar-fill.bar-gold { background: linear-gradient(90deg, var(--gold), #c78500); }
.bar-count {
  width: 60px;
  font-size: 13px;
  font-weight: 700;
  color: #ffffff;
  text-align: left;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.users-table th {
  text-align: right;
  padding: 12px 16px;
  border-bottom: 2px solid var(--border);
  color: var(--text-muted);
  font-weight: 600; font-size: 12px;
}
.users-table td {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.users-table tr:hover td { background: rgba(59,130,246,0.05); }

/* ========== MODAL ========== */
.modal-overlay {
  display: none;
  position: fixed; inset: 0;
  background: radial-gradient(ellipse at center, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.85) 100%);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  z-index: 200;
  align-items: center; justify-content: center;
}
.modal-overlay.show { display: flex; animation: fadeIn 0.25s ease; }
.modal {
  background: rgba(18,18,20,0.96);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 32px;
  width: 90%; max-width: 560px;
  animation: popIn 0.35s cubic-bezier(0.25, 0.8, 0.25, 1.2);
  max-height: 85vh; overflow-y: auto;
  box-shadow: 0 0 80px rgba(0,0,0,0.7), 0 0 40px rgba(var(--accent-rgb),0.06);
  position: relative;
}
.modal::before {
  content: '';
  position: absolute;
  top: -1px; left: 20px; right: 20px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(79,143,255,0.4), transparent);
}
.modal-title {
  font-size: 18px;
  font-weight: 800;
  color: #ffffff;
  margin-bottom: 22px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 24px; }

/* ========== DELETE CONFIRM MODAL ========== */
.confirm-modal .modal { max-width: 440px; text-align: center; padding: 36px 32px; }
.confirm-icon {
  width: 56px; height: 56px;
  margin: 0 auto 20px;
  display: flex; align-items: center; justify-content: center;
  animation: popIn 0.4s cubic-bezier(0.25,0.8,0.25,1.2);
}
.confirm-icon svg { width: 48px; height: 48px; }
.confirm-text {
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.8;
  margin-bottom: 8px;
}
.confirm-text strong {
  color: #ffffff;
  font-weight: 700;
}
.confirm-modal .modal-actions { justify-content: center; gap: 12px; }

/* ========== TOAST ========== */
.toast-container {
  position: fixed; bottom: 20px; left: 20px;
  z-index: 300;
  display: flex; flex-direction: column; gap: 8px;
}
.toast {
  background: rgba(18,18,20,0.94);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 20px;
  font-size: 13px;
  animation: slideInRight 0.4s cubic-bezier(0.25,0.8,0.25,1.2);
  box-shadow: 0 8px 30px rgba(0,0,0,0.5);
  display: flex; align-items: center; gap: 10px;
  pointer-events: auto;
  border-left: 3px solid var(--success);
}
.toast.success { border-left-color: var(--success); }
.toast.error { border-left-color: var(--danger); }

/* ========== RESPONSIVE ========== */
@media (max-width: 900px) {
  .sidebar { width: 64px; min-width: 64px; }
  .sidebar .logo-text, .sidebar .logo-sub, .sidebar .nav-item span:not(.nav-icon),
  .sidebar .nav-badge { display: none; }
  .sidebar .logo-icon { width: 36px; height: 36px; border-radius: 10px; }
  .sidebar .logo-icon svg { width: 20px; height: 20px; }
  .main { margin-right: 64px; padding: 20px; }
  .messages-layout { grid-template-columns: 1fr; }
  .users-panel { display: none; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}

/* ========== SCROLLBAR ========== */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* ========== MEDIA IN CHAT ========== */
.msg-image {
  max-width: 260px; border-radius: 10px;
  cursor: pointer; display: block;
  transition: transform 0.2s;
  border: 1px solid var(--border);
}
.msg-image:hover { transform: scale(1.02); }
.msg-file {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px;
  background: rgba(255,255,255,0.06);
  border-radius: 8px;
  color: var(--accent);
  text-decoration: none;
  font-size: 12px;
  transition: var(--transition);
}
.msg-file:hover { background: rgba(255,255,255,0.1); color: var(--accent-hover); }
.msg-file svg { width: 18px; height: 18px; flex-shrink: 0; }
.msg-file .file-name { color: var(--text-primary); word-break: break-all; }

/* ========== LOADING ========== */
.loading-spinner {
  width: 20px; height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}
.loading-text { color: var(--text-muted); font-size: 13px; display: flex; align-items: center; gap: 8px; }

/* ========== VOICE MESSAGE ========== */
.voice-msg {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 14px;
  border-radius: 14px;
  background: rgba(255,255,255,0.07);
  min-width: 220px;
  direction: ltr;
  backdrop-filter: blur(4px);
}
.voice-msg .play-btn {
  width: 40px; height: 40px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, var(--accent), #4f46e5);
  color: #fff;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
  transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1.2);
  box-shadow: 0 2px 8px rgba(var(--accent-rgb),0.25);
  position: relative;
}
.voice-msg .play-btn:hover {
  transform: scale(1.12);
  box-shadow: 0 4px 16px var(--accent-glow);
}
.voice-msg .play-btn:active { transform: scale(0.92); }
.voice-msg .play-btn.playing {
  background: linear-gradient(135deg, var(--danger), #dc2626);
  box-shadow: 0 2px 12px var(--danger-glow);
  animation: recPulse 1.2s ease infinite;
}
.voice-msg .waveform {
  flex: 1; height: 32px;
  display: flex; align-items: center;
  gap: 3px;
}
.voice-msg .waveform span {
  width: 4px; border-radius: 3px;
  background: var(--accent);
  display: inline-block;
  animation: waveAnim 1s ease infinite;
  opacity: 0.6;
}
.voice-msg .waveform span:nth-child(1) { height: 40%; animation-delay: 0s; }
.voice-msg .waveform span:nth-child(2) { height: 65%; animation-delay: 0.1s; }
.voice-msg .waveform span:nth-child(3) { height: 30%; animation-delay: 0.2s; }
.voice-msg .waveform span:nth-child(4) { height: 85%; animation-delay: 0.3s; }
.voice-msg .waveform span:nth-child(5) { height: 50%; animation-delay: 0.4s; }
.voice-msg .play-btn.playing ~ .waveform span { background: var(--danger); opacity: 0.8; }
.voice-msg .voice-duration {
  font-size: 12px; font-weight: 600;
  color: var(--text-secondary);
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.5px;
  direction: ltr;
}
@keyframes waveAnim {
  0%, 100% { transform: scaleY(0.5); }
  50% { transform: scaleY(1); }
}
.voice-record-btn {
  width: 44px; height: 44px;
  border-radius: 50%;
  border: 2px solid var(--danger);
  background: rgba(246,70,93,0.08);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1.2);
  flex-shrink: 0;
  color: var(--danger);
  position: relative;
}
.voice-record-btn svg { width: 20px; height: 20px; }
.voice-record-btn:hover {
  background: rgba(246,70,93,0.18);
  border-color: #ff5a70;
  color: #ff6b80;
  transform: scale(1.08);
  box-shadow: 0 0 16px rgba(246,70,93,0.2);
}
.voice-record-btn:active { transform: scale(0.92); }
.voice-record-btn.recording {
  background: var(--danger);
  color: #fff;
  border-color: var(--danger);
  animation: recPulse 0.8s ease infinite;
}
@keyframes recPulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(246,70,93,0.4); }
  50% { box-shadow: 0 0 0 12px rgba(246,70,93,0); }
}

/* ========== SEARCH ========== */
.search-box {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 16px;
  color: var(--text-primary);
  font-family: 'Vazirmatn', system-ui, sans-serif;
  font-size: 13px;
  width: 100%; max-width: 300px;
}
.search-box:focus { outline: none; border-color: var(--accent); }

/* ========== EMPTY STATE ========== */
.empty-state {
  text-align: center; padding: 40px 20px; color: var(--text-muted);
}
.empty-state-icon { font-size: 48px; opacity: 0.3; margin-bottom: 12px; }
</style>
</head>
<body>
<canvas id="particles-canvas"></canvas>

<!-- SIDEBAR -->
<aside class="sidebar" id="sidebar">
  <div class="logo-area">
    <div class="logo-icon">
      <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="lgA" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#5b9aff"/>
            <stop offset="50%" stop-color="#818cf8"/>
            <stop offset="100%" stop-color="#a78bfa"/>
          </linearGradient>
          <linearGradient id="lgB" x1="1" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#a78bfa"/>
            <stop offset="100%" stop-color="#5b9aff"/>
          </linearGradient>
          <linearGradient id="lgCore" x1="0.5" y1="0" x2="0.5" y2="1">
            <stop offset="0%" stop-color="#ffffff" stop-opacity="0.9"/>
            <stop offset="100%" stop-color="#5b9aff" stop-opacity="0.5"/>
          </linearGradient>
        </defs>
        <!-- outer thin ring - slow rotate -->
        <g class="logo-ring-outer" style="transform-origin:24px 24px">
          <circle cx="24" cy="24" r="22" stroke="url(#lgA)" stroke-width="0.6" fill="none" opacity="0.18" stroke-dasharray="3 12 34 12 3 18"/>
        </g>
        <!-- mid segmented orbit - fast rotate -->
        <g class="logo-ring-mid" style="transform-origin:24px 24px">
          <circle cx="24" cy="24" r="17" stroke="url(#lgB)" stroke-width="2.5" fill="none" opacity="0.5" stroke-dasharray="10 6 28 6 10 8" stroke-linecap="round"/>
        </g>
        <!-- orbital dots -->
        <g class="logo-ring-dots" style="transform-origin:24px 24px">
          <circle cx="24" cy="7" r="2.5" fill="url(#lgA)" opacity="0.8"/>
          <circle cx="41" cy="24" r="2.5" fill="url(#lgB)" opacity="0.6"/>
          <circle cx="24" cy="41" r="2.5" fill="url(#lgA)" opacity="0.8"/>
          <circle cx="7" cy="24" r="2.5" fill="url(#lgB)" opacity="0.6"/>
        </g>
        <!-- core hex spark -->
        <polygon points="24,10 36,17 36,31 24,38 12,31 12,17" stroke="url(#lgCore)" stroke-width="1.4" fill="url(#lgB)" fill-opacity="0.1" opacity="0.9"/>
        <polygon points="24,15 32,19 32,29 24,33 16,29 16,19" stroke="url(#lgCore)" stroke-width="0.9" fill="none" opacity="0.45"/>
        <!-- core counter-rotating triangle -->
        <g class="logo-ring-core" style="transform-origin:24px 24px">
          <polygon points="24,20 30,27 18,27" stroke="#a78bfa" stroke-width="1" fill="none" opacity="0.35"/>
        </g>
        <!-- central pulse node -->
        <circle cx="24" cy="24" r="3.2" fill="white" opacity="0.95">
          <animate attributeName="r" values="3.2;4.5;3.2" dur="2s" repeatCount="indefinite"/>
          <animate attributeName="opacity" values="0.95;0.5;0.95" dur="2s" repeatCount="indefinite"/>
        </circle>
        <!-- inner glow ring -->
        <circle cx="24" cy="24" r="7" stroke="url(#lgCore)" stroke-width="0.7" fill="none" opacity="0.25">
          <animate attributeName="r" values="7;8.5;7" dur="3s" repeatCount="indefinite"/>
          <animate attributeName="opacity" values="0.25;0.08;0.25" dur="3s" repeatCount="indefinite"/>
        </circle>
        <!-- outer orbit glow ring -->
        <circle cx="24" cy="24" r="22" stroke="url(#lgA)" stroke-width="3" fill="none" opacity="0.06">
          <animate attributeName="opacity" values="0.06;0.12;0.06" dur="4s" repeatCount="indefinite"/>
        </circle>
      </svg>
    </div>
    <div>
      <div class="logo-text">پنل پیام‌رسان</div>
      <div class="logo-sub">مدیریت هوشمند</div>
    </div>
  </div>
  <ul class="nav-list" id="nav-list">
    <li><button class="nav-item active" data-page="dashboard"><span class="nav-icon"><svg viewBox="0 0 20 20" fill="none"><rect x="3" y="12" width="3.5" height="6" rx="1" fill="currentColor" opacity=".85"/><rect x="8.25" y="7" width="3.5" height="11" rx="1" fill="currentColor" opacity=".85"/><rect x="13.5" y="3" width="3.5" height="15" rx="1" fill="currentColor" opacity=".4"/></svg></span> <span>داشبورد</span></button></li>
    <li><button class="nav-item" data-page="messages"><span class="nav-icon"><svg viewBox="0 0 20 20" fill="none"><path d="M10 2C5.58 2 2 5.13 2 9c0 2.1 1.1 3.95 2.8 5.1L4 17l3.2-1.6c.9.4 1.85.6 2.8.6 4.42 0 8-3.13 8-7s-3.58-7-8-7z" stroke="currentColor" stroke-width="1.6" fill="none"/><circle cx="7.5" cy="9" r="1.2" fill="currentColor" opacity=".85"/><circle cx="10" cy="9" r="1.2" fill="currentColor" opacity=".85"/><circle cx="12.5" cy="9" r="1.2" fill="currentColor" opacity=".85"/></svg></span> <span>پیام‌ها</span> <span class="nav-badge" id="unread-badge" style="display:none">0</span></button></li>
    <li><button class="nav-item" data-page="users"><span class="nav-icon"><svg viewBox="0 0 20 20" fill="none"><circle cx="6" cy="6" r="3" stroke="currentColor" stroke-width="1.6" fill="none"/><path d="M1 17c0-2.76 2.24-5 5-5 2.76 0 5 2.24 5 5" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round"/><circle cx="15" cy="8" r="2.2" stroke="currentColor" stroke-width="1.4" fill="none" opacity=".6"/><path d="M12 17c0-1.66 1.34-3 3-3s3 1.34 3 3" stroke="currentColor" stroke-width="1.4" fill="none" stroke-linecap="round" opacity=".6"/></svg></span> <span>کاربران</span></button></li>
    <li><button class="nav-item" data-page="sops"><span class="nav-icon"><svg viewBox="0 0 20 20" fill="none"><rect x="3" y="2" width="13" height="16" rx="2" stroke="currentColor" stroke-width="1.5" fill="none"/><line x1="6" y1="6" x2="14" y2="6" stroke="currentColor" stroke-width="1.2" opacity=".6"/><line x1="6" y1="9" x2="14" y2="9" stroke="currentColor" stroke-width="1.2" opacity=".85"/><line x1="6" y1="12" x2="11" y2="12" stroke="currentColor" stroke-width="1.2" opacity=".4"/><circle cx="16" cy="13" r="4" fill="var(--accent)" opacity=".2"/></svg></span> <span>راهنماها (SOP)</span></button></li>
    <li><button class="nav-item" data-page="analytics"><span class="nav-icon"><svg viewBox="0 0 20 20" fill="none"><polyline points="4,16 7,11 10,13 13,7 16,4" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/><circle cx="16" cy="4" r="1.8" fill="currentColor" opacity=".85"/></svg></span> <span>گزارش‌ها</span></button></li>
    <li><button class="nav-item" data-page="broadcast"><span class="nav-icon"><svg viewBox="0 0 20 20" fill="none"><path d="M3 11V9l4-3v8l-4-3z" fill="currentColor" opacity=".85"/><path d="M7 14l2 3h1l1-3" stroke="currentColor" stroke-width="1.2" fill="none" opacity=".7"/><path d="M11 8c.8.5 1.5 1.2 1.5 2s-.7 1.5-1.5 2" stroke="currentColor" stroke-width="1.3" fill="none" opacity=".5"/><path d="M13 6c1.5 1 2.5 2.5 2.5 4s-1 3-2.5 4" stroke="currentColor" stroke-width="1.3" fill="none" opacity=".3"/></svg></span> <span>ارسال همگانی</span></button></li>
    <li><button class="nav-item" data-page="themes"><span class="nav-icon"><svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5" fill="none"/><circle cx="10" cy="10" r="3" fill="currentColor" opacity=".3"/><path d="M10 3v2M10 15v2M3 10h2M15 10h2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg></span> <span>تم‌ها</span></button></li>
  </ul>
  <div class="sidebar-footer">
    <div class="theme-row">
      <div style="display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text-muted);">
        <span class="status-dot online" id="status-dot"></span>
        <span id="status-text">در حال اتصال...</span>
      </div>
      <button class="theme-btn" id="theme-toggle" title="تغییر تم">
        <span class="theme-icon-sun"><svg viewBox="0 0 24 24" width="20" height="20" fill="none"><circle cx="12" cy="12" r="4.5" stroke="currentColor" stroke-width="1.8"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></span>
        <span class="theme-icon-moon"><svg viewBox="0 0 24 24" width="20" height="20" fill="none"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg></span>
      </button>
    </div>
    <div style="font-size:10px;color:var(--text-muted);margin-top:4px;" id="update-time"></div>
  </div>
</aside>

<!-- MAIN -->
<main class="main nav-dashboard" id="main-content">

  <!-- DASHBOARD -->
  <div class="page active" id="page-dashboard">
    <!-- ✨ Animated Banner -->
    <div class="dashboard-banner">
      <div class="banner-glow"></div>
      <div class="banner-content">
        <div class="banner-greeting">
          <svg viewBox="0 0 20 20" width="18" height="18" style="vertical-align:-3px;margin-left:4px"><circle cx="10" cy="10" r="9" stroke="var(--accent)" stroke-width="1.2" fill="none" opacity=".5"/><circle cx="10" cy="10" r="3" fill="var(--accent)" opacity=".3"/></svg>
          به پنل مدیریت خوش آمدید
        </div>
        <div class="banner-stats">
          <div class="banner-stat"><span class="banner-stat-val" id="ban-users">—</span><span class="banner-stat-label">کاربر</span></div>
          <div class="banner-stat-divider"></div>
          <div class="banner-stat"><span class="banner-stat-val" id="ban-msgs">—</span><span class="banner-stat-label">پیام</span></div>
          <div class="banner-stat-divider"></div>
          <div class="banner-stat"><span class="banner-stat-val" id="ban-online">—</span><span class="banner-stat-label">SOP فعال</span></div>
        </div>
      </div>
    </div>
    <div class="page-header"><div class="page-title">داشبورد مدیریت</div><div class="page-subtitle">نمای کلی وضعیت ربات و کاربران</div></div>
    <div class="stats-grid" id="stats-cards">
      <div class="stat-card"><div class="stat-icon"><svg viewBox="0 0 28 28" fill="none"><circle cx="9" cy="8" r="4.5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M1 26c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><circle cx="20" cy="11" r="3" stroke="currentColor" stroke-width="1.5" fill="none" opacity=".5"/><path d="M15 26c0-2.8 2.2-5 5-5s5 2.2 5 5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" opacity=".5"/></svg></div><div class="stat-value" id="stat-users">—</div><div class="stat-label">کاربران ثبت‌نام کرده</div></div>
      <div class="stat-card"><div class="stat-icon"><svg viewBox="0 0 28 28" fill="none"><path d="M14 3C7.37 3 2 7.7 2 13.5c0 3.2 1.6 6 4.2 7.7L5 26l4.8-2.4c1.3.6 2.7.9 4.2.9 6.63 0 12-4.7 12-10.5S20.63 3 14 3z" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="9.5" cy="14" r="1.8" fill="currentColor"/><circle cx="14" cy="14" r="1.8" fill="currentColor"/><circle cx="18.5" cy="14" r="1.8" fill="currentColor"/></svg></div><div class="stat-value" id="stat-msgs">—</div><div class="stat-label">کل پیام‌ها</div></div>
      <div class="stat-card"><div class="stat-icon"><svg viewBox="0 0 28 28" fill="none"><rect x="4" y="2" width="18" height="24" rx="2.5" stroke="currentColor" stroke-width="2" fill="none"/><line x1="8" y1="8" x2="20" y2="8" stroke="currentColor" stroke-width="1.5" opacity=".6"/><line x1="8" y1="13" x2="20" y2="13" stroke="currentColor" stroke-width="1.5"/><line x1="8" y1="18" x2="15" y2="18" stroke="currentColor" stroke-width="1.5" opacity=".4"/><circle cx="22" cy="19" r="5" fill="var(--accent)" opacity=".15"/></svg></div><div class="stat-value" id="stat-sops">—</div><div class="stat-label">راهنماهای تعریف شده</div></div>
      <div class="stat-card"><div class="stat-icon"><svg viewBox="0 0 28 28" fill="none"><rect x="4" y="13" width="4" height="10" rx="1" fill="currentColor" opacity=".4"/><rect x="10" y="8" width="4" height="15" rx="1" fill="currentColor" opacity=".7"/><rect x="16" y="3" width="4" height="20" rx="1" fill="currentColor"/><polyline points="16,3 20,3 20,23 16,23" stroke="var(--accent)" stroke-width="1.5" fill="none" opacity=".4"/></svg></div><div class="stat-value" id="stat-today">—</div><div class="stat-label">پیام‌های امروز</div></div>
    </div>
    <div class="chart-card"><div class="chart-title"><svg viewBox="0 0 18 18" width="16" height="16" style="vertical-align:-2px;margin-left:4px"><polyline points="3,13 6,9 9,10 12,6 15,3" stroke="var(--accent)" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/><circle cx="15" cy="3" r="1.5" fill="var(--accent)"/></svg>آمار روزانه</div><div id="daily-chart" class="loading-text"><span class="loading-spinner"></span> در حال بارگذاری...</div></div>
  </div>

  <!-- MESSAGES -->
  <div class="page" id="page-messages">
    <div class="page-header"><div class="page-title">پیام‌های کاربران</div><div class="page-subtitle">مشاهده و پاسخ به پیام‌ها</div></div>
    <div class="messages-layout">
      <div class="users-panel" id="users-panel-container">
        <div class="panel-header"><svg viewBox="0 0 16 16" width="14" height="14" style="vertical-align:-2px;margin-left:4px"><circle cx="5" cy="4" r="2.5" stroke="currentColor" stroke-width="1.3" fill="none"/><path d="M0 14c0-2.8 2.2-5 5-5s5 2.2 5 5" stroke="currentColor" stroke-width="1.3" fill="none" stroke-linecap="round"/><circle cx="12" cy="6" r="1.8" stroke="currentColor" stroke-width="1.1" fill="none" opacity=".5"/><path d="M9 14c0-1.7 1.3-3 3-3s3 1.3 3 3" stroke="currentColor" stroke-width="1.1" fill="none" stroke-linecap="round" opacity=".5"/></svg>کاربران</div>
        <div class="user-list" id="msg-user-list"><div class="loading-text" style="padding:16px;"><span class="loading-spinner"></span> در حال بارگذاری...</div></div>
      </div>
      <div class="chat-panel" id="chat-panel">
        <div id="chat-header-placeholder" class="chat-header" style="display:none">
          <div class="chat-avatar" id="chat-avatar-icon"><svg viewBox="0 0 24 24" width="22" height="22"><circle cx="12" cy="8" r="5" stroke="currentColor" stroke-width="2" fill="none"/><path d="M2 24c0-5.5 4.5-10 10-10s10 4.5 10 10" stroke="currentColor" stroke-width="2" fill="none"/></svg></div>
          <div class="chat-user-detail">
            <div class="chat-user-name" id="chat-user-name"></div>
            <div class="chat-user-meta" id="chat-user-meta"></div>
          </div>
        </div>
        <div id="chat-messages" class="chat-messages">
          <div class="chat-empty"><div class="chat-empty-icon"><svg viewBox="0 0 36 36" width="36" height="36"><path d="M18 5C8.5 5 1 11.4 1 19.5c0 4.3 2.2 8 5.5 10.3L4 31l5.3-2.7c1.4.6 2.9.9 4.5 1.1" stroke="currentColor" stroke-width="2" fill="none" opacity=".3"/><circle cx="10" cy="19" r="2" fill="currentColor" opacity=".25"/><circle cx="18" cy="19" r="2" fill="currentColor" opacity=".25"/><circle cx="26" cy="16" r="5" stroke="currentColor" stroke-width="2" fill="none" opacity=".5"/><circle cx="22" cy="19" r="2" fill="currentColor" opacity=".4"/><circle cx="26" cy="19" r="2" fill="currentColor" opacity=".4"/><circle cx="30" cy="19" r="2" fill="currentColor" opacity=".4"/></svg></div><div>یک کاربر را از لیست سمت راست انتخاب کنید</div></div>
        </div>
                <div class="chat-input-area" id="chat-input-area" style="display:none">
                  <textarea class="chat-input" id="chat-input" placeholder="پاسخ خود را بنویسید..." rows="1"></textarea>
                  <button class="btn btn-primary" id="btn-send-reply"><svg viewBox="0 0 14 14" width="13" height="13" style="vertical-align:-2px;margin-left:3px"><path d="M1 7L13 1L7 13L5 9L1 7z" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/></svg>ارسال</button>
                  <button class="btn btn-gold btn-sm" id="btn-send-sop"><svg viewBox="0 0 14 14" width="13" height="13" style="vertical-align:-2px;margin-left:3px"><rect x="2" y="1" width="9" height="12" rx="1.5" stroke="currentColor" stroke-width="1.3" fill="none"/><line x1="4" y1="4" x2="10" y2="4" stroke="currentColor" stroke-width="1.1"/><line x1="4" y1="7" x2="10" y2="7" stroke="currentColor" stroke-width="1.1"/><line x1="4" y1="10" x2="7" y2="10" stroke="currentColor" stroke-width="1.1"/></svg>SOP</button>
                  <button class="btn btn-outline btn-sm" id="btn-record-voice" title="ضبط پیام صوتی"><svg viewBox="0 0 24 24" width="20" height="20" fill="none"><rect x="9" y="2" width="6" height="11" rx="3" stroke="currentColor" stroke-width="1.8"/><path d="M5 10a7 7 0 0 0 14 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><line x1="12" y1="17" x2="12" y2="22" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></button>
                  <button class="btn btn-outline btn-sm" id="btn-attach-file" title="ارسال عکس یا فایل"><svg viewBox="0 0 24 24" width="18" height="18" fill="none"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></button>
                  <input type="file" id="file-input" accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.zip,.txt,.xlsx,.pptx" style="display:none" multiple>
                </div>
      </div>
    </div>
  </div>

  <!-- USERS -->
  <div class="page" id="page-users">
    <div class="page-header"><div class="page-title">کاربران ثبت‌نام کرده</div><div class="page-subtitle">لیست تمام کاربرانی که شماره تماس ثبت کرده‌اند</div></div>
    <div class="chart-card">
      <div style="overflow-x:auto;">
        <table class="users-table" id="users-table">
          <thead><tr><th>کاربر</th><th>شماره تماس</th><th>تاریخ ثبت‌نام</th><th>تعداد پیام</th><th>عملیات</th><th></th></tr></thead>
          <tbody id="users-tbody"><tr><td colspan="6" class="loading-text" style="text-align:center;padding:20px;"><span class="loading-spinner"></span> در حال بارگذاری...</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- SOPs -->
  <div class="page" id="page-sops">
    <div class="page-header"><div class="page-title">راهنماهای از پیش تعریف شده (SOP)</div><div class="page-subtitle">مدیریت پاسخ‌های خودکار به کاربران</div></div>
    <button class="btn btn-primary" id="btn-add-sop" style="margin-bottom:16px;">➕ تعریف راهنمای جدید</button>
    <div class="sops-list" id="sops-list"></div>
  </div>

  <!-- ANALYTICS -->
  <div class="page" id="page-analytics">
    <div class="page-header"><div class="page-title">گزارش‌های تحلیلی</div><div class="page-subtitle">آمار و تحلیل پیام‌ها و کاربران</div></div>
    <div class="chart-card"><div class="chart-title"><svg viewBox="0 0 16 16" width="14" height="14" style="vertical-align:-2px;margin-left:4px"><rect x="3" y="9" width="3" height="5" rx=".5" fill="var(--accent)" opacity=".4"/><rect x="6.5" y="5" width="3" height="9" rx=".5" fill="var(--accent)" opacity=".7"/><rect x="10" y="2" width="3" height="12" rx=".5" fill="var(--accent)"/></svg>آمار امروز</div><div id="daily-report" class="loading-text"><span class="loading-spinner"></span> در حال بارگذاری...</div></div>
    <div class="chart-card"><div class="chart-title"><svg viewBox="0 0 16 16" width="14" height="14" style="vertical-align:-2px;margin-left:4px"><polyline points="2,12 5,8 8,9 11,5 14,2" stroke="var(--accent)" stroke-width="1.3" fill="none" stroke-linecap="round" stroke-linejoin="round"/><circle cx="14" cy="2" r="1.5" fill="var(--accent)"/></svg>آمار هفتگی</div><div id="weekly-chart" class="loading-text"><span class="loading-spinner"></span> در حال بارگذاری...</div></div>
    <div class="chart-card"><div class="chart-title"><svg viewBox="0 0 16 16" width="14" height="14" style="vertical-align:-2px;margin-left:4px"><circle cx="8" cy="8" r="7" stroke="var(--accent)" stroke-width="1.3" fill="none"/><path d="M5 8h6M8 5v6" stroke="var(--accent)" stroke-width="1.3" stroke-linecap="round"/></svg>کلمات کلیدی پرتکرار</div><div id="keywords-chart" class="loading-text"><span class="loading-spinner"></span> در حال بارگذاری...</div></div>
  </div>

  <!-- BROADCAST -->
  <div class="page" id="page-broadcast">
    <div class="page-header"><div class="page-title">ارسال همگانی</div><div class="page-subtitle">ارسال پیام یا راهنما به تمام کاربران ثبت‌نام کرده</div></div>
    <div class="broadcast-layout">
      <div class="chart-card broadcast-card">
        <div class="chart-title"><span class="broadcast-icon-wrap"><svg viewBox="0 0 14 14" width="14" height="14"><path d="M1 7L13 1L7 13L5 9L1 7z" stroke="var(--accent)" stroke-width="1.4" fill="none" stroke-linejoin="round"/></svg></span> ارسال پیام متنی</div>
        <p class="broadcast-hint">پیام شما برای <strong id="broadcast-user-count-text">همه کاربران</strong> ارسال خواهد شد.</p>
        <div class="form-group">
          <label class="form-label">متن پیام</label>
          <textarea class="form-textarea" id="broadcast-text" placeholder="متن پیام همگانی خود را اینجا بنویسید..." rows="4"></textarea>
        </div>
        <div class="broadcast-footer">
          <span class="broadcast-char-count" id="broadcast-char-count">۰ کاراکتر</span>
          <button class="btn btn-primary" id="btn-send-broadcast"><svg viewBox="0 0 14 14" width="13" height="13" style="vertical-align:-2px;margin-left:3px"><path d="M2 3h10L4 7l8 4H2V3z" stroke="currentColor" stroke-width="1.4" fill="none"/></svg>ارسال همگانی</button>
        </div>
      </div>
      <div class="chart-card broadcast-card">
        <div class="chart-title"><span class="broadcast-icon-wrap gold"><svg viewBox="0 0 14 14" width="14" height="14"><rect x="3" y="1" width="8" height="12" rx="1.5" stroke="var(--gold)" stroke-width="1.3" fill="none"/><line x1="5" y1="4" x2="11" y2="4" stroke="var(--gold)" stroke-width="1" opacity=".6"/><line x1="5" y1="7" x2="11" y2="7" stroke="var(--gold)" stroke-width="1"/><line x1="5" y1="10" x2="9" y2="10" stroke="var(--gold)" stroke-width="1" opacity=".4"/></svg></span> ارسال راهنمای آماده</div>
        <p class="broadcast-hint">یکی از راهنماهای تعریف شده را انتخاب و برای همه کاربران بفرستید.</p>
        <div class="form-group">
          <label class="form-label">انتخاب راهنما (SOP)</label>
          <select class="form-input" id="broadcast-sop-select">
            <option value="">— یک راهنما انتخاب کنید —</option>
          </select>
        </div>
        <div class="broadcast-footer">
          <span class="broadcast-sop-preview" id="broadcast-sop-preview"></span>
          <button class="btn btn-gold" id="btn-send-broadcast-sop"><svg viewBox="0 0 14 14" width="13" height="13" style="vertical-align:-2px;margin-left:3px"><rect x="3" y="1" width="8" height="12" rx="1.5" stroke="currentColor" stroke-width="1.3" fill="none"/><line x1="5" y1="4" x2="11" y2="4" stroke="currentColor" stroke-width="1" opacity=".6"/><line x1="5" y1="7" x2="11" y2="7" stroke="currentColor" stroke-width="1"/></svg>ارسال راهنما</button>
        </div>
      </div>
    </div>
  </div>

  <!-- THEMES -->
  <div class="page" id="page-themes">
    <div class="page-header"><div class="page-title">انتخاب تم رنگی</div><div class="page-subtitle">رنگ اصلی پنل مدیریت را انتخاب کنید</div></div>
    <div class="chart-card">
      <div class="chart-title"><svg viewBox="0 0 18 18" width="16" height="16" style="vertical-align:-2px;margin-left:4px"><circle cx="9" cy="9" r="7" stroke="var(--accent)" stroke-width="1.5" fill="none"/><circle cx="9" cy="9" r="3" fill="var(--accent)" opacity=".3"/><path d="M9 2v2M9 14v2M2 9h2M14 9h2" stroke="var(--accent)" stroke-width="1.3" stroke-linecap="round"/></svg>تم‌های موجود</div>
      <div class="theme-picker-grid">
        <button class="theme-option active" data-accent="blue">
          <span class="theme-swatch" style="background:#5b9aff"></span>
          <span class="theme-name">آبی</span>
          <span class="theme-badge">پیش‌فرض</span>
        </button>
        <button class="theme-option" data-accent="orange">
          <span class="theme-swatch" style="background:#f97316"></span>
          <span class="theme-name">نارنجی</span>
        </button>
        <button class="theme-option" data-accent="red">
          <span class="theme-swatch" style="background:#ef4444"></span>
          <span class="theme-name">قرمز</span>
        </button>
        <button class="theme-option" data-accent="purple">
          <span class="theme-swatch" style="background:#8b5cf6"></span>
          <span class="theme-name">بنفش</span>
        </button>
        <button class="theme-option" data-accent="yellow">
          <span class="theme-swatch" style="background:#eab308"></span>
          <span class="theme-name">زرد</span>
        </button>
        <button class="theme-option" data-accent="green">
          <span class="theme-swatch" style="background:#22c55e"></span>
          <span class="theme-name">سبز</span>
        </button>
      </div>
    </div>
    <div class="chart-card">
      <div class="chart-title"><svg viewBox="0 0 16 16" width="15" height="15" style="vertical-align:-2px;margin-left:4px"><rect x="2" y="2" width="12" height="12" rx="2" stroke="var(--accent)" stroke-width="1.3" fill="none"/><circle cx="8" cy="8" r="2" fill="var(--accent)" opacity=".5"/></svg>پیش‌نمایش زنده</div>
      <div class="theme-preview-area">
        <div class="preview-card"><div class="preview-header">عنوان نمونه</div><div class="preview-body">این یک متن نمونه در تم انتخاب شده است. رنگ دکمه‌ها، حاشیه‌ها و خطوط با تم تغییر می‌کنند.</div><div class="preview-actions"><button class="btn btn-primary btn-sm">دکمه اصلی</button><button class="btn btn-outline btn-sm">دکمه حاشیه</button></div></div>
      </div>
    </div>
  </div>
</main>

<!-- MODALS -->
<div class="modal-overlay" id="sop-modal">
  <div class="modal">
    <div class="modal-title" id="sop-modal-title">تعریف راهنمای جدید</div>
    <div class="form-group"><label class="form-label">نام راهنما</label><input class="form-input" id="sop-name" placeholder="مثلاً: هزینه طراحی سایت"></div>
    <div class="form-group"><label class="form-label">متن پاسخ</label><textarea class="form-textarea" id="sop-response" placeholder="متنی که به کاربر نمایش داده می‌شود..."></textarea></div>
    <div class="form-group"><label class="form-label">کلمات کلیدی (با کاما جدا کنید)</label><input class="form-input" id="sop-keywords" placeholder="هزینه, قیمت, چند, مشاوره"><div style="font-size:10px;color:var(--text-muted);margin-top:4px;">وقتی کاربر این کلمات رو بفرسته، پاسخ به صورت خودکار ارسال میشه</div></div>
    <input type="hidden" id="sop-edit-id" value="">
    <div class="modal-actions">
      <button class="btn btn-outline" id="btn-sop-cancel">انصراف</button>
      <button class="btn btn-primary" id="btn-sop-save"><svg viewBox="0 0 14 14" width="13" height="13" style="vertical-align:-2px;margin-left:3px"><path d="M2 2v10h10V4L9 1H3a1 1 0 00-1 1z" stroke="currentColor" stroke-width="1.3" fill="none"/><line x1="7" y1="1" x2="7" y2="8" stroke="currentColor" stroke-width="1.3"/><line x1="4" y1="5" x2="10" y2="5" stroke="currentColor" stroke-width="1.3" opacity=".5"/></svg>ذخیره</button>
    </div>
  </div>
</div>

<div class="modal-overlay" id="sop-select-modal">
  <div class="modal">
    <div class="modal-title">ارسال SOP</div>
    <div id="sop-select-list" style="display:flex;flex-direction:column;gap:8px;"></div>
    <div class="modal-actions"><button class="btn btn-outline" id="btn-sop-select-close">انصراف</button></div>
  </div>
</div>

<div class="modal-overlay confirm-modal" id="confirm-modal">
  <div class="modal">
    <div class="confirm-icon"><svg viewBox="0 0 48 48" width="48" height="48"><circle cx="24" cy="24" r="22" stroke="var(--danger)" stroke-width="2" fill="none" opacity=".3"/><line x1="24" y1="14" x2="24" y2="28" stroke="var(--danger)" stroke-width="2.5" stroke-linecap="round"/><circle cx="24" cy="34" r="2" fill="var(--danger)"/></svg></div>
    <div class="modal-title" style="justify-content:center;">تأیید حذف</div>
    <div class="confirm-text">آیا از <strong id="confirm-item-name">حذف این آیتم</strong> اطمینان دارید؟</div>
    <div class="confirm-text" style="font-size:12px;color:var(--text-muted);">این عملیات قابل بازگشت نیست.</div>
    <div class="modal-actions">
      <button class="btn btn-outline" id="btn-confirm-cancel">انصراف</button>
      <button class="btn btn-danger" id="btn-confirm-ok"><svg viewBox="0 0 14 14" width="13" height="13" style="vertical-align:-2px;margin-left:3px"><path d="M2 3h10l-1 9H3L2 3z" stroke="currentColor" stroke-width="1.3" fill="none"/><line x1="5" y1="6" x2="5" y2="9" stroke="currentColor" stroke-width="1.2" opacity=".6"/><line x1="9" y1="6" x2="9" y2="9" stroke="currentColor" stroke-width="1.2" opacity=".6"/><line x1="3" y1="3" x2="11" y2="3" stroke="currentColor" stroke-width="1.3" opacity=".5"/><line x1="5" y1="3" x2="4" y2="1" stroke="currentColor" stroke-width="1.2" opacity=".4"/><line x1="9" y1="3" x2="10" y2="1" stroke="currentColor" stroke-width="1.2" opacity=".4"/></svg>حذف</button>
    </div>
  </div>
</div>

<div class="toast-container" id="toast-container"></div>

<script>
// ======================================================================
// ZARO FIX v2.1 — REBUILT DASHBOARD
// تمام هندلرهای inline با event delegation و data attributes جایگزین شدن
// ======================================================================

(function() {
  'use strict';

  // ========== THEME ==========
  document.getElementById('theme-toggle').addEventListener('click', function() {
    var current = document.documentElement.getAttribute('data-theme');
    var next = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('zaro-theme', next);
  });

  // ========== ACCENT THEME PICKER ==========
  var savedAccent = localStorage.getItem('zaro-accent') || 'blue';
  function setAccentTheme(accent) {
    document.documentElement.setAttribute('data-accent', accent);
    localStorage.setItem('zaro-accent', accent);
    document.querySelectorAll('.theme-option, .accent-dot').forEach(function(el) {
      el.classList.toggle('active', el.getAttribute('data-accent') === accent);
    });
  }
  document.querySelectorAll('.theme-option').forEach(function(btn) {
    btn.classList.toggle('active', btn.getAttribute('data-accent') === savedAccent);
    btn.addEventListener('click', function() { setAccentTheme(this.getAttribute('data-accent')); });
  });

  // ========== PARTICLES BACKGROUND ==========
  var canvas = document.getElementById('particles-canvas');
  var ctx = canvas.getContext('2d');
  var particles = [];
  var PARTICLE_COUNT = 12;

  function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resizeCanvas();
  window.addEventListener('resize', function() {
    resizeCanvas();
    particles = [];
    for (var p = 0; p < PARTICLE_COUNT; p++) particles.push({
      x: Math.random() * canvas.width, y: Math.random() * canvas.height,
      r: Math.random() * 1.2 + 0.3, vx: (Math.random()-0.5)*0.1,
      vy: -Math.random()*0.1-0.03, opacity: Math.random()*0.25+0.06
    });
  });

  for (var p = 0; p < PARTICLE_COUNT; p++) {
    particles.push({
      x: Math.random() * canvas.width, y: Math.random() * canvas.height,
      r: Math.random() * 1.2 + 0.3, vx: (Math.random() - 0.5) * 0.1,
      vy: -Math.random() * 0.1 - 0.03, opacity: Math.random() * 0.25 + 0.06
    });
  }

  var frameCount = 0;
  function animateParticles() {
    frameCount++;
    if (frameCount % 3 !== 0) { requestAnimationFrame(animateParticles); return; }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (var i = 0; i < particles.length; i++) {
      var pt = particles[i];
      pt.x += pt.vx; pt.y += pt.vy;
      if (pt.x < -10) pt.x = canvas.width + 10;
      if (pt.x > canvas.width + 10) pt.x = -10;
      if (pt.y < -10) pt.y = canvas.height + 10;
      if (pt.y > canvas.height + 10) pt.y = -10;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, pt.r, 0, Math.PI * 2);
      var accentRgb = getComputedStyle(document.documentElement).getPropertyValue('--accent-rgb').trim() || '91,154,255';
      ctx.fillStyle = 'rgba(' + accentRgb + ',' + pt.opacity + ')';
      ctx.fill();
    }
    requestAnimationFrame(animateParticles);
  }
  animateParticles();

  // ========== CLICK SOUND (Web Audio) ==========
  var audioCtx = null;
  function initAudio() {
    if (audioCtx) return;
    try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e) {}
  }
  function playClick(freq, vol, dur) {
    if (!audioCtx) return;
    freq = freq || 800;
    vol = vol || 0.03;
    dur = dur || 0.06;
    var osc = audioCtx.createOscillator();
    var gain = audioCtx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(freq * 0.3, audioCtx.currentTime + dur);
    gain.gain.setValueAtTime(vol, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + dur);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + dur);
  }
  // init audio on first user interaction
  document.addEventListener('click', function() { initAudio(); }, { once: true });

  // attach click sound to all buttons
  document.addEventListener('click', function(e) {
    var btn = e.target.closest('button, .btn, .nav-item, .user-item');
    if (btn) playClick(600 + Math.random() * 400, 0.025, 0.05);
  });

  // ========== GLOBAL STATE ==========
  var APP = {
    currentPage: 'dashboard',
    selectedUserId: null,
    selectedUserName: '',
    selectedUserPhone: '',
    lastMsgCount: 0,
    sopCache: []
  };

  // ========== DOM REFS ==========
  var $ = function(id) { return document.getElementById(id); };

  // ========== API HELPER ==========
  function api(path, method, body) {
    path = BASE + path;
    method = method || 'GET';
    var opts = { method: method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    return fetch(path, opts).then(function(r) {
      if (!r.ok) {
        return r.json().then(function(e) { throw new Error(e.detail || 'خطای سرور'); });
      }
      return r.json();
    });
  }

  // ========== TOAST ==========
  function toast(msg, type) {
    type = type || 'success';
    var c = $('toast-container');
    var t = document.createElement('div');
    t.className = 'toast ' + type;
    t.innerHTML = (type === 'success' ? '<span style="color:var(--success);font-weight:700">✓</span> ' : '<span style="color:var(--danger);font-weight:700">✗</span> ') + msg;
    c.appendChild(t);
    setTimeout(function() {
      t.style.opacity = '0';
      t.style.transition = 'opacity 0.3s';
      setTimeout(function() { t.remove(); }, 300);
    }, 3000);
  }

  // ========== HTML ESCAPE ==========
  function escHtml(text) {
    var d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML.replace(/\n/g, '<br>');
  }

  function escAttr(text) {
    return text.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/'/g, '&#39;');
  }

  // ========== NAVIGATION ==========
  function navigateTo(page) {
    APP.currentPage = page;
    // set page class on main for header coloring
    var main = $('main-content');
    var pageClasses = ['nav-dashboard','nav-messages','nav-users','nav-sops','nav-analytics','nav-broadcast'];
    for (var pc = 0; pc < pageClasses.length; pc++) main.classList.remove(pageClasses[pc]);
    main.classList.add('nav-' + page);
    // update nav buttons
    var navItems = document.querySelectorAll('#nav-list .nav-item');
    for (var i = 0; i < navItems.length; i++) {
      navItems[i].classList.remove('active');
    }
    var activeNav = document.querySelector('#nav-list .nav-item[data-page="' + page + '"]');
    if (activeNav) activeNav.classList.add('active');
    // show page with animation
    var pages = document.querySelectorAll('.page');
    for (var j = 0; j < pages.length; j++) {
      pages[j].classList.remove('active');
    }
    var targetPage = $('page-' + page);
    if (targetPage) targetPage.classList.add('active');
    // load data
    if (page === 'dashboard') loadDashboard();
    else if (page === 'messages') loadMessageUsers();
    else if (page === 'users') loadUsers();
    else if (page === 'sops') loadSops();
    else if (page === 'analytics') loadAnalytics();
    else if (page === 'broadcast') loadBroadcastOptions();
  }

  // NAV CLICK HANDLER — delegation on nav-list
  $('nav-list').addEventListener('click', function(e) {
    var btn = e.target.closest('.nav-item');
    if (!btn) return;
    var page = btn.getAttribute('data-page');
    if (page) navigateTo(page);
  });

  // ========== COUNT-UP ANIMATION ==========
  function animateCount(el, target, duration) {
    duration = duration || 800;
    var start = 0;
    var startTime = null;
    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var progress = Math.min((timestamp - startTime) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      var current = Math.round(eased * target);
      el.textContent = current;
      if (progress < 1) { requestAnimationFrame(step); }
    }
    requestAnimationFrame(step);
  }

  // ========== DASHBOARD ==========
  function loadDashboard() {
    api('/api/stats').then(function(s) {
      animateCount($('stat-users'), s.users_count);
      animateCount($('stat-msgs'), s.messages_count);
      animateCount($('stat-sops'), s.sops_count);
      animateCount($('stat-today'), s.daily.total_messages);
      // banner stats
      animateCount($('ban-users'), s.users_count);
      animateCount($('ban-msgs'), s.messages_count);
      animateCount($('ban-online'), s.sops_count);
      // daily chart
      var html = '';
      if (s.daily.user_counts && Object.keys(s.daily.user_counts).length) {
        var counts = [];
        for (var k in s.daily.user_counts) { counts.push([k, s.daily.user_counts[k]]); }
        counts.sort(function(a, b) { return b[1] - a[1]; });
        var max = counts[0][1];
        for (var i = 0; i < Math.min(counts.length, 10); i++) {
          var pct = Math.max(Math.round(counts[i][1] / max * 100), 4);
          html += '<div class="bar-row" style="animation:slideInRight 0.4s ease backwards;animation-delay:' + (i*0.06) + 's"><div class="bar-label">' + escHtml(counts[i][0]) + '</div><div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div><div class="bar-count">' + counts[i][1] + ' پیام</div></div>';
        }
      } else { html = '<span style="color:var(--text-muted)">امروز پیامی ثبت نشده</span>'; }
      $('daily-chart').innerHTML = html;
      APP.lastMsgCount = s.messages_count;
    }).catch(function(e) {
      $('daily-chart').innerHTML = '<span style="color:var(--danger)">خطا در بارگذاری</span>';
      console.error(e);
    });
  }

  // ========== MESSAGES ==========
  function loadMessageUsers() {
    api('/api/users').then(function(u) {
      var list = $('msg-user-list');
      if (!u.users.length) {
        list.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><svg viewBox="0 0 36 36" width="36" height="36"><circle cx="12" cy="10" r="6" stroke="currentColor" stroke-width="2" fill="none" opacity=".3"/><path d="M0 30c0-6.6 5.4-12 12-12s12 5.4 12 12" stroke="currentColor" stroke-width="2" fill="none" opacity=".3"/><circle cx="24" cy="22" r="4" stroke="currentColor" stroke-width="1.5" fill="none" opacity=".15"/></svg></div><div>هنوز کاربری ثبت نام نکرده</div></div>';
        return;
      }
      list.innerHTML = '';
      for (var i = 0; i < u.users.length; i++) {
        (function(user) {
          var div = document.createElement('button');
          div.className = 'user-item';
          if (APP.selectedUserId === user.user_id) div.classList.add('selected');
          div.setAttribute('data-uid', user.user_id);
          div.setAttribute('data-name', user.first_name);
          div.setAttribute('data-phone', user.phone);
          div.innerHTML =
            '<div class="user-avatar">' + escHtml(user.first_name[0]) + '</div>' +
            '<div class="user-info"><div class="user-name">' + escHtml(user.first_name) + '</div><div class="user-last-msg">' + escHtml(user.last_message || 'بدون پیام') + '</div></div>' +
            '<div class="user-time">' + user.total_messages + ' پیام</div>';
          div.addEventListener('click', function() {
            selectUser(this.getAttribute('data-uid'), this.getAttribute('data-name'), this.getAttribute('data-phone'));
          });
          list.appendChild(div);
        })(u.users[i]);
      }
    }).catch(function(e) {
      $('msg-user-list').innerHTML = '<div class="empty-state"><div class="empty-state-icon" style="color:var(--danger)"><svg viewBox="0 0 36 36" width="36" height="36"><circle cx="18" cy="18" r="14" stroke="currentColor" stroke-width="2" fill="none" opacity=".3"/><line x1="18" y1="10" x2="18" y2="22" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity=".5"/><circle cx="18" cy="27" r="1.5" fill="currentColor" opacity=".5"/></svg></div><div>خطا در بارگذاری کاربران</div></div>';
    });
  }

  function selectUser(uid, name, phone) {
    APP.selectedUserId = uid;
    APP.selectedUserName = name;
    APP.selectedUserPhone = phone;
    $('chat-header-placeholder').style.display = 'flex';
    $('chat-avatar-icon').textContent = name[0] || '👤';
    $('chat-user-name').textContent = name;
    $('chat-user-meta').textContent = 'تلفن: ' + phone + ' | آیدی: ' + uid;
    $('chat-input-area').style.display = 'flex';
    // update selection visual
    var items = document.querySelectorAll('#msg-user-list .user-item');
    for (var i = 0; i < items.length; i++) {
      items[i].classList.remove('selected');
    }
    var selected = document.querySelector('#msg-user-list .user-item[data-uid="' + uid + '"]');
    if (selected) selected.classList.add('selected');
    loadConversation(uid);
  }

  function formatVoiceDuration(sec) { var m = Math.floor(sec/60), s = sec%60; return m+':'+(s<10?'0':'')+s; }

  function renderVoiceMsg(fileId, direction, duration) {
    duration = duration || 0;
    var dir = direction === 'outgoing' ? 'msg-outgoing' : 'msg-incoming';
    return '<div class="msg-bubble ' + dir + '">' +
      '<div class="voice-msg">' +
        '<button class="play-btn" data-file-id="' + fileId + '" onclick="toggleVoice(this)">▶</button>' +
        '<div class="waveform">' +
          '<span></span><span></span><span></span><span></span><span></span>' +
        '</div>' +
        '<span class="voice-duration">' + formatVoiceDuration(duration) + '</span>' +
      '</div>' +
      '<div class="msg-time">' + duration + ' ثانیه</div>' +
    '</div>';
  }

  window._audioPlayers = {};

  window.toggleVoice = function(btn) {
    var fileId = btn.getAttribute('data-file-id');
    if (window._audioPlayers[fileId] && window._audioPlayers[fileId]._playing) {
      window._audioPlayers[fileId].pause();
      window._audioPlayers[fileId]._playing = false;
      btn.textContent = '▶';
      btn.classList.remove('playing');
      return;
    }
    for (var k in window._audioPlayers) {
      if (window._audioPlayers[k] && window._audioPlayers[k]._playing) {
        window._audioPlayers[k].pause();
        window._audioPlayers[k]._playing = false;
        var ob2 = document.querySelector('.play-btn[data-file-id="' + k + '"]');
        if (ob2) { ob2.textContent = '▶'; ob2.classList.remove('playing'); }
      }
    }
    btn.textContent = '⏳';
    btn.classList.add('playing');
    var audio = new Audio();
    audio.addEventListener('canplaythrough', function() {
      audio.play().catch(function() {
        btn.textContent = '▶'; btn.classList.remove('playing');
        window._audioPlayers[fileId] = null;
      });
    });
    audio.addEventListener('error', function() {
      btn.textContent = '▶'; btn.classList.remove('playing');
      window._audioPlayers[fileId] = null;
      toast('خطا در پخش فایل صوتی', 'error');
    });
    audio.addEventListener('ended', function() {
      audio._playing = false;
      btn.textContent = '▶'; btn.classList.remove('playing');
    });
    audio.src = BASE + '/api/voice-proxy/' + fileId;
    window._audioPlayers[fileId] = audio;
    audio._playing = true;
    btn.textContent = '⏸';
    audio.load();
  }

  function loadConversation(uid) {
    api('/api/conversation/' + uid).then(function(c) {
      var el = $('chat-messages');
      if (!c.messages || !c.messages.length) {
        el.innerHTML = '<div class="chat-empty"><div class="chat-empty-icon"><svg viewBox="0 0 36 36" width="36" height="36"><circle cx="18" cy="18" r="14" stroke="currentColor" stroke-width="1.5" fill="none" opacity=".2"/><line x1="10" y1="18" x2="26" y2="18" stroke="currentColor" stroke-width="2" opacity=".25"/><line x1="18" y1="15" x2="18" y2="21" stroke="currentColor" stroke-width="2" opacity=".15"/></svg></div><div>هنوز پیامی رد و بدل نشده</div></div>';
        return;
      }
      var html = '';
      for (var i = 0; i < c.messages.length; i++) {
        var m = c.messages[i];
        var timeStr = (m.timestamp || '').slice(11, 16);
        if (m.type === 'contact') {
          html += '<div class="msg-bubble msg-system"><span style="color:var(--accent);font-weight:600">●</span> اشتراک شماره تماس — ' + timeStr + '</div>';
        } else if (m.type === 'admin_reply') {
          var vMatch = m.text.match(/\[voice:([^\]]+)\]/);
          if (vMatch) {
            html += renderVoiceMsg(vMatch[1], 'outgoing');
          } else if (m.text.indexOf('[photo:') !== -1) {
            var pMatch2 = m.text.match(/\[photo:([^\]]+)\]/);
            if (pMatch2) {
              var cap2 = m.text.replace(/\[photo:[^\]]+\]\s*/, '');
              html += '<div class="msg-bubble msg-outgoing"><a href="' + BASE + '/api/voice-proxy/' + pMatch2[1] + '" target="_blank"><img class="msg-image" src="' + BASE + '/api/voice-proxy/' + pMatch2[1] + '" alt="photo" loading="lazy"></a>' + (cap2 ? '<div style="margin-top:6px;font-size:12px;">' + escHtml(cap2) + '</div>' : '') + '<div class="msg-time">' + timeStr + '</div></div>';
            } else { html += '<div class="msg-bubble msg-outgoing">🖼 عکس<div class="msg-time">' + timeStr + '</div></div>'; }
          } else if (m.text.indexOf('[document:') !== -1) {
            var dMatch2 = m.text.match(/\[document:([^\]]+)\]/);
            if (dMatch2) {
              html += '<div class="msg-bubble msg-outgoing"><a class="msg-file" href="' + BASE + '/api/voice-proxy/' + dMatch2[1] + '" target="_blank"><svg viewBox="0 0 24 24" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="currentColor" stroke-width="1.6" fill="none"/><path d="M14 2v6h6" stroke="currentColor" stroke-width="1.6" fill="none"/></svg><span class="file-name">فایل</span> 📥</a><div class="msg-time">' + timeStr + '</div></div>';
            } else { html += '<div class="msg-bubble msg-outgoing">📎 فایل<div class="msg-time">' + timeStr + '</div></div>'; }
          } else {
            html += '<div class="msg-bubble msg-outgoing">' + escHtml(m.text) + '<div class="msg-time">' + timeStr + '</div></div>';
          }
        } else {
          // check for voice markers in incoming messages
          var vMatch = m.text.match(/\[voice:([^\]]+)\]/);
          if (vMatch) {
            var durMatch = m.text.match(/\(duration: (\d+)/);
            var dur = durMatch ? parseInt(durMatch[1]) : 0;
            html += renderVoiceMsg(vMatch[1], 'incoming', dur);
          } else if (m.text.indexOf('[voice:') !== -1) {
            var fid2 = m.text.match(/\[voice:([^\]]+)\]/);
            if (fid2) html += renderVoiceMsg(fid2[1], 'incoming', 0);
            else html += '<div class="msg-bubble msg-incoming">🎤 پیام صوتی<div class="msg-time">' + timeStr + '</div></div>';
          } else if (m.text.indexOf('[photo:') !== -1) {
            var pMatch = m.text.match(/\[photo:([^\]]+)\]/);
            if (pMatch) {
              var cap = m.text.replace(/\[photo:[^\]]+\]\s*/, '');
              html += '<div class="msg-bubble msg-incoming"><a href="' + BASE + '/api/voice-proxy/' + pMatch[1] + '" target="_blank"><img class="msg-image" src="' + BASE + '/api/voice-proxy/' + pMatch[1] + '" alt="photo" loading="lazy"></a>' + (cap ? '<div style="margin-top:6px;font-size:12px;">' + escHtml(cap) + '</div>' : '') + '<div class="msg-time">' + timeStr + '</div></div>';
            } else { html += '<div class="msg-bubble msg-incoming">🖼 عکس<div class="msg-time">' + timeStr + '</div></div>'; }
          } else if (m.text.indexOf('[document:') !== -1) {
            var dMatch = m.text.match(/\[document:([^\]]+)\]/);
            if (dMatch) {
              var fname = m.text.replace(/\[document:[^\]]+\]\s*/, '') || 'فایل';
              html += '<div class="msg-bubble msg-incoming"><a class="msg-file" href="' + BASE + '/api/voice-proxy/' + dMatch[1] + '" target="_blank"><svg viewBox="0 0 24 24" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="currentColor" stroke-width="1.6" fill="none"/><path d="M14 2v6h6" stroke="currentColor" stroke-width="1.6" fill="none"/></svg><span class="file-name">' + escHtml(fname.slice(0,40)) + '</span> 📥</a><div class="msg-time">' + timeStr + '</div></div>';
            } else { html += '<div class="msg-bubble msg-incoming">📎 فایل<div class="msg-time">' + timeStr + '</div></div>'; }
          } else {
            html += '<div class="msg-bubble msg-incoming">' + escHtml(m.text) + '<div class="msg-time">' + timeStr + '</div></div>';
          }
        }
      }
      el.innerHTML = html;
      el.scrollTop = el.scrollHeight;
    }).catch(function(e) {
      console.error(e);
    });
  }

  function sendReply() {
    var text = $('chat-input').value.trim();
    if (!text || !APP.selectedUserId) return;
    $('btn-send-reply').disabled = true;
    api('/api/reply', 'POST', { user_id: APP.selectedUserId, text: text }).then(function() {
      $('chat-input').value = '';
      toast('پاسخ ارسال شد');
      return Promise.all([loadConversation(APP.selectedUserId), loadMessageUsers()]);
    }).catch(function() {}).finally(function() {
      $('btn-send-reply').disabled = false;
    });
  }

  $('btn-send-reply').addEventListener('click', sendReply);

  $('chat-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendReply(); }
  });

  // ========== VOICE RECORDING ==========
  var mediaRecorder = null;
  var audioChunks = [];
  var isRecording = false;
  var recordBtn = $('btn-record-voice');

  recordBtn.addEventListener('click', function() {
    if (!APP.selectedUserId) { toast('ابتدا کاربر را انتخاب کنید', 'error'); return; }
    if (isRecording) {
      // stop recording
      if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
      }
      isRecording = false;
      recordBtn.textContent = '🎤';
      recordBtn.classList.remove('recording');
      recordBtn.style.background = '';
      return;
    }
    // start recording
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      toast('مرورگر شما از ضبط صدا پشتیبانی نمی‌کند', 'error');
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
      audioChunks = [];
      var mimeType = 'audio/webm;codecs=opus';
      if (!MediaRecorder.isTypeSupported(mimeType)) mimeType = 'audio/webm';
      if (!MediaRecorder.isTypeSupported(mimeType)) mimeType = 'audio/ogg;codecs=opus';
      if (!MediaRecorder.isTypeSupported(mimeType)) mimeType = '';
      mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType: mimeType } : {});
      mediaRecorder.ondataavailable = function(e) {
        if (e.data.size > 0) audioChunks.push(e.data);
      };
      mediaRecorder.onstop = function() {
        var blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
        stream.getTracks().forEach(function(t) { t.stop(); });
        // Upload voice
        var formData = new FormData();
        formData.append('user_id', APP.selectedUserId);
        formData.append('voice', blob, 'voice_' + Date.now() + '.webm');
        recordBtn.textContent = '⏳';
        recordBtn.disabled = true;
        fetch(BASE + '/api/upload-voice', { method: 'POST', body: formData }).then(function(r) {
          if (!r.ok) throw new Error('خطا');
          return r.json();
        }).then(function() {
          toast('🎤 پیام صوتی ارسال شد');
          loadConversation(APP.selectedUserId);
          loadMessageUsers();
        }).catch(function() {
          toast('خطا در ارسال پیام صوتی', 'error');
        }).finally(function() {
          recordBtn.textContent = '🎤';
          recordBtn.disabled = false;
        });
      };
      mediaRecorder.start();
      isRecording = true;
      recordBtn.textContent = '⏹';
      recordBtn.classList.add('recording');
      toast('🎤 در حال ضبط... برای توقف کلیک کنید', 'success');
    }).catch(function(err) {
      toast('دسترسی به میکروفون رد شد', 'error');
      console.error(err);
    });
  });

  // ========== FILE UPLOAD ==========
  var fileInput = $('file-input');
  $('btn-attach-file').addEventListener('click', function() {
    if (!APP.selectedUserId) { toast('ابتدا کاربر را انتخاب کنید', 'error'); return; }
    fileInput.click();
  });

  fileInput.addEventListener('change', function() {
    var files = this.files;
    if (!files || !files.length) return;
    for (var fi = 0; fi < files.length; fi++) {
      (function(file) {
        var formData = new FormData();
        formData.append('user_id', APP.selectedUserId);
        formData.append('file', file, file.name);
        var btn = $('btn-attach-file');
        btn.textContent = '⏳';
        btn.disabled = true;
        fetch(BASE + '/api/upload-file', { method: 'POST', body: formData }).then(function(r) {
          if (!r.ok) throw new Error('err');
          return r.json();
        }).then(function() {
          toast('📎 فایل ارسال شد');
          loadConversation(APP.selectedUserId);
          loadMessageUsers();
        }).catch(function() {
          toast('خطا در ارسال فایل', 'error');
        }).finally(function() {
          btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
          btn.disabled = false;
        });
      })(files[fi]);
    }
    fileInput.value = '';
  });

  // ========== USERS ==========
  function loadUsers() {
    api('/api/users').then(function(u) {
      var tbody = $('users-tbody');
      if (!u.users.length) {
        tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state"><div class="empty-state-icon"><svg viewBox="0 0 36 36" width="36" height="36"><circle cx="12" cy="10" r="6" stroke="currentColor" stroke-width="2" fill="none" opacity=".3"/><path d="M0 30c0-6.6 5.4-12 12-12s12 5.4 12 12" stroke="currentColor" stroke-width="2" fill="none" opacity=".3"/><circle cx="24" cy="22" r="4" stroke="currentColor" stroke-width="1.5" fill="none" opacity=".15"/></svg></div><div>هنوز کاربری ثبت نام نکرده</div></div></td></tr>';
        return;
      }
      tbody.innerHTML = '';
      for (var i = 0; i < u.users.length; i++) {
        (function(user) {
          var tr = document.createElement('tr');
          tr.innerHTML =
            '<td><strong>' + escHtml(user.first_name) + '</strong> <span style="color:var(--text-muted);font-size:11px;">(' + escHtml(user.user_id) + ')</span></td>' +
            '<td dir="ltr">' + escHtml(user.phone) + '</td>' +
            '<td>' + escHtml(user.registered_at) + '</td>' +
            '<td>' + user.total_messages + '</td>' +
            '<td><button class="btn btn-outline btn-sm chat-btn" data-uid="' + escAttr(user.user_id) + '" data-name="' + escAttr(user.first_name) + '" data-phone="' + escAttr(user.phone) + '">چت</button></td>' +
            '<td><button class="btn btn-danger btn-sm del-user-btn" data-uid="' + escAttr(user.user_id) + '" data-name="' + escAttr(user.first_name) + '">🗑️</button></td>';
          tbody.appendChild(tr);
        })(u.users[i]);
      }
    }).catch(function(e) {
      $('users-tbody').innerHTML = '<tr><td colspan="6"><div class="empty-state"><div class="empty-state-icon" style="color:var(--danger)"><svg viewBox="0 0 36 36" width="36" height="36"><circle cx="18" cy="18" r="14" stroke="currentColor" stroke-width="2" fill="none" opacity=".3"/><line x1="18" y1="10" x2="18" y2="22" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity=".5"/><circle cx="18" cy="27" r="1.5" fill="currentColor" opacity=".5"/></svg></div><div>خطا در بارگذاری</div></div></td></tr>';
    });
  }

  // USERS TABLE CHAT BUTTON DELEGATION
  $('users-tbody').addEventListener('click', function(e) {
    var btn = e.target.closest('.chat-btn');
    if (btn) {
      var uid = btn.getAttribute('data-uid');
      var name = btn.getAttribute('data-name');
      var phone = btn.getAttribute('data-phone');
      navigateTo('messages');
      setTimeout(function() { selectUser(uid, name, phone); }, 300);
      return;
    }
    var delBtn = e.target.closest('.del-user-btn');
    if (delBtn) {
      var uid = delBtn.getAttribute('data-uid');
      var name = delBtn.getAttribute('data-name');
      showConfirm('حذف کاربر ' + name, 'آیا از حذف این کاربر اطمینان دارید؟', function() {
        api('/api/users/' + uid, 'DELETE').then(function() {
          toast('کاربر ' + name + ' حذف شد');
          loadUsers();
        });
      });
    }
  });

  // ========== SOPs ==========
  // ========== CONFIRM MODAL ==========
  var confirmCallback = null;

  function showConfirm(title, itemName, onConfirm) {
    $('confirm-item-name').textContent = itemName;
    confirmCallback = onConfirm;
    $('confirm-modal').classList.add('show');
  }

  function hideConfirm() {
    $('confirm-modal').classList.remove('show');
    confirmCallback = null;
  }

  $('btn-confirm-cancel').addEventListener('click', hideConfirm);
  $('confirm-modal').addEventListener('click', function(e) {
    if (e.target === $('confirm-modal')) hideConfirm();
  });

  $('btn-confirm-ok').addEventListener('click', function() {
    if (confirmCallback) {
      $('btn-confirm-ok').disabled = true;
      confirmCallback().finally(function() {
        $('btn-confirm-ok').disabled = false;
        hideConfirm();
      });
    }
  });
  function loadSops() {
    api('/api/sops').then(function(s) {
      APP.sopCache = s.sops;
      if (!s.sops.length) {
        $('sops-list').innerHTML = '<div class="empty-state"><div class="empty-state-icon"><svg viewBox="0 0 36 36" width="36" height="36"><rect x="7" y="4" width="20" height="28" rx="2.5" stroke="currentColor" stroke-width="2" fill="none" opacity=".25"/><line x1="11" y1="10" x2="25" y2="10" stroke="currentColor" stroke-width="1.5" opacity=".18"/><line x1="11" y1="16" x2="25" y2="16" stroke="currentColor" stroke-width="1.5" opacity=".25"/><line x1="11" y1="22" x2="18" y2="22" stroke="currentColor" stroke-width="1.5" opacity=".15"/></svg></div><div>هنوز راهنمایی تعریف نشده است</div></div>';
        return;
      }
      var html = '';
      for (var i = 0; i < s.sops.length; i++) {
        var sop = s.sops[i];
        var kw = sop.keywords && sop.keywords.length ? sop.keywords.join('، ') : '';
        var kwHtml = kw ? '<div class="sop-keywords"><span class="kw-badge">کلمات کلیدی:</span> ' + escHtml(kw) + '</div>' : '<div class="sop-keywords" style="color:var(--text-muted);opacity:.5;">بدون کلمه کلیدی</div>';
        html +=
          '<div class="sop-card">' +
            '<div class="sop-header">' +
              '<div class="sop-title">#' + sop.id + ' — ' + escHtml(sop.name) + '</div>' +
            '<div class="sop-meta">تاریخ: ' + escHtml(sop.created_at) + ' | استفاده: ' + sop.use_count + ' بار</div>' +
            '</div>' +
            '<div class="sop-response">' + escHtml(sop.response) + '</div>' +
            kwHtml +
            '<div class="sop-actions">' +
              '<button class="btn btn-outline btn-sm sop-edit-btn" data-id="' + sop.id + '" data-name="' + escAttr(sop.name) + '" data-response="' + escAttr(sop.response) + '" data-keywords="' + escAttr(kw) + '">✏️ ویرایش</button>' +
              '<button class="btn btn-danger btn-sm sop-del-btn" data-id="' + sop.id + '" data-name="' + escAttr(sop.name) + '">🗑️ حذف</button>' +
            '</div>' +
          '</div>';
      }
      $('sops-list').innerHTML = html;
    }).catch(function(e) {
      $('sops-list').innerHTML = '<div class="empty-state"><div class="empty-state-icon" style="color:var(--danger)"><svg viewBox="0 0 36 36" width="36" height="36"><circle cx="18" cy="18" r="14" stroke="currentColor" stroke-width="2" fill="none" opacity=".3"/><line x1="18" y1="10" x2="18" y2="22" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity=".5"/><circle cx="18" cy="27" r="1.5" fill="currentColor" opacity=".5"/></svg></div><div>خطا در بارگذاری</div></div>';
    });
  }

  // SOP EDIT / DELETE DELEGATION
  $('sops-list').addEventListener('click', function(e) {
    var editBtn = e.target.closest('.sop-edit-btn');
    if (editBtn) {
      showSopModalEdit(
        parseInt(editBtn.getAttribute('data-id')),
        editBtn.getAttribute('data-name'),
        editBtn.getAttribute('data-response'),
        editBtn.getAttribute('data-keywords')
      );
      return;
    }
    var delBtn = e.target.closest('.sop-del-btn');
    if (delBtn) {
      var delId = parseInt(delBtn.getAttribute('data-id'));
      var sopName = delBtn.getAttribute('data-name') || 'این راهنما';
      showConfirm('حذف راهنما', sopName, function() {
        return api('/api/sops/' + delId, 'DELETE').then(function() {
          toast('راهنما حذف شد');
          loadSops();
          loadBroadcastOptions();
        });
      });
    }
  });

  $('btn-add-sop').addEventListener('click', showSopModalAdd);

  function showSopModalAdd() {
    $('sop-modal-title').textContent = 'تعریف راهنمای جدید';
    $('sop-name').value = '';
    $('sop-response').value = '';
    $('sop-keywords').value = '';
    $('sop-edit-id').value = '';
    $('sop-modal').classList.add('show');
    $('sop-name').focus();
  }

  function showSopModalEdit(id, name, response, keywords) {
    $('sop-modal-title').textContent = 'ویرایش راهنما';
    $('sop-name').value = name;
    $('sop-response').value = response;
    $('sop-keywords').value = keywords || '';
    $('sop-edit-id').value = id;
    $('sop-modal').classList.add('show');
  }

  $('btn-sop-cancel').addEventListener('click', function() { $('sop-modal').classList.remove('show'); });
  $('sop-modal').addEventListener('click', function(e) { if (e.target === $('sop-modal')) $('sop-modal').classList.remove('show'); });

  $('btn-sop-save').addEventListener('click', function() {
    var name = $('sop-name').value.trim();
    var response = $('sop-response').value.trim();
    var keywords = $('sop-keywords').value.trim();
    var editId = $('sop-edit-id').value;
    if (!name || !response) { toast('نام و پاسخ الزامی است', 'error'); return; }
    $('btn-sop-save').disabled = true;
    var promise;
    if (editId) {
      promise = api('/api/sops/' + editId, 'PUT', { name: name, response: response, keywords: keywords }).then(function() { toast('راهنما ویرایش شد'); });
    } else {
      promise = api('/api/sops', 'POST', { name: name, response: response, keywords: keywords }).then(function() { toast('راهنما جدید ایجاد شد'); });
    }
    promise.then(function() {
      $('sop-modal').classList.remove('show');
      loadSops();
      loadBroadcastOptions();
    }).catch(function() {}).finally(function() {
      $('btn-sop-save').disabled = false;
    });
  });

  // ========== SOP SELECT FOR REPLY ==========
  $('btn-send-sop').addEventListener('click', function() {
    if (!APP.selectedUserId) { toast('ابتدا کاربر را انتخاب کنید', 'error'); return; }
    api('/api/sops').then(function(s) {
      var html = '';
      if (!s.sops.length) {
        html = '<span style="color:var(--text-muted);padding:12px;">هیچ راهنمایی تعریف نشده</span>';
      } else {
        for (var i = 0; i < s.sops.length; i++) {
          html += '<button class="btn btn-outline sop-select-item" data-sid="' + s.sops[i].id + '" style="text-align:right;justify-content:flex-start;"><svg viewBox="0 0 14 14" width="13" height="13" style="margin-left:4px"><rect x="3" y="2" width="8" height="10" rx="1.2" stroke="currentColor" stroke-width="1.2" fill="none"/><line x1="5" y1="5" x2="11" y2="5" stroke="currentColor" stroke-width=".9" opacity=".5"/><line x1="5" y1="8" x2="10" y2="8" stroke="currentColor" stroke-width=".9"/></svg>#' + s.sops[i].id + ' — ' + escHtml(s.sops[i].name) + '</button>';
        }
      }
      $('sop-select-list').innerHTML = html;
      $('sop-select-modal').classList.add('show');
    }).catch(function() {});
  });

  $('btn-sop-select-close').addEventListener('click', function() { $('sop-select-modal').classList.remove('show'); });
  $('sop-select-modal').addEventListener('click', function(e) { if (e.target === $('sop-select-modal')) $('sop-select-modal').classList.remove('show'); });

  $('sop-select-list').addEventListener('click', function(e) {
    var btn = e.target.closest('.sop-select-item');
    if (!btn) return;
    var sid = parseInt(btn.getAttribute('data-sid'));
    $('sop-select-modal').classList.remove('show');
    api('/api/broadcast-sop', 'POST', { sop_id: sid, targets: [APP.selectedUserId] }).then(function() {
      toast('SOP ارسال شد');
      return loadConversation(APP.selectedUserId);
    }).catch(function() {});
  });

  // ========== ANALYTICS ==========
  function loadAnalytics() {
    api('/api/stats').then(function(s) {
      // daily
      var dh = '';
      if (s.daily.top_keywords && s.daily.top_keywords.length) {
        dh = '<p style="margin-bottom:8px;color:#ffffff;font-weight:600;font-size:14px;">پیام: ' + s.daily.total_messages + '  ·  کاربر: ' + s.daily.unique_users + '  ·  اشتراک: ' + s.daily.contacts_shared + '</p>';
      } else {
        dh = '<span style="color:var(--text-muted)">امروز پیامی ثبت نشده</span>';
      }
      $('daily-report').innerHTML = dh;

      // weekly
      var wh = '';
      if (s.weekly.total_messages) {
        wh = '<p style="margin-bottom:14px;color:#ffffff;font-weight:600;font-size:14px;">پیام: ' + s.weekly.total_messages + '  ·  کاربر: ' + s.weekly.unique_users + '</p>';
        var days = s.weekly.daily_breakdown;
        if (days && Object.keys(days).length) {
          var dayList = [];
          for (var dk in days) { dayList.push([dk, days[dk].count]); }
          dayList.sort(function(a, b) { return b[1] - a[1]; });
          var max = dayList[0][1] || 1;
          for (var i = 0; i < dayList.length; i++) {
            wh += '<div class="bar-row" style="animation:slideInRight 0.4s ease backwards;animation-delay:' + (i*0.06) + 's"><div class="bar-label">' + escHtml(dayList[i][0].slice(5)) + '</div><div class="bar-track"><div class="bar-fill bar-gold" style="width:' + Math.round(dayList[i][1] / max * 100) + '%"></div></div><div class="bar-count">' + dayList[i][1] + ' پیام</div></div>';
          }
        }
      } else {
        wh = '<span style="color:var(--text-muted)">این هفته پیامی ثبت نشده</span>';
      }
      $('weekly-chart').innerHTML = wh;

      // keywords
      var kh = '';
      if (s.weekly.top_keywords && s.weekly.top_keywords.length) {
        var kmax = s.weekly.top_keywords[0].count || 1;
        for (var j = 0; j < Math.min(s.weekly.top_keywords.length, 15); j++) {
          var k = s.weekly.top_keywords[j];
          kh += '<div class="bar-row" style="animation:slideInRight 0.4s ease backwards;animation-delay:' + (j*0.04) + 's"><div class="bar-label">' + escHtml(k.word) + '</div><div class="bar-track"><div class="bar-fill" style="width:' + Math.round(k.count / kmax * 100) + '%"></div></div><div class="bar-count">' + k.count + '</div></div>';
        }
      } else {
        kh = '<span style="color:var(--text-muted)">داده‌ای برای نمایش وجود ندارد</span>';
      }
      $('keywords-chart').innerHTML = kh;
    }).catch(function(e) {
      $('daily-report').innerHTML = '<span style="color:var(--danger)">خطا در بارگذاری</span>';
      $('weekly-chart').innerHTML = '';
      $('keywords-chart').innerHTML = '';
    });
  }

  // ========== BROADCAST ==========
  function loadBroadcastOptions() {
    api('/api/sops').then(function(s) {
      APP.sopCache = s.sops;
      var html = '<option value="">— یک راهنما انتخاب کنید —</option>';
      for (var i = 0; i < s.sops.length; i++) {
        html += '<option value="' + s.sops[i].id + '">' + escHtml(s.sops[i].name) + '</option>';
      }
      $('broadcast-sop-select').innerHTML = html;
    }).catch(function() {});
    api('/api/users').then(function(u) {
      $('broadcast-user-count-text').textContent = (u.total || 0) + ' کاربر ثبت‌نام کرده';
    }).catch(function() {});
  }

  var _bt = $('broadcast-text');
  if (_bt) _bt.addEventListener('input', function() {
    var el = $('broadcast-char-count');
    if (el) el.textContent = this.value.length + ' کاراکتر';
  });

  var _bs = $('broadcast-sop-select');
  if (_bs) _bs.addEventListener('change', function() {
    var sid = parseInt(this.value), pv = $('broadcast-sop-preview');
    if (!sid || !pv) { if (pv) pv.textContent = ''; return; }
    for (var i = 0; i < APP.sopCache.length; i++) {
      if (APP.sopCache[i].id === sid) { pv.textContent = 'استفاده: ' + APP.sopCache[i].use_count + ' بار'; return; }
    }
    pv.textContent = '';
  });

  $('btn-send-broadcast').addEventListener('click', function() {
    var text = $('broadcast-text').value.trim();
    if (!text) { toast('متن پیام را وارد کنید', 'error'); return; }
    $('btn-send-broadcast').disabled = true;
    api('/api/broadcast', 'POST', { text: text }).then(function(r) {
      toast('پیام به ' + r.sent + ' کاربر ارسال شد');
      $('broadcast-text').value = '';
      var el = $('broadcast-char-count'); if (el) el.textContent = '۰ کاراکتر';
    }).catch(function() {}).finally(function() { $('btn-send-broadcast').disabled = false; });
  });

  $('btn-send-broadcast-sop').addEventListener('click', function() {
    var sopId = parseInt($('broadcast-sop-select').value);
    if (!sopId) { toast('یک راهنما انتخاب کنید', 'error'); return; }
    $('btn-send-broadcast-sop').disabled = true;
    api('/api/broadcast-sop', 'POST', { sop_id: sopId }).then(function(r) {
      toast('راهنما به ' + r.sent + ' کاربر ارسال شد');
    }).catch(function() {}).finally(function() { $('btn-send-broadcast-sop').disabled = false; });
  });

  // ========== STATUS & POLLING ==========
  function updateStatus() {
    api('/api/status').then(function(s) {
      $('status-dot').className = 'status-dot online';
      $('status-text').textContent = 'آنلاین';
      $('update-time').textContent = 'بروز: ' + new Date().toLocaleTimeString('fa-IR');
      if (APP.currentPage === 'dashboard') loadDashboard();
      else if (APP.currentPage === 'messages' && APP.selectedUserId) {
        loadConversation(APP.selectedUserId);
        loadMessageUsers();
      }
      if (s.total_messages > APP.lastMsgCount) {
        var diff = s.total_messages - APP.lastMsgCount;
        if (APP.currentPage !== 'messages') {
          var badge = $('unread-badge');
          badge.textContent = diff;
          badge.style.display = 'inline';
        }
        APP.lastMsgCount = s.total_messages;
      }
    }).catch(function() {
      $('status-dot').className = 'status-dot';
      $('status-text').textContent = 'قطع';
    });
  }

  // ========== INIT ==========
  function init() {
    loadDashboard();
    updateStatus();
    setInterval(updateStatus, 5000);
  }

  // KEYBOARD SHORTCUT: ESC closes modals
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      var modals = document.querySelectorAll('.modal-overlay.show');
      for (var i = 0; i < modals.length; i++) { modals[i].classList.remove('show'); }
    }
  });

  // Start the app when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html = DASHBOARD_HTML.replace('"__BASE_PATH__"', json.dumps(config.SECRET_PATH))
    return HTMLResponse(content=html)

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


# ===================== BOT POLLING =====================

def bot_polling_loop():
    """Background bot polling thread"""
    import time as time_mod, requests as req
    B = '\033[38;2;91;154;255m'   # blue
    G = '\033[38;2;14;203;129m'   # green
    Y = '\033[38;2;240;165;0m'    # gold
    R = '\033[38;2;246;70;93m'    # red
    D = '\033[38;2;148;163;184m'  # dim
    RST = '\033[0m'
    print(f"{G}  > {RST} Bot polling started {D}(admin: {config.ADMIN_ID}){RST}")
    offset = 0
    while True:
        try:
            url = f"{config.BASE_URL}/getUpdates"
            resp = req.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
            if resp.status_code != 200:
                time_mod.sleep(3)
                continue
            result = resp.json()
            if not result.get("ok"):
                continue
            updates = result.get("result", [])
            for update in updates:
                try:
                    bot_core.process_update(update)
                except Exception as e:
                    print(f"{R}[Bot] Update error: {e}{RST}")
                offset = update["update_id"] + 1
            if updates:
                print(f"{D}[{time.strftime('%H:%M:%S')}]{RST} {Y}{len(updates)}{RST} new message(s)")
        except req.exceptions.Timeout:
            pass
        except req.exceptions.ConnectionError:
            print(f"{R}  ✗ Connection error, retrying...{RST}")
            time_mod.sleep(5)
        except Exception as e:
            print(f"{R}[Bot] Error: {e}{RST}")
            time_mod.sleep(3)


def run():
    """Start web server + bot concurrently"""
    B = '\033[38;2;91;154;255m'   # blue
    P = '\033[38;2;167;139;250m'  # purple
    G = '\033[38;2;14;203;129m'   # green
    W = '\033[38;2;255;255;255m'  # white
    D = '\033[38;2;148;163;184m'  # dim gray
    RST = '\033[0m'

    bot_core.init()

    bot_thread = threading.Thread(target=bot_polling_loop, daemon=True)
    bot_thread.start()

    print(f"\n{G}  > {RST}  Dashboard {W}http://{config.WEB_HOST}:{config.WEB_PORT}{RST}")
    print(f"{D}     Bot running in background{RST}\n")
    uvicorn.run(app, host=config.WEB_HOST, port=config.WEB_PORT, log_level="warning")


if __name__ == "__main__":
    run()
