import os
import json
import re
import io
from PIL import Image
from typing import Dict, Any, Optional
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

    def analyze_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        현품 촬영 사진을 Gemini Vision 모델로 분석하여 제품명, 브랜드, 바코드, 성분 목록을 JSON으로 추출
        """
        # 이미지 크기 및 형식 유효성 검사
        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            # 너무 큰 이미지는 리사이징 (최대 1600px)
            max_dim = 1600
            if max(pil_img.size) > max_dim:
                pil_img.thumbnail((max_dim, max_dim))
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=85)
                image_bytes = buf.getvalue()
        except Exception as e:
            return {
                "success": False,
                "error": f"유효하지 않은 이미지 파일입니다: {e}",
                "data": None
            }

        if not self.client:
            self._init_client()
            if not self.client:
                return {
                    "success": False,
                    "error": "Gemini API 키가 설정되지 않았거나 클라이언트를 초기화할 수 없습니다. .env를 확인해주세요.",
                    "data": None
                }

        prompt = """
당신은 대한민국 관세청 및 식품의약품안전처의 'AI 위해식품/불법의약품 스마트 검사관'입니다.
제공된 사진(제품 포장 전면, 라벨, 성분표, 바코드 등)을 정밀하게 판독하여 다음 정보를 반드시 JSON 포맷으로만 응답하세요.

마크다운(```json ```) 태그 없이 순수 JSON 객체만 반환하세요:
{
  "product_name": "제품 전체 공식 명칭 (영문 또는 원어)",
  "product_name_ko": "제품명 한국어 번역 또는 한글 표기",
  "brand": "제조사 또는 브랜드명",
  "barcode": "바코드 숫자 (보이는 경우만, 예: 850045552664, 없으면 null)",
  "ingredients": ["성분1", "성분2", "성분3", ...],
  "harmful_suspects": ["위해 의심 성분 (예: Yohimbine, Sennoside, Sildenafil, Ephedrine, Melatonin 등)"],
  "summary": "제품 및 성분에 대한 1~2줄 검사 요약 설명"
}

중요 지침:
1. 라벨의 텍스트와 Ingredients/Supplement Facts를 정밀하게 읽으세요.
2. 성분 목록에 있는 모든 화학물질명과 생약명, 추출물을 ingredients 배열에 넣으세요.
3. 바코드가 보이면 누락 없이 정확한 숫자를 추출하세요.
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
                from google.genai import types
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                        prompt
                    ]
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
