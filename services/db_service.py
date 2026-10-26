import os
import sys
import re
import json
import sqlite3
import difflib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from config import SQLITE_DB_PATH, LOCAL_DB_JSON_PATH, PRODUCT_IMAGE_DIR

# Windows 콘솔 인코딩 안전화
try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 단독으로 위험 성분으로 판정하면 안 되는 일반적인 성분 목록
COMMON_SAFE_INGREDIENTS = {
    "water", "purified water", "aqua", "gelatin", "glycerin", "sugar",
    "caffeine", "salt", "sodium", "calcium", "magnesium", "vitamin",
    "vitamin c", "vitamin d", "zinc", "iron", "potassium", "물", "정제수",
    "젤라틴", "글리세린", "비타민", "카페인", "소금", "칼슘", "마그네슘"
}

# 주요 위해성분별 대국민 알기 쉬운 부작용 및 반입불가 사유 사전
HARMFUL_INGREDIENT_EXPLANATIONS = {
    "andrographis": {
        "name_ko": "천심련 (Andrographis)",
        "why_prohibited": "간 기능 손상 및 급성 알레르기(아나필락시스) 부작용 위험으로 식약처 해외직구 차단 원료로 지정되었습니다.",
        "health_risks": "간독성, 급성 피부 발진, 어지럼증, 임산부 유산 위험",
        "legal_basis": "식품위생법 제7조 및 식약처 해외직구 위해식품 공고"
    },
    "bacopa": {
        "name_ko": "바코파 (Bacopa monnieri)",
        "why_prohibited": "심박수 감소(서맥) 유발 및 소화기 장애 위험이 있어 국내 식품 및 건강기능식품 원료로 사용이 금지되어 있습니다.",
        "health_risks": "심박수 비정상적 저하(서맥), 심한 복통, 메스꺼움, 천식 악화",
        "legal_basis": "수입식품안전관리 특별법 제25조"
    },
    "ashwagandha": {
        "name_ko": "아슈와간다 (Ashwagandha)",
        "why_prohibited": "간 손상 및 갑상선 호르몬 과다 분비 등 중대한 부작용 보고가 급증하여 최근 식약처 반입금지 품목에 등재되었습니다.",
        "health_risks": "간 수치 급상승, 갑상선 기능 항진, 호흡 곤란",
        "legal_basis": "식약처 해외직구 위해원료 지정"
    },
    "yohimbine": {
        "name_ko": "요힘빈 (Yohimbine)",
        "why_prohibited": "혈압을 급격히 상승시키고 심장마비를 유발할 수 있어 관세청 및 식약처가 해외직구를 전면 차단하고 있습니다.",
        "health_risks": "심근경색, 뇌졸중, 극심한 불안 및 환각, 고혈압 위기",
        "legal_basis": "관세법 제234조 (수출입의 금지) 및 약사법 위반"
    },
    "sennoside": {
        "name_ko": "센노사이드 / 센나 (Sennoside / Senna)",
        "why_prohibited": "강력한 설사 유발 변비약 성분으로 장기 복용 시 장 마비와 흑색증을 일으키므로 의사 처방 없이 식품 혼입이 엄격히 금지됩니다.",
        "health_risks": "대장 점막 흑색증, 전해질 불균형, 만성 탈수, 대장 무력증",
        "legal_basis": "식약처 부정물질 및 해외직구 위해성분"
    },
    "senna": {
        "name_ko": "센나차 / 센나 (Senna)",
        "why_prohibited": "다이어트차에 흔히 악용되는 설사 유발 물질로, 복통과 만성 장 마비를 유발하여 반입이 불허됩니다.",
        "health_risks": "만성 설사, 대장 흑색증, 위경련",
        "legal_basis": "식품위생법상 식품 원료 사용불가"
    },
    "sildenafil": {
        "name_ko": "실데나필 (비아그라 성분)",
        "why_prohibited": "발기부전 치료 전문의약품 성분으로, 복용 시 혈압 급강하로 인한 실신 및 사망 위험이 있어 해외직구가 불법입니다.",
        "health_risks": "급격한 저혈압, 심근경색, 시력 상실, 뇌출혈",
        "legal_basis": "약사법 및 부정의약품 반입금지"
    },
    "tadalafil": {
        "name_ko": "타다라필 (시알리스 성분)",
        "why_prohibited": "심혈관계에 강력한 영향을 주는 전문의약품 성분으로 무단 복용 시 생명이 위험할 수 있어 적발 시 전량 폐기됩니다.",
        "health_risks": "심정지, 저혈압 쇼크, 지속 발기증",
        "legal_basis": "약사법 제61조 및 관세법 위반"
    },
    "melatonin": {
        "name_ko": "멜라토닌 (Melatonin)",
        "why_prohibited": "국내에서는 수면장애 치료 전문의약품으로 분류되어 의사의 처방전(소견서)이 있어야만 통관이 가능하며, 단순 직구 시 통관 보류됩니다.",
        "health_risks": "호르몬 교란, 만성 주간 졸음, 우울증 악화",
        "legal_basis": "약사법상 전문의약품 분류 (자가사용 인정기준 의사 처방전 필수)"
    },
    "ephedrine": {
        "name_ko": "에페드린 / 마황 (Ephedrine)",
        "why_prohibited": "필로폰 원료 물질이자 심장박동을 비정상적으로 자극하는 위험 성분으로 마약류 및 반입금지 물질로 관리됩니다.",
        "health_risks": "부정맥, 심장마비, 뇌출혈, 중독성",
        "legal_basis": "마약류 관리에 관한 법률 및 관세법"
    },
    "icariin": {
        "name_ko": "이카린 / 음양곽 (Icariin)",
        "why_prohibited": "혈압 저하 및 어지럼증을 유발하는 성분으로 성기능 보충제에 불법 혼입되어 적발되는 대표 위해물질입니다.",
        "health_risks": "어지럼증, 저혈압 쇼크, 구토",
        "legal_basis": "식약처 해외직구 반입차단 원료"
    },
    "sibutramine": {
        "name_ko": "시부트라민 (Sibutramine)",
        "why_prohibited": "심장마비와 뇌졸중 발생 위험으로 인해 전 세계적으로 허가가 취소된 비만약 성분으로 반입 시 엄중 처벌 대상입니다.",
        "health_risks": "치명적 심장마비, 뇌경색, 정신이상",
        "legal_basis": "식품위생법 및 관세법 수출입금지"
    },
    "cbd": {
        "name_ko": "CBD / 대마 성분 (Cannabidiol)",
        "why_prohibited": "대마에서 추출된 성분으로, 희귀질환 치료 목적으로 한국희귀필수의약품센터를 통한 승인을 받지 않은 일반 직구는 마약류로 형사처벌 대상입니다.",
        "health_risks": "신경계 억제, 인지기능 저하, 법적 마약류 처벌",
        "legal_basis": "마약류 관리에 관한 법률 위반"
    }
}

def get_ingredient_explanation(ingredient_name: str) -> Dict[str, str]:
    """성분명으로 대국민 알기 쉬운 반입금지 사유 조회"""
    if not ingredient_name:
        return {}
    clean = normalize_text(ingredient_name)
    for key, info in HARMFUL_INGREDIENT_EXPLANATIONS.items():
        if key in clean or clean in key:
            return info
    return {
        "name_ko": ingredient_name,
        "why_prohibited": "식품의약품안전처 및 관세청에서 안전성이 입증되지 않았거나 인체 유해 우려가 있어 해외직구 반입을 차단한 원료입니다.",
        "health_risks": "원료 기준 미달 및 오남용 시 소화기·간 기능 장애 우려",
        "legal_basis": "수입식품안전관리 특별법 제25조 (해외직구 차단)"
    }

def normalize_text(text: str) -> str:
    """텍스트 정규화: 소문자화, 특수문자 제거, 공백 축소"""
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"[^a-zA-Z0-9가-힣]", " ", text)
    return " ".join(text.split())

class DatabaseService:
    """
    식품안전나라 공식 Open API 수집 자료 전용 자체 SQLite 데이터베이스 서비스
    (엑셀 의존성 완전 제거, 자체 관계형 DB 영구 보관 및 고속 색인)
    """
    def __init__(self):
        self.db_path = Path(SQLITE_DB_PATH)
        self.records: List[Dict[str, Any]] = []
        self.barcode_map: Dict[str, Dict[str, Any]] = {}
        self.seq_map: Dict[str, Dict[str, Any]] = {}
        self.harmful_ingredients_set: set = set()
        self.last_sync_time: Optional[str] = None
        self.initialized = False
        
        # 자체 SQLite DB 초기화 및 데이터 로드
        self._init_sqlite()
        self.load_database()

    def _get_connection(self) -> sqlite3.Connection:
        """SQLite 커넥션 생성 (row_factory 설정)"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite(self):
        """자체 SQLite 테이블 및 인덱스 생성"""
        with self._get_connection() as conn:
            cur = conn.cursor()
            # 1. 식품안전나라 위해물품 메인 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS harmful_products (
                    seq TEXT PRIMARY KEY,
                    product_name TEXT NOT NULL,
                    barcode TEXT,
                    reg_date TEXT,
                    harmful_ingredient TEXT,
                    manufacturer TEXT,
                    country TEXT,
                    block_reason TEXT,
                    original_img_url TEXT,
                    local_img_path TEXT,
                    source TEXT DEFAULT '식품안전나라 공식 Open API',
                    updated_at TEXT
                )
            """)

            # 2. 고속 검색을 위한 인덱스 생성
            cur.execute("CREATE INDEX IF NOT EXISTS idx_hp_barcode ON harmful_products(barcode)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_hp_name ON harmful_products(product_name)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_hp_reg_date ON harmful_products(reg_date DESC)")

            # 3. 메타데이터 테이블 (동기화 일시, 통계 등)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS db_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def load_database(self):
        """자체 SQLite DB로부터 최신 데이터 로드 및 고속 인메모리 색인 구축"""
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                
                # 메타데이터 조회
                cur.execute("SELECT value FROM db_meta WHERE key = 'last_sync_time'")
                meta_row = cur.fetchone()
                if meta_row:
                    self.last_sync_time = meta_row["value"]

                # 전체 레코드 조회 (최신 등록일순)
                cur.execute("""
                    SELECT seq, product_name, barcode, reg_date, harmful_ingredient,
                           manufacturer, country, block_reason, original_img_url,
                           local_img_path, source, updated_at
                    FROM harmful_products
                    ORDER BY reg_date DESC, seq DESC
                """)
                rows = cur.fetchall()

                records = []
                for r in rows:
                    records.append({
                        "등록번호": r["seq"] or "",
                        "제품명": r["product_name"] or "",
                        "바코드명": r["barcode"] or "",
                        "등록일자": r["reg_date"] or "",
                        "성분명": r["harmful_ingredient"] or "",
                        "제조사명": r["manufacturer"] or "",
                        "제조국가명": r["country"] or "",
                        "통관보류사유내용": r["block_reason"] or "",
                        "원본이미지URL": r["original_img_url"] or "",
                        "저장된이미지경로": r["local_img_path"] or "",
                        "정보출처": r["source"] or "식품안전나라 공식 Open API"
                    })

                self.records = records
                self._build_indexes()
                self.initialized = True
                print(f"[SUCCESS] 자체 SQLite DB 로드 완료: 총 {len(self.records)}건 색인화 (경로: {self.db_path})")

        except Exception as e:
            print(f"[ERROR] SQLite DB 로드 실패: {e}")
            self.records = []
            self.initialized = True

    def _build_indexes(self):
        """고속 조회를 위한 인덱스 생성"""
        self.barcode_map = {}
        self.seq_map = {}
        self.harmful_ingredients_set = set()

        for rec in self.records:
            seq = rec.get("등록번호", "")
            barcode = rec.get("바코드명", "")
            ingr = rec.get("성분명", "")

            if seq:
                self.seq_map[seq] = rec
            if barcode and barcode.isdigit() and len(barcode) >= 8:
                self.barcode_map[barcode] = rec

            # 위해 성분 토큰 추출
            if ingr:
                for part in re.split(r"[,;/+]", ingr):
                    cleaned = part.strip().lower()
                    if len(cleaned) >= 3 and cleaned not in COMMON_SAFE_INGREDIENTS:
                        self.harmful_ingredients_set.add(cleaned)

    def replace_all_from_api(self, new_records: List[Dict[str, Any]]) -> int:
        """
        식품안전나라 공식 Open API에서 수집된 자료로 자체 DB 전면 갱신
        (기존 데이터를 완전히 공식 API 데이터로 교체)
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        inserted_count = 0

        with self._get_connection() as conn:
            cur = conn.cursor()
            
            # 1. 기존 데이터 테이블 초기화 (공식 API 데이터만 유지하기 위함)
            cur.execute("DELETE FROM harmful_products")

            # 2. 일괄 벌크 삽입
            insert_sql = """
                INSERT OR REPLACE INTO harmful_products (
                    seq, product_name, barcode, reg_date, harmful_ingredient,
                    manufacturer, country, block_reason, original_img_url,
                    local_img_path, source, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            batch_data = []
            for r in new_records:
                seq = str(r.get("등록번호", "")).strip()
                if not seq:
                    continue
                pname = str(r.get("제품명", "")).strip()
                bcode = str(r.get("바코드명", "")).strip()
                rdate = str(r.get("등록일자", "")).strip()
                ingr = str(r.get("성분명", "")).strip()
                mufc = str(r.get("제조사명", "")).strip()
                cntry = str(r.get("제조국가명", "")).strip()
                reason = str(r.get("통관보류사유내용", "")).strip()
                orig_img = str(r.get("원본이미지URL", "")).strip()
                local_img = str(r.get("저장된이미지경로", "")).strip()
                source = str(r.get("정보출처", "식품안전나라 공식 Open API(I2715)")).strip()

                batch_data.append((
                    seq, pname, bcode, rdate, ingr, mufc, cntry, reason,
                    orig_img, local_img, source, now_str
                ))

            cur.executemany(insert_sql, batch_data)
            inserted_count = len(batch_data)

            # 3. 메타데이터 업데이트
            cur.execute("INSERT OR REPLACE INTO db_meta (key, value) VALUES ('last_sync_time', ?)", (now_str,))
            cur.execute("INSERT OR REPLACE INTO db_meta (key, value) VALUES ('total_records', ?)", (str(inserted_count),))
            cur.execute("INSERT OR REPLACE INTO db_meta (key, value) VALUES ('data_source', ?)", ("식품안전나라 공식 Open API (I2715)",))
            conn.commit()

        self.last_sync_time = now_str

        # 4. 메모리 캐시 및 인덱스 재구축
        self.load_database()

        # 5. 보조 JSON 백업 캐시 갱신
        try:
            with open(LOCAL_DB_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(self.records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARNING] 보조 JSON 캐시 저장 실패: {e}")

        print(f"[SUCCESS] 식품안전나라 공식 API 자료로 자체 DB 갱신 완료: 총 {inserted_count}건 저장")
        return inserted_count

    def merge_records(self, new_records: List[Dict[str, Any]]) -> int:
        """새로 수집된 API 레코드를 자체 SQLite DB에 증분 저장 및 병합"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        added_count = 0

        with self._get_connection() as conn:
            cur = conn.cursor()
            insert_sql = """
                INSERT OR REPLACE INTO harmful_products (
                    seq, product_name, barcode, reg_date, harmful_ingredient,
                    manufacturer, country, block_reason, original_img_url,
                    local_img_path, source, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            batch_data = []
            for r in new_records:
                seq = str(r.get("등록번호", "")).strip()
                if not seq:
                    continue
                batch_data.append((
                    seq,
                    str(r.get("제품명", "")).strip(),
                    str(r.get("바코드명", "")).strip(),
                    str(r.get("등록일자", "")).strip(),
                    str(r.get("성분명", "")).strip(),
                    str(r.get("제조사명", "")).strip(),
                    str(r.get("제조국가명", "")).strip(),
                    str(r.get("통관보류사유내용", "")).strip(),
                    str(r.get("원본이미지URL", "")).strip(),
                    str(r.get("저장된이미지경로", "")).strip(),
                    str(r.get("정보출처", "식품안전나라 공식 Open API(I2715)")).strip(),
                    now_str
                ))

            cur.executemany(insert_sql, batch_data)
            added_count = len(batch_data)
            cur.execute("INSERT OR REPLACE INTO db_meta (key, value) VALUES ('last_sync_time', ?)", (now_str,))
            conn.commit()

        # 메모리 갱신
        self.load_database()
        return added_count

    def get_stats(self) -> Dict[str, Any]:
        """데이터베이스 통계 및 메타정보"""
        return {
            "total_records": len(self.records),
            "total_barcodes": len(self.barcode_map),
            "total_harmful_ingredients": len(self.harmful_ingredients_set),
            "db_type": "자체 SQLite DB (식품안전나라 공식 API 전용)",
            "db_file": str(self.db_path),
            "last_sync_time": self.last_sync_time or "동기화 이력 없음",
            "has_local_images": Path(PRODUCT_IMAGE_DIR).exists() and len(os.listdir(PRODUCT_IMAGE_DIR)) > 0
        }

    def search(self, query: str = "", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """목록 검색 및 페이징"""
        if not query:
            filtered = self.records
        else:
            norm_q = normalize_text(query)
            filtered = []
            for rec in self.records:
                target = f"{rec.get('제품명','')} {rec.get('성분명','')} {rec.get('제조사명','')} {rec.get('제조국가명','')} {rec.get('등록번호','')} {rec.get('바코드명','')}"
                if norm_q in normalize_text(target):
                    filtered.append(rec)

        total = len(filtered)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        items = filtered[start_idx:end_idx]

        # 이미지 경로 보정
        for item in items:
            item["로컬이미지존재"] = self._check_image_exists(item)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items
        }

    def _check_image_exists(self, record: Dict[str, Any]) -> bool:
        """해당 레코드의 로컬 사진 파일 존재 여부 확인"""
        seq = record.get("등록번호", "")
        if seq:
            candidate1 = PRODUCT_IMAGE_DIR / f"img_{seq}.jpg"
            candidate2 = PRODUCT_IMAGE_DIR / f"{seq}.jpg"
            if candidate1.exists() or candidate2.exists():
                return True
        local_path = record.get("저장된이미지경로", "")
        if local_path and Path(local_path).exists():
            return True
        return False

    def get_image_path_or_url(self, record: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """로컬 이미지 파일 경로 또는 원본 이미지 URL 반환 (local_file, remote_url)"""
        seq = record.get("등록번호", "")
        if seq:
            c1 = PRODUCT_IMAGE_DIR / f"img_{seq}.jpg"
            c2 = PRODUCT_IMAGE_DIR / f"{seq}.jpg"
            if c1.exists():
                return str(c1), record.get("원본이미지URL", "")
            if c2.exists():
                return str(c2), record.get("원본이미지URL", "")

        local_p = record.get("저장된이미지경로", "")
        if local_p and Path(local_p).exists():
            return str(local_p), record.get("원본이미지URL", "")

        return None, record.get("원본이미지URL", "")

    def match_product(self, ocr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        AI 분석 결과(제품명, 바코드, 성분 등)를 자체 DB와 대조하여 대국민 판정 생성
        - 1) 반입 가능 여부: 반입 금지(DANGER) / 반입 주의(WARNING) / 반입 가능(PASS)
        - 2) 왜 반입이 안 되는지: 위해성분 부작용, 건강 위험성, 법적 근거
        - 3) 국민 행동 요령: 구매 취소 방법, 세관 폐기 안내, 대체 방안
        """
        detected_barcode = str(ocr_data.get("barcode", "") or "").strip()
        detected_name = str(ocr_data.get("product_name", "") or "").strip()
        detected_brand = str(ocr_data.get("brand", "") or "").strip()
        detected_category = str(ocr_data.get("category", "해외 의약품/건강식품") or "해외 의약품/건강식품").strip()
        
        detected_ingredients = ocr_data.get("ingredients", [])
        if isinstance(detected_ingredients, str):
            detected_ingredients = [x.strip() for x in detected_ingredients.split(",") if x.strip()]

        harmful_suspects = ocr_data.get("harmful_suspects", [])
        ai_why = str(ocr_data.get("why_prohibited_reason", "") or "").strip()
        ai_health = str(ocr_data.get("health_risks", "") or "").strip()
        ai_advice = str(ocr_data.get("customs_advice", "") or "").strip()

        norm_name = normalize_text(detected_name)

        # -------------------------------------------------------------
        # 1단계: 바코드 100% 완전 일치 (위해식품/불법약품 확정)
        # -------------------------------------------------------------
        if detected_barcode and detected_barcode in self.barcode_map:
            matched_rec = self.barcode_map[detected_barcode]
            local_img, remote_url = self.get_image_path_or_url(matched_rec)
            ingr_info = get_ingredient_explanation(matched_rec.get("성분명", ""))
            
            why_text = ingr_info.get("why_prohibited") or f"식품안전나라에 차단 등록된 위해성분({matched_rec.get('성분명')})이 함유되어 있습니다."
            risks_text = ingr_info.get("health_risks") or "인체 안전성이 검증되지 않아 복용 시 심각한 부작용 위험이 있습니다."

            return {
                "status": "DANGER",
                "verdict": "반입 금지 (통관 차단·폐기 대상)",
                "confidence": 99.0,
                "citizen_summary": {
                    "is_safe": False,
                    "can_import": "불가 (전량 폐기)",
                    "badge_type": "danger",
                    "badge_text": "🚫 국내 반입 불가 (폐기 대상)",
                    "headline": f"이 약품/식품은 식품안전나라 해외직구 차단 품목으로 확인되었습니다!",
                    "why_prohibited": why_text,
                    "health_risks": risks_text,
                    "legal_basis": ingr_info.get("legal_basis", "관세법 제234조 및 식품위생법 제7조"),
                    "action_guide": "구매 전이라면 즉시 결제를 취소하시고, 이미 배송 중이라면 세관 통관 전 반품하거나 통관 시 폐기 요청을 하셔야 합니다. (반복 반입 시 과태료 부과 가능)",
                    "customs_rule": "해외직구 의약품/건강식품은 자가사용 기준(최대 6병 이하)이라 하더라도 유해성분 함유 시 1병도 통관되지 않고 전량 폐기됩니다."
                },
                "match_reason": f"제품 바코드 [{detected_barcode}]가 정부 차단 DB와 100% 일치합니다.",
                "match_stage": "1순위 바코드 일치",
                "record": matched_rec,
                "db_product_name": matched_rec.get("제품명"),
                "db_harmful_ingredient": matched_rec.get("성분명"),
                "db_reason": matched_rec.get("통관보류사유내용") or "해외직구 위해식품 차단",
                "db_local_image": local_img,
                "db_remote_image_url": remote_url,
                "ocr_data": ocr_data
            }

        # -------------------------------------------------------------
        # 2단계: 제품명 유사도 매칭 (차단 DB 등록 제품)
        # -------------------------------------------------------------
        best_match = None
        best_ratio = 0.0

        if norm_name:
            for rec in self.records:
                db_name = rec.get("제품명", "")
                norm_db = normalize_text(db_name)
                if not norm_db:
                    continue

                # 완전 일치
                if norm_name == norm_db:
                    best_match = rec
                    best_ratio = 1.0
                    break

                # 문자열 유사도
                seq_ratio = difflib.SequenceMatcher(None, norm_name, norm_db).ratio()
                
                # 토큰(단어) 집합 일치 검사 (최소 2단어 이상이고 모든 단어가 포함될 때만)
                words_detected = [w for w in norm_name.split() if len(w) >= 3]
                words_db = [w for w in norm_db.split() if len(w) >= 3]
                
                token_ratio = 0.0
                if len(words_db) >= 2 and set(words_db).issubset(set(words_detected)):
                    token_ratio = 0.88
                elif len(words_detected) >= 2 and set(words_detected).issubset(set(words_db)):
                    token_ratio = 0.88

                ratio = max(seq_ratio, token_ratio)

                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = rec

        if best_match and best_ratio >= 0.78:
            local_img, remote_url = self.get_image_path_or_url(best_match)
            ingr_info = get_ingredient_explanation(best_match.get("성분명", ""))
            
            why_text = ingr_info.get("why_prohibited") or f"식약처 차단 위해성분({best_match.get('성분명')}) 함유로 공식 수입금지된 제품과 {round(best_ratio * 100, 1)}% 일치합니다."
            risks_text = ingr_info.get("health_risks") or "복용 시 건강을 해칠 수 있는 유해 물질이 검출된 이력이 있습니다."

            is_danger = best_ratio >= 0.85
            return {
                "status": "DANGER" if is_danger else "WARNING",
                "verdict": "반입 금지 (위해식품 일치)" if is_danger else "반입 주의 (차단 제품과 매우 유사)",
                "confidence": round(best_ratio * 100, 1),
                "citizen_summary": {
                    "is_safe": False,
                    "can_import": "불가 (폐기 대상)" if is_danger else "정밀 확인 필요",
                    "badge_type": "danger" if is_danger else "warning",
                    "badge_text": "🚫 국내 반입 불가 (폐기 대상)" if is_danger else "⚠️ 반입 주의 (차단 품목 의심)",
                    "headline": f"공식 해외직구 차단 제품 [{best_match.get('제품명')}]과 일치합니다!",
                    "why_prohibited": why_text,
                    "health_risks": risks_text,
                    "legal_basis": ingr_info.get("legal_basis", "수입식품안전관리 특별법 제25조"),
                    "action_guide": "이 제품은 세관 X-ray 및 정밀 검사 시 통관 보류 및 폐기 처분 대상입니다. 구매를 중단하시고 국내 정식 수입 통관된 안전한 대체품을 권장합니다.",
                    "customs_rule": "해외 사이트에서 쉽게 구매할 수 있어도 국내 안전 기준을 통과하지 못한 위해물품은 통관이 일절 불허됩니다."
                },
                "match_reason": f"정부 차단 DB의 [{best_match.get('제품명')}]과 {round(best_ratio * 100, 1)}% 일치",
                "match_stage": "2순위 제품명 매칭",
                "record": best_match,
                "db_product_name": best_match.get("제품명"),
                "db_harmful_ingredient": best_match.get("성분명"),
                "db_reason": best_match.get("통관보류사유내용") or "식품안전나라 차단 원료 함유",
                "db_local_image": local_img,
                "db_remote_image_url": remote_url,
                "ocr_data": ocr_data
            }

        # -------------------------------------------------------------
        # 3단계: 성분표 내 정부 지정 위해성분 검출
        # -------------------------------------------------------------
        detected_harmful_list = []
        for ingr in detected_ingredients:
            clean_i = normalize_text(ingr)
            if not clean_i or clean_i in COMMON_SAFE_INGREDIENTS or len(clean_i) < 3:
                continue
            for h_ingr in self.harmful_ingredients_set:
                if clean_i in h_ingr or h_ingr in clean_i:
                    detected_harmful_list.append(h_ingr)
                    break

        if detected_harmful_list:
            sample_rec = None
            sample_ingr = detected_harmful_list[0]
            for rec in self.records:
                if sample_ingr in normalize_text(rec.get("성분명", "")):
                    sample_rec = rec
                    break

            local_img, remote_url = (self.get_image_path_or_url(sample_rec) if sample_rec else (None, None))
            ingr_info = get_ingredient_explanation(sample_ingr)

            return {
                "status": "DANGER",
                "verdict": "반입 금지 (반입차단 위해성분 검출)",
                "confidence": 88.0,
                "citizen_summary": {
                    "is_safe": False,
                    "can_import": "불가 (차단 성분 검출)",
                    "badge_type": "danger",
                    "badge_text": "🚫 국내 반입 불가 (금지 성분 함유)",
                    "headline": f"약 라벨에서 해외직구 반입금지 성분 [{sample_ingr}]이 발견되었습니다!",
                    "why_prohibited": ingr_info.get("why_prohibited", f"해당 성분({sample_ingr})은 인체 위해 우려로 식약처에서 반입을 차단한 원료입니다."),
                    "health_risks": ingr_info.get("health_risks", "복용 시 심장, 간, 신경계에 예기치 못한 부작용을 일으킬 수 있습니다."),
                    "legal_basis": ingr_info.get("legal_basis", "식약처 고시 해외직구 차단 원료 목록"),
                    "action_guide": "성분표에 표시된 금지 성분으로 인해 통관 과정에서 전량 폐기됩니다. 판매처에 환불을 요청하세요.",
                    "customs_rule": "성분표에 반입금지 원료가 기재되어 있는 경우, 포장 개봉 여부와 관계없이 통관이 보류됩니다."
                },
                "match_reason": f"성분표 분석 결과 차단 성분 검출: {', '.join(detected_harmful_list[:3])}",
                "match_stage": "3순위 위해성분 검출",
                "record": sample_rec,
                "db_product_name": sample_rec.get("제품명") if sample_rec else "성분 일치 차단제품 다수",
                "db_harmful_ingredient": ", ".join(detected_harmful_list),
                "db_reason": "식품안전나라 해외직구 차단 원료 함유",
                "db_local_image": local_img,
                "db_remote_image_url": remote_url,
                "ocr_data": ocr_data
            }

        # -------------------------------------------------------------
        # 4단계: Gemini AI가 의심/제한 성분(멜라토닌 등)을 감지한 경우
        # -------------------------------------------------------------
        if harmful_suspects or ocr_data.get("is_prohibited_suspect"):
            suspect_names = ", ".join(harmful_suspects) if harmful_suspects else "처방 필요 의약품 성분"
            first_suspect = harmful_suspects[0] if harmful_suspects else ""
            ingr_info = get_ingredient_explanation(first_suspect) if first_suspect else {}

            why_text = ai_why or ingr_info.get("why_prohibited") or f"라벨에서 주의/차단 대상 성분({suspect_names})이 확인되었습니다."
            risks_text = ai_health or ingr_info.get("health_risks") or "국내 의사 처방전이 필요하거나 오남용 시 부작용 우려가 있습니다."

            return {
                "status": "WARNING",
                "verdict": "반입 주의 (처방전 필요 또는 반입 제한 성분)",
                "confidence": 80.0,
                "citizen_summary": {
                    "is_safe": False,
                    "can_import": "조건부 가능 또는 확인 필요",
                    "badge_type": "warning",
                    "badge_text": "⚠️ 반입 주의 (처방전/소견서 필요)",
                    "headline": f"국내에서 처방전이 필요하거나 반입이 제한되는 성분 [{suspect_names}] 감지!",
                    "why_prohibited": why_text,
                    "health_risks": risks_text,
                    "legal_basis": ingr_info.get("legal_basis", "약사법 및 관세청 자가사용 인정기준"),
                    "action_guide": ai_advice or "멜라토닌 등 국내 전문의약품 성분의 경우 의사 처방전이 있어야 통관이 가능합니다. 처방전이 없다면 통관이 보류될 수 있습니다.",
                    "customs_rule": "의약품은 원칙적으로 자가사용 목적 6병 이내까지만 가능하며, 오남용 우려 의약품은 처방전 제출이 의무화되어 있습니다."
                },
                "match_reason": f"AI 비전 라벨 판독 결과 주의 성분 감지: {suspect_names}",
                "match_stage": "4순위 AI 성분 주의 판정",
                "record": None,
                "db_product_name": None,
                "db_harmful_ingredient": suspect_names,
                "db_reason": why_text,
                "db_local_image": None,
                "db_remote_image_url": None,
                "ocr_data": ocr_data
            }

        # -------------------------------------------------------------
        # 5단계: 불일치 / 정상 물품 (안심 반입 가능)
        # -------------------------------------------------------------
        return {
            "status": "PASS",
            "verdict": "반입 가능 (정상 물품)",
            "confidence": 95.0,
            "citizen_summary": {
                "is_safe": True,
                "can_import": "가능 (자가사용 기준 준수 시)",
                "badge_type": "success",
                "badge_text": "✅ 국내 반입 가능 (안전)",
                "headline": "식품안전나라 해외직구 차단 DB에 등록되지 않은 정상 물품입니다.",
                "why_prohibited": "위해성분이나 불법의약품 성분이 검출되지 않았으며, 현재 차단 목록에 포함되어 있지 않습니다.",
                "health_risks": "알려진 치명적 위해성분 없음 (단, 제품 라벨의 일일 권장 섭취량을 준수하세요)",
                "legal_basis": "관세법 소액물품 면세 및 자가사용 통관 기준",
                "action_guide": "안심하고 통관하셔도 좋습니다. 단, 자가사용 인정 수량(총 6병 이하)과 면세 한도(총 결제금액 미화 150달러 이하, 미국발 200달러)를 지켜주세요.",
                "customs_rule": "건강기능식품 및 일반의약품의 해외직구 자가사용 허용 수량은 1인당 최대 6병(용기)까지입니다."
            },
            "match_reason": "식품안전나라 차단 DB 및 성분 분석 결과 반입 제한 요소가 없습니다.",
            "match_stage": "정상 판정",
            "record": None,
            "db_product_name": None,
            "db_harmful_ingredient": None,
            "db_reason": "특이사항 없음 (통관 적합)",
            "db_local_image": None,
            "db_remote_image_url": None,
            "ocr_data": ocr_data
        }

db_service = DatabaseService()

