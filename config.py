import os
from pathlib import Path
from dotenv import load_dotenv

# 기본 경로
BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR.parent

# .env 로드
load_dotenv(BASE_DIR / ".env")

def get_secret(key: str, default: str = "") -> str:
    # 1. 시스템 환경변수 확인
    val = os.getenv(key)
    if val:
        return val
    # 2. Streamlit Cloud Secrets 및 secrets.toml 확인
    try:
        import streamlit as st
        if hasattr(st, "secrets") and st.secrets is not None:
            if key in st.secrets:
                return str(st.secrets[key])
            if key.lower() in st.secrets:
                return str(st.secrets[key.lower()])
            # 중첩 섹션 ([general], [secrets] 등) 탐색
            for v in st.secrets.values():
                if isinstance(v, dict):
                    if key in v:
                        return str(v[key])
                    if key.lower() in v:
                        return str(v[key.lower()])
    except Exception:
        pass
    return default

# API Keys
GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "")
FOOD_SAFETY_API_KEY = get_secret("FOOD_SAFETY_API_KEY", "")
FOOD_SAFETY_SERVICE_ID = get_secret("FOOD_SAFETY_SERVICE_ID", "I2715")
SAFETYKOREA_API_KEY = get_secret("SAFETYKOREA_API_KEY", "")

# 서버 설정
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# 데이터 및 이미지 경로 설정
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

TEMP_UPLOADS_DIR = BASE_DIR / "temp_uploads"
TEMP_UPLOADS_DIR.mkdir(exist_ok=True)

# 자체 SQLite 데이터베이스 경로 (식품안전나라 공식 Open API 수집 전용)
SQLITE_DB_PATH = DATA_DIR / "customs_safety.db"

# 로컬 캐시 JSON 경로 (보조 백업용)
LOCAL_DB_JSON_PATH = DATA_DIR / "drugs_db_cache.json"

# 기존 다운로드 이미지 디렉터리 탐색
IMAGE_DIR_CANDIDATES = [
    DATA_DIR / "product_images",
    WORKSPACE_DIR / "Customs_AI_Bot" / "all_downloaded_images",
    WORKSPACE_DIR / "all_downloaded_images",
]

PRODUCT_IMAGE_DIR = None
for p in IMAGE_DIR_CANDIDATES:
    if p.exists():
        PRODUCT_IMAGE_DIR = p
        break

if PRODUCT_IMAGE_DIR is None:
    PRODUCT_IMAGE_DIR = DATA_DIR / "product_images"
    PRODUCT_IMAGE_DIR.mkdir(exist_ok=True)
