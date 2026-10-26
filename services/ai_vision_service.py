import os
import json
import re
import io
from PIL import Image
from typing import Dict, Any, Optional, List, Union
from config import GEMINI_API_KEY

class AiVisionService:
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key
        self.client = None
        self._init_client()

    def _init_client(self):
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"⚠️ Gemini Client 초기화 실패: {e}")
                self.client = None

    def analyze_image(self, images: Union[bytes, List[bytes]]) -> Dict[str, Any]:
        """
        현품 촬영 사진(단일 또는 여러 장: 전면 라벨, 후면 원재료/성분표, 바코드 등)을
        Gemini Vision 모델로 통합 분석하여 제품명, 브랜드, 바코드, 성분 목록을 JSON으로 추출
        """
        if isinstance(images, bytes):
            image_list = [images]
        elif isinstance(images, list):
            image_list = images
        else:
            return {
                "success": False,
                "error": "전달된 이미지 데이터 형식이 올바르지 않습니다.",
                "data": None
            }

        if not image_list:
            return {
                "success": False,
                "error": "등록된 사진이 없습니다.",
                "data": None
            }

        processed_parts = []
        max_dim = 1600

        for idx, img_b in enumerate(image_list):
            try:
                pil_img = Image.open(io.BytesIO(img_b))
                if max(pil_img.size) > max_dim:
                    pil_img.thumbnail((max_dim, max_dim))
                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=85)
                    img_b = buf.getvalue()
                
                from google.genai import types
                processed_parts.append(
                    types.Part.from_bytes(data=img_b, mime_type="image/jpeg")
                )
            except Exception as e:
                print(f"⚠️ {idx+1}번째 이미지 처리 오류: {e}")
                continue

        if not processed_parts:
            return {
                "success": False,
                "error": "유효하게 처리된 사진이 없습니다.",
                "data": None
            }

        if not self.client:
            self._init_client()
            if not self.client:
                return {
                    "success": False,
                    "error": "Gemini API 키가 설정되지 않았거나 클라이언트를 초기화할 수 없습니다. .env 또는 Secrets를 확인해주세요.",
                    "data": None
                }

        prompt = """
당신은 대한민국 관세청과 식품의약품안전처가 제공하는 '대국민 해외직구 의약품·영양제 안심 통관 도우미' AI 전문 약학 자문관입니다.
전달된 사진들은 동일한 의심 제품의 여러 각도 사진(제품 전면 라벨, 후면 원재료/성분표(Supplement Facts, Nutrition Facts, Ingredients), 바코드, 측면 등)일 수 있습니다.
전달된 모든 사진을 종합적으로 정밀 판독하여,
"해당 약이 위험한지", "국내 반입이 가능한지", 그리고 "왜 반입이 안 되는지(부작용 및 법적 사유)"를 국민 눈높이에 맞춰 친절하고 알기 쉽게 분석하세요.

반드시 마크다운 태그(```json 등) 없이 순수 JSON 객체만 반환하세요:
{
  "product_name": "제품 전체 공식 명칭 (영문 또는 원어)",
  "product_name_ko": "제품명 한국어 번역 또는 한글 친화적 표기",
  "brand": "제조사 또는 브랜드명",
  "category": "일반의약품 | 전문의약품 | 건강기능식품(보충제) | 기타",
  "barcode": "바코드 숫자 (보이는 경우만, 예: 850045552664, 없으면 null)",
  "ingredients": ["주요성분1", "주요성분2", "주요성분3", ...],
  "harmful_suspects": ["식약처/관세청 반입금지 또는 주의 성분 목록 (예: Yohimbine, Melatonin, Sennoside, Sildenafil, Ephedrine, CBD 등)"],
  "is_prohibited_suspect": true/false (국내 반입 금지 또는 처방전 필수 성분이 포함된 것으로 보이면 true),
  "why_prohibited_reason": "왜 반입이 안 되거나 주의해야 하는지 일반 국민이 쉽게 이해할 수 있는 구체적 이유 (예: '요힘빈 성분은 심혈관계 부작용(심근경색, 혈압 급상승)을 유발할 수 있어 식약처가 해외직구 반입을 법적으로 전면 금지하고 있습니다.')",
  "health_risks": "복용 시 건강상 위험성 및 부작용 설명 (간독성, 어지럼증, 중독성 등)",
  "customs_advice": "국민을 위한 통관 가이드 및 행동 요령 (예: '구매 전이라면 구매를 중단하세요. 통관 시 전량 폐기되며 폐기 수수료가 발생합니다.')",
  "summary": "국민을 위한 1~2줄 총평 요약"
}

중요 판정 지침:
1. 사진 중 후면 성분표(Supplement Facts / Ingredients)가 있다면 모든 성분명을 하나도 빠짐없이 꼼꼼히 추출하세요.
2. 멜라토닌(Melatonin: 국내 전문의약품/처방필요), 요힘빈(Yohimbine: 심근경색위험 반입금지), 센노사이드(Sennoside: 변비약 성분 남용위험), 실데나필/타다라필(발기부전 치료성분), 에페드린/슈도에페드린(마약원료), CBD/THC(대마성분) 등 국내 반입 제한 성분을 엄격히 선별하세요.
3. 전문 용어보다는 국민이 안심하고 이해할 수 있는 쉬운 한국어로 설명하세요.
"""

        # 호출할 모델 순서 (fallback)
        models_to_try = [
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-2.0-flash"
        ]

        last_error = None
        for model_name in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=processed_parts + [prompt]
                )
                
                resp_text = response.text.strip()
                # 마크다운 코드블록 제거
                if resp_text.startswith("```"):
                    resp_text = re.sub(r"^```[a-zA-Z]*\n?", "", resp_text)
                    resp_text = re.sub(r"\n?```$", "", resp_text)
                    resp_text = resp_text.strip()

                parsed = json.loads(resp_text)
                return {
                    "success": True,
                    "model_used": model_name,
                    "data": parsed
                }
            except Exception as e:
                last_error = e
                continue

        return {
            "success": False,
            "error": f"AI 비전 판독 실패 ({last_error})",
            "data": None
        }

ai_vision_service = AiVisionService()
