import os
import json
import platform

# 🔥 xác định thư mục cache chuẩn theo hệ điều hành
def get_cache_dir():
    if platform.system() == "Windows":
        base = os.getenv("APPDATA", os.path.expanduser("~"))
    elif platform.system() == "Darwin":
        base = os.path.expanduser("~/Library/Caches")
    else:
        base = os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return os.path.join(base, "srt_translator")

CACHE_DIR = get_cache_dir()
CACHE_FILE = os.path.join(CACHE_DIR, "translation_cache.json")
MAX_CACHE_SIZE_MB = 50  # giới hạn cache tối đa

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)

def load_cache():
    ensure_cache_dir()
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(cache):
    ensure_cache_dir()
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        return
    
    # kiểm tra size
    try:
        size_mb = os.path.getsize(CACHE_FILE) / (1024 * 1024)
        if size_mb > MAX_CACHE_SIZE_MB:
            clear_cache()
            print(f"[INFO] Cache quá lớn ({size_mb:.2f}MB), đã xóa.")
    except Exception:
        pass

def clear_cache():
    ensure_cache_dir()
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
    except Exception:
        pass

def cache_size_bytes():
    ensure_cache_dir()
    try:
        if os.path.exists(CACHE_FILE):
            return os.path.getsize(CACHE_FILE) / 1024.0  # KB
    except Exception:
        pass
    return 0.0
