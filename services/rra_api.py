import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional

class RraApi:
    """
    과학기술정보통신부 국립전파연구원(RRA) 방송통신기자재등의 적합성평가(전자파적합등록/인증) 조회 서비스
    """
    POPUP_URL = "https://www.rra.go.kr/ko/license/A_b_popup_keyno.do"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def extract_cert_numbers(self, text: str) -> List[str]:
        """텍스트에서 전자파 적합등록/인증번호 추출 (예: R-REM-Y15-YW1801, R-RRI-..., MSIP-..., KCC-...)"""
        if not text:
            return []
        pattern = r"(?:R-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+(?:-[A-Z0-9]+)?|MSIP-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+|KCC-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+)"
        found = re.findall(pattern, text, re.IGNORECASE)
        # 중복 제거 및 대문자화
        cleaned = []
        for x in found:
            u = x.upper().strip()
            if u not in cleaned:
                cleaned.append(u)
        return cleaned

    def lookup_conformity(self, cert_num: str) -> Dict[str, Any]:
        """
        국립전파연구원 전자파 적합성평가 번호로 등록 현황 조회
        """
        clean_num = cert_num.strip().upper()
        if not clean_num:
            return {"success": False, "error": "인증번호가 비어 있습니다.", "data": None}

        url = f"{self.POPUP_URL}?key_no={clean_num}"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code != 200:
                return {"success": False, "error": f"HTTP {res.status_code}", "data": None}

            soup = BeautifulSoup(res.text, "html.parser")
            data_map = {}
            for th, td in zip(soup.find_all("th"), soup.find_all("td")):
                k = th.get_text(strip=True)
                v = td.get_text(strip=True)
                if k:
                    data_map[k] = v

            # 유효성 검증: 상호나 기기명칭, 인증연월일이 있는지 확인
            if data_map.get("상호") or data_map.get("기기명칭") or data_map.get("인증연월일"):
                return {
                    "success": True,
                    "valid": True,
                    "cert_num": clean_num,
                    "data": {
                        "상호": data_map.get("상호", "-"),
                        "기기명칭": data_map.get("기기명칭", "-"),
                        "기본모델명": data_map.get("모델명", "-"),
                        "파생모델명": data_map.get("파생모델명", "-"),
                        "인증번호": data_map.get("인증번호", clean_num),
                        "제조자": data_map.get("제조자", "-"),
                        "제조국가": data_map.get("제조국가", "-"),
                        "인증연월일": data_map.get("인증연월일", "-"),
                        "조회링크": url
                    }
                }
            else:
                return {
                    "success": True,
                    "valid": False,
                    "cert_num": clean_num,
                    "message": "국립전파연구원에 등록되지 않았거나 일치하는 정보가 없습니다.",
                    "data": None
                }
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    def multi_lookup(self, cert_numbers: List[str]) -> List[Dict[str, Any]]:
        """여러 개의 전자파 인증번호를 일괄 조회"""
        results = []
        for num in cert_numbers:
            r = self.lookup_conformity(num)
            results.append(r)
        return results

rra_api = RraApi()
