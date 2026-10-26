import os
import requests
from typing import Dict, Any, List, Optional
from config import SAFETYKOREA_API_KEY

class SafetyKoreaApi:
    """
    국가기술표준원 SafetyKorea 제품안전정보 Open API 클라이언트
    (KC인증정보, 국내리콜정보, 국외리콜정보, 해외직구 안전성조사결과)
    """
    BASE_URL = "http://www.safetykorea.kr/openapi/api"

    def __init__(self, api_key: str = SAFETYKOREA_API_KEY):
        self.api_key = api_key or os.getenv("SAFETYKOREA_API_KEY", "")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "AuthKey": self.api_key or os.getenv("SAFETYKOREA_API_KEY", ""),
            "User-Agent": "SafetyKoreaClient/2.1"
        }

    def get_status(self) -> Dict[str, Any]:
        """SafetyKorea API 연결 상태 확인"""
        key = self.api_key or os.getenv("SAFETYKOREA_API_KEY", "")
        if not key:
            return {"connected": False, "error": "API 키가 설정되지 않았습니다."}
        try:
            url = f"{self.BASE_URL}/recall/overseasList.json"
            res = requests.get(url, headers=self._get_headers(), params={"conditionKey": "all", "conditionValue": "test"}, timeout=7)
            if res.status_code == 200:
                data = res.json()
                code = data.get("resultCode")
                if code in ("2000", "2004"):
                    return {"connected": True, "message": "정상 연결"}
                elif code == "4000":
                    return {"connected": False, "error": "유효하지 않은 AuthKey(서비스 ID)"}
                return {"connected": False, "error": f"응답 코드: {code} ({data.get('resultMsg')})"}
            return {"connected": False, "error": f"HTTP {res.status_code}"}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    # -------------------------------------------------------------
    # 1. KC 인증정보 조회
    # -------------------------------------------------------------
    def search_certifications(self, query: str, condition_key: str = "all") -> Dict[str, Any]:
        """
        KC인증정보 조회
        condition_key: all(전체), certNum(인증번호), productName(제품명), modelName(모델명), certDate(인증일자), signDate(등록일)
        """
        if not query:
            return {"success": True, "items": [], "total": 0}
        try:
            url = f"{self.BASE_URL}/cert/certificationList.json"
            params = {
                "conditionKey": condition_key,
                "conditionValue": query
            }
            res = requests.get(url, headers=self._get_headers(), params=params, timeout=12)
            if res.status_code == 200:
                data = res.json()
                if data.get("resultCode") in ("2000", 2000):
                    raw_items = data.get("resultData", [])
                    items = raw_items if isinstance(raw_items, list) else []
                    return {
                        "success": True,
                        "items": items,
                        "total": len(items)
                    }
                elif data.get("resultCode") in ("2004", 2004):
                    return {"success": True, "items": [], "total": 0}
                return {"success": False, "error": data.get("resultMsg", "조회 실패"), "items": [], "total": 0}
            return {"success": False, "error": f"HTTP {res.status_code}", "items": [], "total": 0}
        except Exception as e:
            return {"success": False, "error": str(e), "items": [], "total": 0}

    def get_certification_detail(self, cert_num: str) -> Dict[str, Any]:
        """KC인증정보 상세 조회 (사진 목록, 파생모델 등)"""
        try:
            url = f"{self.BASE_URL}/cert/certificationDetail.json"
            res = requests.get(url, headers=self._get_headers(), params={"certNum": cert_num}, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("resultCode") in ("2000", 2000):
                    return {"success": True, "data": data.get("resultData", {})}
            return {"success": False, "error": "상세정보 조회 불가", "data": None}
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    # -------------------------------------------------------------
    # 2. 국내리콜정보 조회
    # -------------------------------------------------------------
    def search_domestic_recalls(self, query: str, condition_key: str = "all") -> Dict[str, Any]:
        """
        국내리콜정보 조회
        condition_key: all(전체), barcodeNum(바코드), recallProductName(제품명), recallBrandName(상표명), recallModelName(모델명), certNum(인증번호), publishDate(공표일자)
        """
        if not query:
            return {"success": True, "items": [], "total": 0}
        try:
            url = f"{self.BASE_URL}/recall/recallList.json"
            params = {
                "conditionKey": condition_key,
                "conditionValue": query
            }
            res = requests.get(url, headers=self._get_headers(), params=params, timeout=12)
            if res.status_code == 200:
                data = res.json()
                if data.get("resultCode") in ("2000", 2000):
                    raw_items = data.get("resultData", [])
                    items = raw_items if isinstance(raw_items, list) else []
                    return {
                        "success": True,
                        "items": items,
                        "total": len(items)
                    }
                elif data.get("resultCode") in ("2004", 2004):
                    return {"success": True, "items": [], "total": 0}
                return {"success": False, "error": data.get("resultMsg", "조회 실패"), "items": [], "total": 0}
            return {"success": False, "error": f"HTTP {res.status_code}", "items": [], "total": 0}
        except Exception as e:
            return {"success": False, "error": str(e), "items": [], "total": 0}

    def get_domestic_recall_detail(self, recall_uid: str) -> Dict[str, Any]:
        """국내리콜정보 상세 조회 (리콜사진 배열 등)"""
        try:
            url = f"{self.BASE_URL}/recall/recallDetail.json"
            res = requests.get(url, headers=self._get_headers(), params={"recallUid": recall_uid}, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("resultCode") in ("2000", 2000):
                    return {"success": True, "data": data.get("resultData", {})}
            return {"success": False, "error": "상세정보 조회 불가", "data": None}
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    # -------------------------------------------------------------
    # 3. 국외리콜정보 조회
    # -------------------------------------------------------------
    def search_foreign_recalls(self, query: str, condition_key: str = "all") -> Dict[str, Any]:
        """
        국외리콜정보 조회
        condition_key: all, recallProductName, recallBrandName, recallModelName, publishDate, fRecallUid
        """
        if not query:
            return {"success": True, "items": [], "total": 0}
        try:
            url = f"{self.BASE_URL}/recall/fRecallList.json"
            params = {
                "conditionKey": condition_key,
                "conditionValue": query
            }
            res = requests.get(url, headers=self._get_headers(), params=params, timeout=12)
            if res.status_code == 200:
                data = res.json()
                if data.get("resultCode") in ("2000", 2000):
                    raw_items = data.get("resultData", [])
                    items = raw_items if isinstance(raw_items, list) else []
                    return {
                        "success": True,
                        "items": items,
                        "total": len(items)
                    }
                elif data.get("resultCode") in ("2004", 2004):
                    return {"success": True, "items": [], "total": 0}
                return {"success": False, "error": data.get("resultMsg", "조회 실패"), "items": [], "total": 0}
            return {"success": False, "error": f"HTTP {res.status_code}", "items": [], "total": 0}
        except Exception as e:
            return {"success": False, "error": str(e), "items": [], "total": 0}

    # -------------------------------------------------------------
    # 4. 해외직구 안전성조사결과 정보 조회
    # -------------------------------------------------------------
    def search_overseas_safety(self, query: str, condition_key: str = "all") -> Dict[str, Any]:
        """
        해외직구 안전성조사결과 정보 조회
        condition_key: all, productName, modelName, publishDate, overseasUid
        """
        if not query:
            return {"success": True, "items": [], "total": 0}
        try:
            url = f"{self.BASE_URL}/recall/overseasList.json"
            params = {
                "conditionKey": condition_key,
                "conditionValue": query
            }
            res = requests.get(url, headers=self._get_headers(), params=params, timeout=12)
            if res.status_code == 200:
                data = res.json()
                if data.get("resultCode") in ("2000", 2000):
                    raw_items = data.get("resultData", [])
                    items = raw_items if isinstance(raw_items, list) else []
                    return {
                        "success": True,
                        "items": items,
                        "total": len(items)
                    }
                elif data.get("resultCode") in ("2004", 2004):
                    return {"success": True, "items": [], "total": 0}
                return {"success": False, "error": data.get("resultMsg", "조회 실패"), "items": [], "total": 0}
            return {"success": False, "error": f"HTTP {res.status_code}", "items": [], "total": 0}
        except Exception as e:
            return {"success": False, "error": str(e), "items": [], "total": 0}

    # -------------------------------------------------------------
    # 5. 제품명/모델명/바코드 4대 안전정보 통합 원스톱 점검
    # -------------------------------------------------------------
    def comprehensive_check(self, product_name: str = "", model_name: str = "", barcode: str = "") -> Dict[str, Any]:
        """
        제품명, 모델명, 바코드로 4대 안전정보를 원스톱 일괄 조회하고 종합 위험도를 판정합니다.
        """
        queries = []
        if product_name and len(product_name.strip()) >= 2:
            queries.append(product_name.strip())
        if model_name and len(model_name.strip()) >= 2 and model_name.strip() not in queries:
            queries.append(model_name.strip())
        if barcode and len(barcode.strip()) >= 4:
            queries.append(barcode.strip())

        result = {
            "overseas_safety": [],     # 해외직구 안전성 부적합
            "domestic_recalls": [],    # 국내리콜
            "foreign_recalls": [],     # 국외리콜
            "certifications": [],      # KC인증
            "danger_count": 0,
            "warning_count": 0,
            "has_danger": False,
            "has_warning": False,
            "is_kc_certified": False,
            "summary_alerts": []
        }

        if not queries:
            return result

        main_query = queries[0]

        # 1) 해외직구 안전성 조사 확인
        res_os = self.search_overseas_safety(main_query)
        if res_os.get("success") and res_os.get("items"):
            result["overseas_safety"] = res_os["items"]
            result["danger_count"] += len(res_os["items"])
            result["has_danger"] = True
            first_item = res_os["items"][0]
            harm = first_item.get("harmDscr", "")
            result["summary_alerts"].append(f"🚨 해외직구 안전성조사 부적합 이력 확인: {first_item.get('productName')} ({harm[:60]}...)")

        # 2) 국내리콜정보 확인
        res_dr = self.search_domestic_recalls(main_query)
        if res_dr.get("success") and res_dr.get("items"):
            result["domestic_recalls"] = res_dr["items"]
            result["danger_count"] += len(res_dr["items"])
            result["has_danger"] = True
            first_item = res_dr["items"][0]
            result["summary_alerts"].append(f"🚨 국내 리콜 명령 대상 품목: {first_item.get('recallProductName')} (조치: {first_item.get('publishActionDscr') or '회수명령'})")

        # 3) 국외리콜정보 확인
        res_fr = self.search_foreign_recalls(main_query)
        if res_fr.get("success") and res_fr.get("items"):
            result["foreign_recalls"] = res_fr["items"]
            result["warning_count"] += len(res_fr["items"])
            result["has_warning"] = True
            first_item = res_fr["items"][0]
            cntry = first_item.get("recallPblshCntryName", "해외")
            result["summary_alerts"].append(f"⚠️ 국외({cntry}) 리콜/수입거절 이력 확인: {first_item.get('recallProductName')} (사유: {first_item.get('violateDscr', '')[:60]}...)")

        # 4) KC인증정보 확인
        res_cert = self.search_certifications(main_query)
        if res_cert.get("success") and res_cert.get("items"):
            result["certifications"] = res_cert["items"]
            valid_certs = [c for c in res_cert["items"] if c.get("certState") == "적합"]
            revoked_certs = [c for c in res_cert["items"] if c.get("certState") in ("안전인증취소", "안전확인신고 효력상실", "기간만료")]
            
            if revoked_certs:
                result["has_danger"] = True
                result["danger_count"] += len(revoked_certs)
                result["summary_alerts"].append(f"🚨 KC 인증 취소/효력상실 이력 존재: {revoked_certs[0].get('certNum')} ({revoked_certs[0].get('certState')})")
            elif valid_certs:
                result["is_kc_certified"] = True
                result["summary_alerts"].append(f"✅ 정식 KC 인증 확인: {valid_certs[0].get('certNum')} ({valid_certs[0].get('productName')})")

        return result

safetykorea_api = SafetyKoreaApi()
