# -*- coding: utf-8 -*-
# تنظیمات ربات بله + وب سرور

# توکن ربات را از BotFather بله دریافت کنید
BOT_TOKEN = "2083170203:_iK6HJbDTHdkfSoBEyqPrCBNVP4QQx0GdYs"

# آیدی عددی ادمین (مدیر) - برای دریافت نوتیفیکیشن‌ها
ADMIN_ID = 1682983321

# آدرس پایه API بله (سازگار با Telegram Bot API)
BASE_URL = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

# مسیر فایل‌های ذخیره‌سازی
DATA_DIR = "data"
DATABASE_PATH = f"{DATA_DIR}/database.db"

# تنظیمات وب سرور
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
SECRET_PATH = ""

# ===================== همگام‌سازی با سایت =====================
SYNC_BASE_URL = ""
SYNC_API_KEY = ""

# ===================== هوش مصنوعی برای تطبیق SOP =====================
AI_BASE_URL = ""
AI_API_KEY = ""
AI_MODEL = "gpt-4o-mini"
# تنظیمات ویس (voice message)
VOICE_DIR = f"{DATA_DIR}/voices"

AI_PROMPT = (
    "تو یه دستیار هوشمندی. لیست SOPهای تعریف شده:\n{sops}\n\n"
    "پیام کاربر:\n{message}\n\n"
    "کدام SOP最适合 این سواله؟ فقط اسم دقیق SOP رو بنویس. "
    "اگر هیچکدوم مناسب نبود، بنویس: none"
)
