import os
import io
import base64
import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from config import (
    BASE_DIR, HOST, PORT, DEBUG,
    TEMP_UPLOADS_DIR, PRODUCT_IMAGE_DIR
)
from services.food_safety_api import food_safety_api
from services.db_service import db_service
from services.ai_vision_service import ai_vision_service

app = FastAPI(
    title="관세청 AI 위해식품·불법의약품 스마트 검사관",
    description="식품안전나라 차단 API 실시간 수집 및 현품 사진 1:1 비교 대조 시스템",
    version="2.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 마운트
static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# -------------------------------------------------------------
# 페이지 라우트
# -------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = BASE_DIR / "templates" / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Index template not found")
    return index_file.read_text(encoding="utf-8")

# -------------------------------------------------------------
# 이미지 파일 제공 라우트
# -------------------------------------------------------------
@app.get("/api/image/local/{seq}")
async def get_local_image(seq: str):
    """로컬에 저장된 제품 원본 이미지 스트리밍"""
    c1 = PRODUCT_IMAGE_DIR / f"img_{seq}.jpg"
    c2 = PRODUCT_IMAGE_DIR / f"{seq}.jpg"
    if c1.exists():
        return FileResponse(c1, media_type="image/jpeg")
    if c2.exists():
        return FileResponse(c2, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")

# -------------------------------------------------------------
# 통계 및 현황 API
# -------------------------------------------------------------
@app.get("/api/stats")
async def get_system_stats():
    """시스템 DB 통계 및 API 상태 반환"""
    db_stats = db_service.get_stats()
    api_stats = food_safety_api.get_status()
    return {
        "database": db_stats,
        "api_connection": api_stats
    }

# -------------------------------------------------------------
# 작업 1: API 데이터 가져오기 (식품안전나라 I2715 차단 API)
# -------------------------------------------------------------
class SyncRequest(BaseModel):
    start: int = 1
    end: int = 50
    download_images: bool = False

@app.get("/api/sync/status")
async def check_api_status():
    """식품안전나라 차단정보 서버 연결 확인 및 총 건수 반환"""
    return food_safety_api.get_status()

@app.post("/api/sync/fetch")
async def fetch_api_data(req: SyncRequest):
    """식품안전나라 API에서 데이터를 가져와 로컬 DB에 병합"""
    res = food_safety_api.fetch_records(
        start=req.start,
        end=req.end,
        download_images=req.download_images
    )
    if not res.get("success"):
        return JSONResponse(status_code=500, content=res)

    new_rows = res.get("rows", [])
    merged_count = db_service.merge_records(new_rows)

    return {
        "success": True,
        "fetched_count": len(new_rows),
        "newly_added_count": merged_count,
        "total_db_count": len(db_service.records),
        "sample_records": new_rows[:5]
    }

# -------------------------------------------------------------
# 차단 목록 검색 API
# -------------------------------------------------------------
@app.get("/api/drugs")
async def list_drugs(
    q: str = Query("", description="검색어 (제품명, 성분명, 바코드, 제조사)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100)
):
    """위해식품/불법의약품 목록 검색 및 페이징"""
    result = db_service.search(query=q, page=page, page_size=page_size)
    return result

# -------------------------------------------------------------
# 작업 2: 사진 촬영 및 1:1 비교 대조 검사 API
# -------------------------------------------------------------
@app.post("/api/inspect/photo")
async def inspect_photo(
    file: UploadFile = File(...),
    barcode_hint: Optional[str] = Form(None)
):
    """
    현품 촬영 사진을 수신하여:
    1) Gemini Vision AI로 라벨 OCR & 성분 추출
    2) 관세청 위해물품 DB와 1:1 비교 대조
    3) 촬영 사진 + DB 원본 사진 + 대조 판정 결과 반환
    """
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="업로드된 사진 데이터가 비어 있습니다.")

        # 촬영 사진 Base64 인코딩 (웹 UI 표시용)
        photo_base64 = f"data:image/jpeg;base64,{base64.b64encode(content).decode('utf-8')}"

        # 1. AI Vision 분석 실행
        vision_result = ai_vision_service.analyze_image(content)
        
        ocr_data = {}
        if vision_result.get("success") and vision_result.get("data"):
            ocr_data = vision_result["data"]
            if barcode_hint and not ocr_data.get("barcode"):
                ocr_data["barcode"] = barcode_hint
        else:
            # AI 분석 실패 시 안내 및 기본 구조
            ocr_data = {
                "product_name": "AI 판독 지연 (수동 확인 권장)",
                "ingredients": [],
                "barcode": barcode_hint or "",
                "error_detail": vision_result.get("error")
            }

        # 2. DB 매칭 및 1:1 비교
        match_result = db_service.match_product(ocr_data)

        # 3. 로컬 이미지 스트리밍 URL 구성
        db_record = match_result.get("record")
        matched_image_api_url = None
        if db_record and db_record.get("등록번호"):
            seq = db_record["등록번호"]
            c1 = PRODUCT_IMAGE_DIR / f"img_{seq}.jpg"
            c2 = PRODUCT_IMAGE_DIR / f"{seq}.jpg"
            if c1.exists() or c2.exists():
                matched_image_api_url = f"/api/image/local/{seq}"

        return {
            "success": True,
            "inspected_photo_preview": photo_base64,
            "vision_model_used": vision_result.get("model_used", "fallback"),
            "ai_extracted": ocr_data,
            "match_result": match_result,
            "db_image_api_url": matched_image_api_url,
            "db_remote_image_url": match_result.get("db_remote_image_url")
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"검사 처리 중 오류: {str(e)}")

# -------------------------------------------------------------
# 텍스트 직접 입력 수동 검사 API
# -------------------------------------------------------------
class ManualInspectRequest(BaseModel):
    product_name: str
    barcode: Optional[str] = None
    ingredients: Optional[List[str]] = None

@app.post("/api/inspect/text")
async def inspect_text(req: ManualInspectRequest):
    """제품명, 바코드, 성분을 텍스트로 직접 입력하여 DB 대조"""
    ocr_data = {
        "product_name": req.product_name,
        "barcode": req.barcode or "",
        "ingredients": req.ingredients or []
    }
    match_result = db_service.match_product(ocr_data)
    
    db_record = match_result.get("record")
    matched_image_api_url = None
    if db_record and db_record.get("등록번호"):
        seq = db_record["등록번호"]
        c1 = PRODUCT_IMAGE_DIR / f"img_{seq}.jpg"
        c2 = PRODUCT_IMAGE_DIR / f"{seq}.jpg"
        if c1.exists() or c2.exists():
            matched_image_api_url = f"/api/image/local/{seq}"

    return {
        "success": True,
        "ai_extracted": ocr_data,
        "match_result": match_result,
        "db_image_api_url": matched_image_api_url,
        "db_remote_image_url": match_result.get("db_remote_image_url")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=HOST, port=PORT, reload=DEBUG)
