# -*- coding: utf-8 -*-
# هسته ربات بله - توابع اصلی بدون حلقه polling
# این ماژول توسط web_server.py استفاده می‌شود

import json, os, time, requests, config
from state import StateMachine
from analytics import Analytics
import sync

analytics = Analytics()
state_machine = StateMachine()

def init():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.VOICE_DIR, exist_ok=True)
    state_machine.load(config.STATES_FILE)
    analytics._ensure_file()
    # load data files into memory cache at startup
    _load_registered()
    _load_sops()
    _load_employers()
    _load_forward_map()

# ===================== API بله =====================

def api_request(method, data=None):
    url = f"{config.BASE_URL}/{method}"
    try:
        if data:
            resp = requests.post(url, json=data, timeout=10)
        else:
            resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            if result.get("ok"):
                return result.get("result")
        return None
    except Exception as e:
        print(f"[API] Error in {method}: {e}")
        return None

def send_message(chat_id, text, reply_markup=None, parse_mode="Markdown", reply_to_message_id=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup is not None:
        data["reply_markup"] = reply_markup
    if reply_to_message_id is not None:
        data["reply_to_message_id"] = reply_to_message_id
    return api_request("sendMessage", data)

def send_voice(chat_id, voice_file_id, caption=None, reply_markup=None):
    data = {"chat_id": chat_id, "voice": voice_file_id}
    if caption:
        data["caption"] = caption
    if reply_markup is not None:
        data["reply_markup"] = reply_markup
    return api_request("sendVoice", data)

def send_photo(chat_id, file_id, caption=None):
    data = {"chat_id": chat_id, "photo": file_id}
    if caption:
        data["caption"] = caption
    return api_request("sendPhoto", data)

def send_document(chat_id, file_id, caption=None):
    data = {"chat_id": chat_id, "document": file_id}
    if caption:
        data["caption"] = caption
    return api_request("sendDocument", data)

def send_video(chat_id, file_id, caption=None):
    data = {"chat_id": chat_id, "video": file_id}
    if caption:
        data["caption"] = caption
    return api_request("sendVideo", data)

def send_audio(chat_id, file_id, caption=None):
    data = {"chat_id": chat_id, "audio": file_id}
    if caption:
        data["caption"] = caption
    return api_request("sendAudio", data)

def get_file_path(file_id):
    result = api_request("getFile", {"file_id": file_id})
    if result and "file_path" in result:
        return result["file_path"]
    return None

def get_file_url(file_id):
    fp = get_file_path(file_id)
    if fp:
        return f"https://tapi.bale.ai/file/bot{config.BOT_TOKEN}/{fp}"
    return None

def get_voice_file_url(file_id):
    return get_file_url(file_id)

_bot_info_cache = None

def get_bot_info():
    global _bot_info_cache
    if _bot_info_cache:
        return _bot_info_cache
    result = api_request("getMe")
    if result:
        _bot_info_cache = result
        return result
    return None

# ===================== کاربران =====================

_registered_cache = {}

def _load_registered():
    global _registered_cache
    try:
        with open(config.REGISTERED_FILE, "r", encoding="utf-8") as f:
            _registered_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _registered_cache = {}

def _save_registered():
    with open(config.REGISTERED_FILE, "w", encoding="utf-8") as f:
        json.dump(_registered_cache, f, ensure_ascii=False, indent=2)

def load_registered():
    if not _registered_cache:
        _load_registered()
    return dict(_registered_cache)

def is_registered(user_id):
    return str(user_id) in _registered_cache

def register_user(user_id, first_name, phone):
    _registered_cache[str(user_id)] = {
        "first_name": first_name, "phone": phone,
        "registered_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    _save_registered()

def unregister_user(user_id):
    if str(user_id) in _registered_cache:
        del _registered_cache[str(user_id)]
        _save_registered()
        return True
    return False

# ===================== SOPها =====================

_sops_cache = []

def _load_sops():
    global _sops_cache
    try:
        with open(config.SOPS_FILE, "r", encoding="utf-8") as f:
            _sops_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _sops_cache = []

def _save_sops():
    with open(config.SOPS_FILE, "w", encoding="utf-8") as f:
        json.dump(_sops_cache, f, ensure_ascii=False, indent=2)

def load_sops():
    if not _sops_cache:
        _load_sops()
    return list(_sops_cache)

def add_sop(name, response, keywords=""):
    sop = {
        "id": len(_sops_cache) + 1,
        "name": name.strip(),
        "response": response.strip(),
        "keywords": [k.strip() for k in keywords.split(",") if k.strip()],
        "smart_enabled": True,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "use_count": 0
    }
    _sops_cache.append(sop)
    _save_sops()
    sync.sync_sop(sop)
    return sop

def update_sop(sop_id, name=None, response=None, keywords=None, smart_enabled=None):
    for s in _sops_cache:
        if s["id"] == sop_id:
            if name: s["name"] = name.strip()
            if response: s["response"] = response.strip()
            if keywords is not None: s["keywords"] = [k.strip() for k in keywords.split(",") if k.strip()]
            if smart_enabled is not None: s["smart_enabled"] = smart_enabled
            _save_sops()
            return s
    return None

def delete_sop(sop_id):
    global _sops_cache
    for i, s in enumerate(_sops_cache):
        if s["id"] == sop_id:
            _sops_cache.pop(i)
            _save_sops()
            return True
    return False

# ===================== پاسخ هوشمند (کلمات کلیدی) =====================

def find_smart_reply(text):
    """بررسی پیام کاربر با کلمات کلیدی SOPها. در صورت تطابق، SOP مربوطه رو برمی‌گردونه"""
    text_lower = text.lower().strip()
    if not text_lower:
        return None
    best_sop = None
    best_count = 0
    for s in _sops_cache:
        if not s.get("smart_enabled", True):
            continue
        keywords = s.get("keywords", [])
        if not keywords:
            continue
        match_count = 0
        for kw in keywords:
            if kw and kw.lower() in text_lower:
                match_count += 1
        if match_count > 0 and match_count > best_count:
            best_count = match_count
            best_sop = s
    return best_sop

# ===================== کارفرمایان =====================

_employers_cache = []

def _load_employers():
    global _employers_cache
    try:
        with open(config.EMPLOYERS_FILE, "r", encoding="utf-8") as f:
            _employers_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _employers_cache = []

def _save_employers():
    with open(config.EMPLOYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(_employers_cache, f, ensure_ascii=False, indent=2)

def load_employers():
    if not _employers_cache:
        _load_employers()
    return list(_employers_cache)

def add_employer(name, admin_id, description=""):
    import random, string
    code = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    employer = {
        "id": len(_employers_cache) + 1,
        "name": name.strip(),
        "admin_id": str(admin_id).strip(),
        "description": description.strip(),
        "code": code,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "active": True
    }
    _employers_cache.append(employer)
    _save_employers()
    return employer

def update_employer(emp_id, name=None, admin_id=None, description=None, active=None):
    for e in _employers_cache:
        if e["id"] == emp_id:
            if name: e["name"] = name.strip()
            if admin_id: e["admin_id"] = str(admin_id).strip()
            if description is not None: e["description"] = description.strip()
            if active is not None: e["active"] = active
            _save_employers()
            return e
    return None

def delete_employer(emp_id):
    global _employers_cache
    for i, e in enumerate(_employers_cache):
        if e["id"] == emp_id:
            _employers_cache.pop(i)
            _save_employers()
            return True
    return False

def find_employer_by_code(code):
    employers = load_employers()
    for e in employers:
        if e["code"] == code and e.get("active", True):
            return e
    return None

def find_employer_by_admin_id(admin_id):
    employers = load_employers()
    for e in employers:
        if e["admin_id"] == str(admin_id) and e.get("active", True):
            return e
    return None

def forward_to_employers(user_id, first_name, text, file_type=None, file_id=None):
    """فوروارد پیام به همه کارفرمایان فعال"""
    employers = load_employers()
    phone = load_registered().get(str(user_id), {}).get("phone", "نامشخص")
    for emp in employers:
        if not emp.get("active", True):
            continue
        emp_admin_id = emp.get("admin_id", "")
        if not emp_admin_id or str(emp_admin_id) == str(config.ADMIN_ID):
            continue
        if file_type and file_id:
            header = f"📩 *{file_type} جدید برای {emp['name']}:*\n\n👤 *نام:* {first_name}\n🆔 *آیدی:* {user_id}\n📞 *شماره:* {phone}"
            if file_type == "🎤":
                send_message(int(emp_admin_id), header)
                send_voice(int(emp_admin_id), file_id)
            elif file_type == "🖼":
                send_message(int(emp_admin_id), header)
                send_photo(int(emp_admin_id), file_id, text or None)
            elif file_type == "📎":
                send_message(int(emp_admin_id), header)
                send_document(int(emp_admin_id), file_id)
            else:
                send_message(int(emp_admin_id), header)
        else:
            emp_msg = f"📩 *پیام جدید برای {emp['name']}:*\n\n👤 *نام:* {first_name}\n🆔 *آیدی:* {user_id}\n📞 *شماره:* {phone}\n💬 *متن:*\n{text}"
            result = send_message(int(emp_admin_id), emp_msg)
            if result:
                mid = result.get("message_id")
                if mid:
                    _forward_map_cache[str(mid)] = {"user_id": user_id, "first_name": first_name}
                    _save_forward_map()

def regenerate_employer_code(emp_id):
    import random, string
    for e in _employers_cache:
        if e["id"] == emp_id:
            e["code"] = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            _save_employers()
            return e["code"]
    return None

# ===================== فوروارد مپ =====================

_forward_map_cache = {}

def _load_forward_map():
    global _forward_map_cache
    try:
        with open(config.FORWARD_MAP_FILE, "r", encoding="utf-8") as f:
            _forward_map_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _forward_map_cache = {}

def _save_forward_map():
    with open(config.FORWARD_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(_forward_map_cache, f, ensure_ascii=False, indent=2)

# ===================== کیبورد منو =====================

def main_menu_keyboard():
    return {
        "keyboard": [
            [{"text": "📝 ارسال پیام جدید"}],
            [{"text": "📞 اطلاعات تماس"}]
        ],
        "resize_keyboard": True
    }

# ===================== هندلرهای اصلی =====================

def handle_start(chat_id, user_id, first_name):
    if is_registered(user_id):
        text = f"👋 خوش آمدید {first_name} عزیز!\n\nاز منوی زیر استفاده کنید:\n\n📝 *ارسال پیام جدید* - ارسال پیام به کارفرما\n📞 *اطلاعات تماس* - شماره ثبت شده شما"
        send_message(chat_id, text, reply_markup=main_menu_keyboard())
    else:
        keyboard = {"keyboard": [[{"text": "📱 ارسال شماره تماس", "request_contact": True}]], "resize_keyboard": True, "one_time_keyboard": True}
        text = f"👋 *به ربات ارتباط با کارفرما خوش آمدید، {first_name} عزیز!*\n\nلطفاً شماره تماس خود را با کلیک روی دکمه زیر ارسال کنید."
        send_message(chat_id, text, reply_markup=keyboard)

def handle_contact(chat_id, user_id, first_name, contact):
    phone = contact.get("phone_number", "نامشخص")
    register_user(user_id, first_name, phone)
    analytics.log_contact(user_id, first_name, phone)
    sync.sync_user(user_id, first_name, phone, time.strftime("%Y-%m-%d %H:%M:%S"))
    send_message(chat_id, f"✅ شماره تماس شما ثبت شد، {first_name} عزیز!\n\nاز این به بعد هر پیامی بفرستید، مستقیماً به کارفرما می‌رسد.", reply_markup=main_menu_keyboard())

def forward_to_admin(chat_id, user_id, text, first_name):
    """فوروارد پیام کاربر به ادمین (FIX: argument order corrected: text THEN first_name)"""
    analytics.log_message(user_id, first_name, text)
    sync.sync_message(user_id, first_name, text, time.strftime("%Y-%m-%d %H:%M:%S"))

    sops = load_sops()
    matched = None
    if config.AI_BASE_URL:
        matched = sync.ai_match_sop(text, sops)
    if not matched:
        text_lower = text.lower()
        for sop in sops:
            if sop["name"].lower() in text_lower:
                matched = sop
                break

    if matched:
        reply = f"📋 *{matched['name']}*\n\n{matched['response']}\n\n—‌—‌—‌—‌—‌—‌—\n💡 اگر جواب کاملی نگرفتید، دوباره پیام بدهید تا به کارفرما منتقل شود."
        send_message(chat_id, reply)
        matched["use_count"] = matched.get("use_count", 0) + 1
        _save_sops()
        analytics.log_admin_reply(user_id, first_name, f"🤖 پاسخ خودکار SOP: {matched['name']}\n{matched['response']}")
        send_message(config.ADMIN_ID, f"🤖 *SOP فعال شد:*\n👤 {first_name}\n📌 {matched['name']}\n📊 {matched['use_count']} بار")
        return

    phone = load_registered().get(str(user_id), {}).get("phone", "نامشخص")
    admin_msg = f"📩 *پیام جدید از کاربر:*\n\n👤 *نام:* {first_name}\n🆔 *آیدی:* {user_id}\n📞 *شماره:* {phone}\n💬 *متن:*\n{text}"
    result = send_message(config.ADMIN_ID, admin_msg)
    if result:
        mid = result.get("message_id")
        if mid:
            _forward_map_cache[str(mid)] = {"user_id": user_id, "first_name": first_name}
            _save_forward_map()

    forward_to_employers(user_id, first_name, text)

    send_message(chat_id, "✅ پیام شما ارسال شد.\n📝 پیام بعدی را بنویسید...", reply_markup=main_menu_keyboard())

def reply_to_user(user_id, text):
    """ارسال پاسخ از ادمین (وب پنل) به کاربر"""
    if len(text.strip()) < 2:
        return False, "پیام خیلی کوتاه است"
    msg_text = f"📨 *پاسخ کارفرما:*\n\n{text.strip()}"
    result = send_message(int(user_id), msg_text)
    if result:
        user_info = load_registered().get(str(user_id), {})
        name = user_info.get("first_name", "کاربر")
        analytics.log_admin_reply(user_id, name, text)
        return True, f"پاسخ به {name} ارسال شد"
    return False, "خطا در ارسال"

def reply_photo_to_user(user_id, file_id_or_path, caption=""):
    if os.path.isfile(file_id_or_path):
        file_path = file_id_or_path
        url = f"{config.BASE_URL}/sendPhoto"
        try:
            data = {"chat_id": int(user_id)}
            if caption and caption.strip():
                data["caption"] = caption.strip()
            with open(file_path, "rb") as f:
                resp = requests.post(url, data=data, files={"photo": f}, timeout=30)
            if resp.status_code == 200 and resp.json().get("ok"):
                user_info = load_registered().get(str(user_id), {})
                name = user_info.get("first_name", "کاربر")
                analytics.log_admin_reply(user_id, name, f"[photo:sent] {caption}")
                return True, f"عکس به {name} ارسال شد"
            return False, "خطا"
        except Exception as e:
            return False, f"خطا: {e}"
    result = send_photo(int(user_id), file_id_or_path, caption or None)
    if result:
        user_info = load_registered().get(str(user_id), {})
        name = user_info.get("first_name", "کاربر")
        analytics.log_admin_reply(user_id, name, f"[photo:{file_id_or_path}] {caption}")
        return True, f"عکس به {name} ارسال شد"
    return False, "خطا"

def reply_document_to_user(user_id, file_id_or_path):
    if os.path.isfile(file_id_or_path):
        file_path = file_id_or_path
        url = f"{config.BASE_URL}/sendDocument"
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(url, data={"chat_id": int(user_id)}, files={"document": f}, timeout=30)
            if resp.status_code == 200 and resp.json().get("ok"):
                user_info = load_registered().get(str(user_id), {})
                name = user_info.get("first_name", "کاربر")
                analytics.log_admin_reply(user_id, name, f"[document:sent]")
                return True, f"فایل به {name} ارسال شد"
            return False, "خطا"
        except Exception as e:
            return False, f"خطا: {e}"
    result = send_document(int(user_id), file_id_or_path)
    if result:
        user_info = load_registered().get(str(user_id), {})
        name = user_info.get("first_name", "کاربر")
        analytics.log_admin_reply(user_id, name, f"[document:{file_id_or_path}]")
        return True, f"فایل به {name} ارسال شد"
    return False, "خطا"

def reply_voice_to_user(user_id, voice_file_id_or_path):
    """ارسال پیام صوتی از ادمین (وب پنل) به کاربر"""
    # اگه فایل محلی باشه، اول آپلودش می‌کنیم
    if os.path.isfile(voice_file_id_or_path):
        file_path = voice_file_id_or_path
        url = f"{config.BASE_URL}/sendVoice"
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(url, data={"chat_id": int(user_id)}, files={"voice": f}, timeout=30)
            if resp.status_code == 200 and resp.json().get("ok"):
                user_info = load_registered().get(str(user_id), {})
                name = user_info.get("first_name", "کاربر")
                file_id = resp.json().get("result", {}).get("voice", {}).get("file_id", "")
                analytics.log_admin_reply(user_id, name, f"[voice:{file_id}]" if file_id else "[voice:sent]")
                return True, f"پیام صوتی به {name} ارسال شد"
            return False, "خطا در ارسال فایل صوتی"
        except Exception as e:
            return False, f"خطا: {e}"
    # مستقیم file_id
    result = send_voice(int(user_id), voice_file_id_or_path)
    if result:
        user_info = load_registered().get(str(user_id), {})
        name = user_info.get("first_name", "کاربر")
        analytics.log_admin_reply(user_id, name, f"[voice:{voice_file_id_or_path}]")
        return True, f"پیام صوتی به {name} ارسال شد"
    return False, "خطا در ارسال"

def reply_video_to_user(user_id, file_id_or_path):
    if os.path.isfile(file_id_or_path):
        file_path = file_id_or_path
        url = f"{config.BASE_URL}/sendVideo"
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(url, data={"chat_id": int(user_id)}, files={"video": f}, timeout=30)
            if resp.status_code == 200 and resp.json().get("ok"):
                user_info = load_registered().get(str(user_id), {})
                name = user_info.get("first_name", "کاربر")
                analytics.log_admin_reply(user_id, name, "[video:sent]")
                return True, f"ویدیو به {name} ارسال شد"
            return False, "خطا"
        except Exception as e:
            return False, f"خطا: {e}"
    result = send_video(int(user_id), file_id_or_path)
    if result:
        user_info = load_registered().get(str(user_id), {})
        name = user_info.get("first_name", "کاربر")
        analytics.log_admin_reply(user_id, name, f"[video:{file_id_or_path}]")
        return True, f"ویدیو به {name} ارسال شد"
    return False, "خطا"

def reply_audio_to_user(user_id, file_id_or_path):
    if os.path.isfile(file_id_or_path):
        file_path = file_id_or_path
        url = f"{config.BASE_URL}/sendAudio"
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(url, data={"chat_id": int(user_id)}, files={"audio": f}, timeout=30)
            if resp.status_code == 200 and resp.json().get("ok"):
                user_info = load_registered().get(str(user_id), {})
                name = user_info.get("first_name", "کاربر")
                analytics.log_admin_reply(user_id, name, "[audio:sent]")
                return True, f"صوت به {name} ارسال شد"
            return False, "خطا"
        except Exception as e:
            return False, f"خطا: {e}"
    result = send_audio(int(user_id), file_id_or_path)
    if result:
        user_info = load_registered().get(str(user_id), {})
        name = user_info.get("first_name", "کاربر")
        analytics.log_admin_reply(user_id, name, f"[audio:{file_id_or_path}]")
        return True, f"صوت به {name} ارسال شد"
    return False, "خطا"

def broadcast_message(targets, text):
    """ارسال پیام همگانی"""
    if not targets:
        registered = load_registered()
        targets = list(registered.keys())
    sent = 0
    for uid in targets:
        msg_text = f"📨 *پیام کارفرما:*\n\n{text.strip()}"
        if send_message(int(uid), msg_text):
            sent += 1
            user_info = load_registered().get(str(uid), {})
            name = user_info.get("first_name", "کاربر")
            analytics.log_admin_reply(uid, name, text.strip())
    return sent

def broadcast_sop(sop_id, targets=None):
    """ارسال SOP همگانی"""
    sops = load_sops()
    sop = next((s for s in sops if s["id"] == sop_id), None)
    if not sop:
        return 0
    if not targets:
        registered = load_registered()
        targets = list(registered.keys())
    sop_text = f"📋 *{sop['name']}*\n\n{sop['response']}\n\n—‌—‌—‌—‌—‌—‌—\n💡 این پیام از طرف کارفرما ارسال شده است."
    sent = 0
    for uid in targets:
        if send_message(int(uid), sop_text):
            sent += 1
            user_info = load_registered().get(str(uid), {})
            name = user_info.get("first_name", "کاربر")
            analytics.log_admin_reply(uid, name, f"📋 SOP: {sop['name']}\n{sop['response']}")
    return sent

# ===================== پردازش آپدیت‌ها =====================

def process_update(update):
    """پردازش یک update از API بله"""
    if "message" not in update:
        return

    msg = update["message"]
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    first_name = msg["from"].get("first_name", "کاربر")
    text = msg.get("text", "")

    # -- هندل پاسخ ادمین به پیام فوروارد شده --
    if user_id == config.ADMIN_ID:
        if text and text.startswith("/start"):
            parts = text.split(maxsplit=1)
            payload = parts[1] if len(parts) > 1 else ""
            if payload.startswith("emp_"):
                code = payload[4:]
                employer = find_employer_by_code(code)
                if employer:
                    send_message(chat_id, f"🔗 لینک دعوت کارفرما:\n\n👤 {employer['name']}\n🆔 آیدی: {employer['admin_id']}\n📋 توضیحات: {employer.get('description', '')}\n✅ وضعیت: {'فعال' if employer.get('active', True) else 'غیرفعال'}\n\nاین لینک مخصوص {employer['name']} است.")
                    return
                send_message(chat_id, "❌ کد نامعتبر")
                return
            handle_start(chat_id, user_id, first_name)
            return

        reply_to = msg.get("reply_to_message")
        if reply_to:
            reply_msg_id = str(reply_to.get("message_id", ""))
            if reply_msg_id in _forward_map_cache:
                target = _forward_map_cache[reply_msg_id]
                target_uid = target["user_id"]
                target_name = target.get("first_name", "کاربر")
                # اگر ادمین ویس فرستاده
                if "voice" in msg:
                    voice = msg["voice"]
                    file_id = voice["file_id"]
                    result = send_voice(int(target_uid), file_id)
                    if result:
                        analytics.log_admin_reply(target_uid, target_name, f"[voice:{file_id}]")
                        send_message(chat_id, f"✅ پیام صوتی شما به *{target_name}* ارسال شد.")
                    else:
                        send_message(chat_id, f"⚠️ خطا در ارسال پیام صوتی به {target_name}")
                    return
                # اگر ادمین عکس فرستاده
                if "photo" in msg:
                    photos = msg["photo"]
                    file_id = photos[-1]["file_id"]
                    result = send_photo(int(target_uid), file_id, text.strip() or None)
                    if result:
                        analytics.log_admin_reply(target_uid, target_name, f"[photo:{file_id}] {text}")
                        send_message(chat_id, f"✅ عکس به *{target_name}* ارسال شد.")
                    else:
                        send_message(chat_id, f"⚠️ خطا در ارسال عکس به {target_name}")
                    return
                # اگر ادمین فایل فرستاده
                if "document" in msg:
                    doc = msg["document"]
                    file_id = doc["file_id"]
                    result = send_document(int(target_uid), file_id)
                    if result:
                        analytics.log_admin_reply(target_uid, target_name, f"[document:{file_id}]")
                        send_message(chat_id, f"✅ فایل به *{target_name}* ارسال شد.")
                    else:
                        send_message(chat_id, f"⚠️ خطا در ارسال فایل به {target_name}")
                    return
                reply_text = f"📨 *پاسخ کارفرما:*\n\n{text.strip()}"
                result = send_message(int(target_uid), reply_text)
                if result:
                    analytics.log_admin_reply(target_uid, target_name, text)
                    send_message(chat_id, f"✅ پاسخ شما به *{target_name}* ارسال شد.")
                else:
                    send_message(chat_id, f"⚠️ خطا در ارسال پاسخ به {target_name}")
                return
        return

    # پیام‌های کاربران عادی
    if text and text.startswith("/start"):
        parts = text.split(maxsplit=1)
        payload = parts[1] if len(parts) > 1 else ""
        if payload.startswith("emp_"):
            code = payload[4:]
            employer = find_employer_by_code(code)
            if employer:
                emp_admin_id = int(employer["admin_id"])
                if user_id == emp_admin_id:
                    send_message(chat_id, f"✅ احراز هویت شدید، {employer['name']} عزیز!\n\nشما به عنوان کارفرما تأیید شدید. پیام‌های کاربران ثبت‌نام کرده برای شما ارسال خواهد شد.", reply_markup=main_menu_keyboard())
                    analytics.log_admin_reply(user_id, employer['name'], f"[employer_auth:{employer['name']}]")
                    return
                else:
                    send_message(chat_id, "❌ این لینک مخصوص کارفرما است. لطفاً با آیدی عددی خود وارد شوید.")
                    return
            else:
                send_message(chat_id, "❌ لینک دعوت نامعتبر است.")
                return
        handle_start(chat_id, user_id, first_name)
        return

    if not is_registered(user_id):
        if "contact" in msg:
            handle_contact(chat_id, user_id, first_name, msg["contact"])
        else:
            handle_start(chat_id, user_id, first_name)
        return

    # هندل دکمه‌های منو
    if text == "📞 اطلاعات تماس":
        phone = load_registered().get(str(user_id), {}).get("phone", "ثبت نشده")
        send_message(chat_id, f"📞 *شماره تماس ثبت شده شما:*\n\n{phone}\n\nبرای تغییر شماره با ادمین تماس بگیرید.", reply_markup=main_menu_keyboard())
        return
    if text == "📝 ارسال پیام جدید":
        send_message(chat_id, "📝 *متن پیام خود را بنویسید...*\n\nهر چیزی که می‌خواید به کارفرما بگید، تایپ کنید و بفرستید.", reply_markup=main_menu_keyboard())
        return

    # هندل ویس دریافتی از کاربر (یک درخواست با کپشن)
    if "voice" in msg:
        voice = msg["voice"]
        file_id = voice["file_id"]
        duration = voice.get("duration", 0)
        analytics.log_message(user_id, first_name, f"[voice:{file_id}] (duration: {duration}s)")
        sync.sync_message(user_id, first_name, f"[voice:{file_id}]", time.strftime("%Y-%m-%d %H:%M:%S"))
        phone = load_registered().get(str(user_id), {}).get("phone", "نامشخص")
        caption = f"🎤 {first_name}\n📞 {phone}\n⏱ {duration} ثانیه"
        voice_result = send_voice(config.ADMIN_ID, file_id, caption)
        if voice_result:
            voice_mid = voice_result.get("message_id")
            if voice_mid:
                _forward_map_cache[str(voice_mid)] = {"user_id": user_id, "first_name": first_name}
        _save_forward_map()
        forward_to_employers(user_id, first_name, "", file_type="🎤", file_id=file_id)
        send_message(chat_id, "✅ پیام صوتی شما ارسال شد.\n📝 پیام بعدی را بنویسید...", reply_markup=main_menu_keyboard())
        return

    # هندل عکس دریافتی از کاربر (یک درخواست با کپشن کامل)
    if "photo" in msg:
        photos = msg["photo"]
        file_id = photos[-1]["file_id"]
        user_caption = msg.get("caption", "")
        analytics.log_message(user_id, first_name, f"[photo:{file_id}] {user_caption}")
        sync.sync_message(user_id, first_name, f"[photo:{file_id}]", time.strftime("%Y-%m-%d %H:%M:%S"))
        phone = load_registered().get(str(user_id), {}).get("phone", "نامشخص")
        caption = f"🖼 عکس از {first_name}\n📞 {phone}"
        if user_caption:
            caption += f"\n💬 {user_caption}"
        photo_result = send_photo(config.ADMIN_ID, file_id, caption)
        if photo_result:
            photo_mid = photo_result.get("message_id")
            if photo_mid:
                _forward_map_cache[str(photo_mid)] = {"user_id": user_id, "first_name": first_name}
        _save_forward_map()
        forward_to_employers(user_id, first_name, user_caption, file_type="🖼", file_id=file_id)
        send_message(chat_id, "✅ عکس شما ارسال شد.\n📝 پیام بعدی را بنویسید...", reply_markup=main_menu_keyboard())
        return

    # هندل فایل دریافتی از کاربر (یک درخواست با کپشن)
    if "document" in msg:
        doc = msg["document"]
        file_id = doc["file_id"]
        file_name = doc.get("file_name", "فایل")
        analytics.log_message(user_id, first_name, f"[document:{file_id}] {file_name}")
        sync.sync_message(user_id, first_name, f"[document:{file_id}]", time.strftime("%Y-%m-%d %H:%M:%S"))
        phone = load_registered().get(str(user_id), {}).get("phone", "نامشخص")
        caption = f"📎 فایل از {first_name}\n📞 {phone}\n📄 {file_name}"
        doc_result = send_document(config.ADMIN_ID, file_id, caption)
        if doc_result:
            doc_mid = doc_result.get("message_id")
            if doc_mid:
                _forward_map_cache[str(doc_mid)] = {"user_id": user_id, "first_name": first_name}
        _save_forward_map()
        forward_to_employers(user_id, first_name, file_name, file_type="📎", file_id=file_id)
        send_message(chat_id, "✅ فایل شما ارسال شد.\n📝 پیام بعدی را بنویسید...", reply_markup=main_menu_keyboard())
        return

    # ===== پاسخ هوشمند: بررسی کلمات کلیدی =====
    if text:
        smart_sop = find_smart_reply(text)
        if smart_sop:
            reply_text = smart_sop["response"]
            send_message(chat_id, reply_text, reply_markup=main_menu_keyboard())
            analytics.log_admin_reply(user_id, first_name, f"[auto:{smart_sop['name']}] {reply_text}")
            sync.sync_message(user_id, first_name, f"[auto:{smart_sop['name']}] {reply_text}", time.strftime("%Y-%m-%d %H:%M:%S"))
            smart_sop["use_count"] = smart_sop.get("use_count", 0) + 1
            _save_sops()
            return

    forward_to_admin(chat_id, user_id, text, first_name)
