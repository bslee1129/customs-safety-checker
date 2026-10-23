import os
import requests
import urllib3
from typing import Dict, Any, List, Optional
from pathlib import Path
from config import FOOD_SAFETY_API_KEY, FOOD_SAFETY_SERVICE_ID, PRODUCT_IMAGE_DIR

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class FoodSafetyApiService:
    def __init__(self, api_key: str = FOOD_SAFETY_API_KEY, service_id: str = FOOD_SAFETY_SERVICE_ID):
        self.api_key = api_key
        self.service_id = service_id
        self.base_url = f"http://openapi.foodsafetykorea.go.kr/api/{self.api_key}/{self.service_id}/json"

    def get_status(self) -> Dict[str, Any]:
        """식품안전나라 API 상태 및 총 데이터 건수 조회"""
        try:
            url = f"{self.base_url}/1/1"
            response = requests.get(url, timeout=7, verify=False)
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
            response = requests.get(url, timeout=15, verify=False)
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
                barcode = str(item.get("BARCODE", "") or item.get("BAR_CD", "")).strip()
                reg_date = str(item.get("CRET_DT", "") or item.get("LAST_UPDT_DTM", "")).strip()
                img_url = str(item.get("IMAGE_URL", "") or item.get("FILE_URL", "")).strip()

                local_img = ""
                # 이미지 다운로드 요청 시 처리
                if download_images and img_url and seq:
                    try:
                        dest = PRODUCT_IMAGE_DIR / f"img_{seq}.jpg"
                        if not dest.exists():
                            img_res = requests.get(img_url, timeout=5, verify=False)
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
                    "통관보류사유내용": f"{ingr_nm} 검출" if ingr_nm else "위해성분 검출",
                    "원본이미지URL": img_url,
                    "저장된이미지경로": local_img,
                    "정보출처": "식품안전나라(I2715)"
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

food_safety_api = FoodSafetyApiService()
