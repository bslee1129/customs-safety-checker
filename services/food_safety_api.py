import os
import requests
import urllib3
from typing import Dict, Any, List, Optional
from pathlib import Path
from config import FOOD_SAFETY_API_KEY, FOOD_SAFETY_SERVICE_ID, PRODUCT_IMAGE_DIR

class FoodSafetyApiService:
    def __init__(self, api_key: str = FOOD_SAFETY_API_KEY, service_id: str = FOOD_SAFETY_SERVICE_ID):
        self.api_key = api_key
        self.service_id = service_id
        self.base_url = f"http://openapi.foodsafetykorea.go.kr/api/{self.api_key}/{self.service_id}/json"

    def get_status(self) -> Dict[str, Any]:
        """식품안전나라 API 상태 및 총 데이터 건수 조회"""
        try:
            url = f"{self.base_url}/1/1"
            response = requests.get(url, timeout=7)
            if response.status_code != 200:
                return {
                    "connected": False,
                    "error": f"HTTP 오류 {response.status_code}",
                    "total_count": 0
                }
            
            data = response.json()
            if self.service_id not in data:
                # 에러 응답인 경우 (예: 인증키 오류)
                result_code = data.get("RESULT", {}).get("CODE", "UNKNOWN")
                result_msg = data.get("RESULT", {}).get("MSG", "API 키 또는 서비스 확인 필요")
                return {
                    "connected": False,
                    "error": f"[{result_code}] {result_msg}",
                    "total_count": 0
                }
            
            total_count = int(data[self.service_id].get("total_count", 0))
            return {
                "connected": True,
                "total_count": total_count,
                "service_id": self.service_id,
                "api_endpoint": self.base_url
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "total_count": 0
            }

    def fetch_records(self, start: int = 1, end: int = 50, download_images: bool = False) -> Dict[str, Any]:
        """지정 구간 데이터 수집"""
        try:
            url = f"{self.base_url}/{start}/{end}"
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}", "rows": []}

            data = response.json()
            if self.service_id not in data:
                return {"success": False, "error": "응답에 서비스 데이터가 없습니다.", "rows": []}

            service_data = data[self.service_id]
            raw_rows = service_data.get("row", [])
            total_count = int(service_data.get("total_count", 0))

            normalized_rows = []
            for item in raw_rows:
                seq = str(item.get("SELF_IMPORT_SEQ", "") or item.get("PRCS_SE", "")).strip()
                prdt_nm = str(item.get("PRDT_NM", "")).strip()
                ingr_nm = str(item.get("INGR_NM_LST", "") or item.get("HARMFUL_INGR_LST", "")).strip()
                mufc_nm = str(item.get("MUFC_NM", "")).strip()
                country = str(item.get("MUFC_CNTRY_NM", "")).strip()
                barcode = str(item.get("BARCD_CTN", "") or item.get("BARCODE", "") or item.get("BAR_CD", "")).strip()
                reg_date = str(item.get("CRET_DTM", "") or item.get("CRET_DT", "") or item.get("LAST_UPDT_DTM", "")).strip()
                img_url_raw = str(item.get("IMAGE_URL", "") or item.get("FILE_URL", "")).strip()
                
                # 이미지 URL이 여러 개(쉼표 분리)일 경우 첫 번째 유효 URL 선택
                img_url = ""
                if img_url_raw:
                    urls = [u.strip() for u in img_url_raw.split(",") if u.strip().startswith("http")]
                    img_url = urls[0] if urls else img_url_raw

                local_img = ""
                # 이미지 다운로드 요청 시 처리
                if download_images and img_url and seq:
                    try:
                        dest = PRODUCT_IMAGE_DIR / f"img_{seq}.jpg"
                        if not dest.exists():
                            img_res = requests.get(img_url, timeout=5)
                            if img_res.status_code == 200:
                                dest.write_bytes(img_res.content)
                                local_img = str(dest)
                        else:
                            local_img = str(dest)
                    except Exception:
                        pass

                normalized_rows.append({
                    "등록번호": seq,
                    "제품명": prdt_nm,
                    "바코드명": barcode,
                    "등록일자": reg_date,
                    "성분명": ingr_nm,
                    "제조사명": mufc_nm,
                    "제조국가명": country,
                    "통관보류사유내용": f"{ingr_nm} 검출 (식품안전나라 해외직구 차단)" if ingr_nm else "식품안전나라 해외직구 위해식품 차단",
                    "원본이미지URL": img_url,
                    "저장된이미지경로": local_img,
                    "정보출처": "식품안전나라 공식 Open API(I2715)"
                })

            return {
                "success": True,
                "total_count": total_count,
                "count": len(normalized_rows),
                "start": start,
                "end": end,
                "rows": normalized_rows
            }
        except Exception as e:
            return {"success": False, "error": str(e), "rows": []}

    def fetch_all_records(self, batch_size: int = 1000) -> Dict[str, Any]:
        """식품안전나라 API 서버의 전체 데이터(5,000+건)를 일괄 수집"""
        status = self.get_status()
        if not status.get("connected"):
            return {"success": False, "error": f"API 연결 실패: {status.get('error')}", "rows": []}

        total_count = status.get("total_count", 0)
        print(f"[INFO] 식품안전나라 API 전체 데이터 수집 시작 (총 {total_count}건, {batch_size}건 단위 호출)...")

        all_rows = []
        for start in range(1, total_count + 1, batch_size):
            end = min(start + batch_size - 1, total_count)
            print(f"[INFO] 구간 수집 중: {start} ~ {end} ...")
            res = self.fetch_records(start=start, end=end, download_images=False)
            if res.get("success"):
                all_rows.extend(res.get("rows", []))
            else:
                print(f"[WARNING] 구간 {start}~{end} 수집 실패: {res.get('error')}")

        print(f"[SUCCESS] 식품안전나라 API 전체 데이터 수집 완료: 총 {len(all_rows)}건 확보")
        return {
            "success": True,
            "total_count": total_count,
            "count": len(all_rows),
            "rows": all_rows
        }

food_safety_api = FoodSafetyApiService()

