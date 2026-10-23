import os
import re
import json
import difflib
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from config import DB_EXCEL_PATH, LOCAL_DB_JSON_PATH, PRODUCT_IMAGE_DIR

# 단독으로 위험 성분으로 판정하면 안 되는 일반적인 성분 목록
COMMON_SAFE_INGREDIENTS = {
    "water", "purified water", "aqua", "gelatin", "glycerin", "sugar",
    "caffeine", "salt", "sodium", "calcium", "magnesium", "vitamin",
    "vitamin c", "vitamin d", "zinc", "iron", "potassium", "물", "정제수",
    "젤라틴", "글리세린", "비타민", "카페인", "소금", "칼슘", "마그네슘"
}

def normalize_text(text: str) -> str:
    """텍스트 정규화: 소문자화, 특수문자 제거, 공백 축소"""
    if not text or pd.isna(text):
        return ""
    text = str(text).lower()
    text = re.sub(r"[^a-zA-Z0-9가-힣]", " ", text)
    return " ".join(text.split())

class DatabaseService:
    def __init__(self):
        self.records: List[Dict[str, Any]] = []
        self.barcode_map: Dict[str, Dict[str, Any]] = {}
        self.seq_map: Dict[str, Dict[str, Any]] = {}
        self.harmful_ingredients_set: set = set()
        self.initialized = False
        self.load_database()

    def load_database(self):
        """기존 엑셀 또는 캐시 파일로부터 DB 로드"""
        # 1. 엑셀 파일 로드 시도
        if DB_EXCEL_PATH and Path(DB_EXCEL_PATH).exists():
            try:
                print(f"📂 엑셀 DB 로드 중: {DB_EXCEL_PATH}")
                df = pd.read_excel(DB_EXCEL_PATH)
                df = df.fillna("")
                
                records = []
                for _, row in df.iterrows():
                    rec = {
                        "등록번호": str(row.get("등록번호", "")).strip(),
                        "제품명": str(row.get("제품명", "")).strip(),
                        "바코드명": str(row.get("바코드명", "")).strip(),
                        "등록일자": str(row.get("등록일자", "")).strip(),
                        "성분명": str(row.get("성분명", "")).strip(),
                        "제조사명": str(row.get("제조사명", "")).strip(),
                        "제조국가명": str(row.get("제조국가명", "")).strip(),
                        "통관보류사유내용": str(row.get("통관보류사유내용", "")).strip(),
                        "원본이미지URL": str(row.get("원본이미지URL", "")).strip(),
                        "저장된이미지경로": str(row.get("저장된이미지경로", "")).strip(),
                        "정보출처": str(row.get("정보출처", "식약처/관세청 DB")).strip(),
                    }
                    records.append(rec)
                
                self.records = records
                self._build_indexes()
                self.initialized = True
                print(f"✅ DB 로드 완료: 총 {len(self.records)}건 색인화")
                return
            except Exception as e:
                print(f"🚨 엑셀 DB 로드 실패: {e}")

        # 2. 캐시 JSON 로드 시도
        if LOCAL_DB_JSON_PATH.exists():
            try:
                with open(LOCAL_DB_JSON_PATH, "r", encoding="utf-8") as f:
                    self.records = json.load(f)
                self._build_indexes()
                self.initialized = True
                print(f"✅ 캐시 JSON DB 로드 완료: 총 {len(self.records)}건")
                return
            except Exception as e:
                print(f"🚨 캐시 JSON 로드 실패: {e}")

        # 3. 기본 빈 데이터셋
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

    def get_stats(self) -> Dict[str, Any]:
        """데이터베이스 통계"""
        return {
            "total_records": len(self.records),
            "total_barcodes": len(self.barcode_map),
            "total_harmful_ingredients": len(self.harmful_ingredients_set),
            "has_local_images": Path(PRODUCT_IMAGE_DIR).exists() and len(os.listdir(PRODUCT_IMAGE_DIR)) > 0,
            "excel_loaded": DB_EXCEL_PATH is not None and Path(DB_EXCEL_PATH).exists()
        }

    def search(self, query: str = "", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """목록 검색 및 페이징"""
        if not query:
            filtered = self.records
        else:
            norm_q = normalize_text(query)
            filtered = []
            for rec in self.records:
                target = f"{rec.get('제품명','')} {rec.get('성분명','')} {rec.get('제조사명','')} {rec.get('등록번호','')} {rec.get('바코드명','')}"
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

    def merge_records(self, new_records: List[Dict[str, Any]]) -> int:
        """새로 수집된 API 레코드를 기존 DB와 병합"""
        added_count = 0
        for rec in new_records:
            seq = rec.get("등록번호", "")
            if seq and seq not in self.seq_map:
                self.records.insert(0, rec)
                self.seq_map[seq] = rec
                barcode = rec.get("바코드명", "")
                if barcode and barcode.isdigit() and len(barcode) >= 8:
                    self.barcode_map[barcode] = rec
                added_count += 1
            elif not seq:
                self.records.insert(0, rec)
                added_count += 1

        if added_count > 0:
            self._build_indexes()
            # 캐시 JSON 저장
            try:
                with open(LOCAL_DB_JSON_PATH, "w", encoding="utf-8") as f:
                    json.dump(self.records[:10000], f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"캐시 저장 실패: {e}")

        return added_count

    def match_product(self, ocr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        AI 분석 결과(제품명, 바코드, 성분 등)를 DB와 3단계 정밀 비교
        - 1단계: 유효한 바코드 완전 일치
        - 2단계: 제품명 정규화 완전 일치 및 유사도(0.7 이상)
        - 3단계: 성분표 텍스트 내 식약처/관세청 지정 위해성분 검출
        """
        detected_barcode = str(ocr_data.get("barcode", "") or "").strip()
        detected_name = str(ocr_data.get("product_name", "") or "").strip()
        detected_brand = str(ocr_data.get("brand", "") or "").strip()
        detected_ingredients = ocr_data.get("ingredients", [])
        if isinstance(detected_ingredients, str):
            detected_ingredients = [x.strip() for x in detected_ingredients.split(",") if x.strip()]

        norm_name = normalize_text(detected_name)
        norm_brand = normalize_text(detected_brand)

        # 1단계: 바코드 일치
        if detected_barcode and detected_barcode in self.barcode_map:
            matched_rec = self.barcode_map[detected_barcode]
            local_img, remote_url = self.get_image_path_or_url(matched_rec)
            return {
                "status": "DANGER",
                "verdict": "통관보류 (위해물품 확정)",
                "confidence": 99.0,
                "match_reason": f"바코드 [{detected_barcode}] 100% 완전 일치",
                "match_stage": "1순위 바코드 일치",
                "record": matched_rec,
                "db_product_name": matched_rec.get("제품명"),
                "db_harmful_ingredient": matched_rec.get("성분명"),
                "db_reason": matched_rec.get("통관보류사유내용") or "위해성분 검출 차단",
                "db_local_image": local_img,
                "db_remote_image_url": remote_url,
                "ocr_data": ocr_data
            }

        # 2단계: 제품명 유사도 매칭
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

                # 부분 포함 (길이 5글자 이상)
                if len(norm_name) >= 5 and (norm_name in norm_db or norm_db in norm_name):
                    ratio = 0.88
                else:
                    ratio = difflib.SequenceMatcher(None, norm_name, norm_db).ratio()

                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = rec

        if best_match and best_ratio >= 0.75:
            local_img, remote_url = self.get_image_path_or_url(best_match)
            return {
                "status": "DANGER" if best_ratio >= 0.85 else "WARNING",
                "verdict": "통관보류 (위해식품 일치)" if best_ratio >= 0.85 else "주의 (위해식품 유사도 높음)",
                "confidence": round(best_ratio * 100, 1),
                "match_reason": f"DB 등록 제품명과 {round(best_ratio * 100, 1)}% 일치",
                "match_stage": "2순위 제품명 매칭",
                "record": best_match,
                "db_product_name": best_match.get("제품명"),
                "db_harmful_ingredient": best_match.get("성분명"),
                "db_reason": best_match.get("통관보류사유내용") or "지정 위해성분 검출",
                "db_local_image": local_img,
                "db_remote_image_url": remote_url,
                "ocr_data": ocr_data
            }

        # 3단계: 위해 성분 검출
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
            # 위해성분을 포함한 대표 DB 레코드 하나 탐색
            sample_rec = None
            sample_ingr = detected_harmful_list[0]
            for rec in self.records:
                if sample_ingr in normalize_text(rec.get("성분명", "")):
                    sample_rec = rec
                    break

            local_img, remote_url = (self.get_image_path_or_url(sample_rec) if sample_rec else (None, None))

            return {
                "status": "WARNING",
                "verdict": "주의 (반입금지 위해성분 검출)",
                "confidence": 85.0,
                "match_reason": f"성분표에서 차단 대상 위해성분 검출: {', '.join(detected_harmful_list[:3])}",
                "match_stage": "3순위 위해성분 검출",
                "record": sample_rec,
                "db_product_name": sample_rec.get("제품명") if sample_rec else "성분 일치 제품 다수",
                "db_harmful_ingredient": ", ".join(detected_harmful_list),
                "db_reason": "관세청/식약처 해외직구 반입금지 위해성분 함유",
                "db_local_image": local_img,
                "db_remote_image_url": remote_url,
                "ocr_data": ocr_data
            }

        # 불일치 / 정상
        return {
            "status": "PASS",
            "verdict": "정상 (위해DB 미검출)",
            "confidence": 95.0,
            "match_reason": "현재 차단된 위해식품/의약품 DB와 일치하는 항목이 없습니다.",
            "match_stage": "정상 판정",
            "record": None,
            "db_product_name": None,
            "db_harmful_ingredient": None,
            "db_reason": "특이사항 없음",
            "db_local_image": None,
            "db_remote_image_url": None,
            "ocr_data": ocr_data
        }

db_service = DatabaseService()
