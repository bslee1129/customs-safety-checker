import os
import sys
import io
import time
from PIL import Image
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="관세청 AI 위해식품 스마트 검사관",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 로컬 설정 및 서비스 모듈 import
from config import (
    GEMINI_API_KEY, FOOD_SAFETY_API_KEY, FOOD_SAFETY_SERVICE_ID,
    PRODUCT_IMAGE_DIR, SQLITE_DB_PATH
)
from services.db_service import db_service
from services.food_safety_api import food_safety_api
from services.ai_vision_service import ai_vision_service

# 커스텀 CSS 스타일링
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0d3b66 0%, #001e3d 100%);
        color: white;
        padding: 24px;
        border-radius: 12px;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        color: #ffffff;
        font-size: 1.9rem;
        margin-bottom: 6px;
        font-weight: 700;
    }
    .main-header p {
        color: #b0c4de;
        font-size: 0.95rem;
        margin-bottom: 0;
    }
    .status-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 12px;
    }
    .badge-danger {
        background-color: #dc3545;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .badge-safe {
        background-color: #28a745;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# 헤더 영역
st.markdown("""
<div class="main-header">
    <h1>🛡️ 관세청 AI 위해식품·불법의약품 스마트 검사관 v2.0</h1>
    <p>식품안전나라 차단 데이터 실시간 수집 및 현품 사진 1:1 비교 대조 시스템</p>
</div>
""", unsafe_allow_html=True)

# 사이드바: 통계 및 동기화 현황
with st.sidebar:
    st.header("📊 시스템 상태 및 DB 통계")
    
    # API 키 설정 상태 표시
    current_gemini_key = os.getenv("GEMINI_API_KEY", "")
    current_food_key = os.getenv("FOOD_SAFETY_API_KEY", "")

    if current_gemini_key:
        st.success("✅ Gemini AI Vision: 연동 완료")
    else:
        st.warning("⚠️ Gemini API 키 미등록 (Streamlit Secrets 설정 필요)")

    if current_food_key:
        st.success("✅ 식품안전나라 API: 연동 완료")
    else:
        st.warning("⚠️ 식품안전나라 API 키 미등록")

    st.markdown("---")
    
    # 자체 DB 통계 조회
    stats = db_service.get_stats()
    st.metric(label="총 위해식품 차단 데이터", value=f"{stats['total_records']:,} 건")
    st.metric(label="등록 바코드 수", value=f"{stats['total_barcodes']:,} 개")
    st.metric(label="식별 위해성분 종류", value=f"{stats['total_harmful_ingredients']:,} 종")
    st.caption(f"최종 DB 동기화: {stats['last_sync_time']}")

    st.markdown("---")
    st.subheader("🔄 Open API 동기화")
    if st.button("식품안전나라 최신 데이터 동기화", use_container_width=True):
        with st.spinner("식품안전나라 공식 API와 동기화 중..."):
            status = food_safety_api.get_status()
            if not status.get("connected"):
                st.error(f"연결 실패: {status.get('error')}")
            else:
                res = food_safety_api.fetch_all_records(batch_size=1000)
                if res.get("success"):
                    rows = res.get("rows", [])
                    inserted = db_service.replace_all_from_api(rows)
                    st.success(f"동기화 성공! {inserted:,}건 적재 완료")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"수집 실패: {res.get('error')}")

# 메인 탭
tab1, tab2, tab3 = st.tabs([
    "📸 현품 사진 1:1 비교 대조 검사",
    "🔍 차단 DB 통합 검색",
    "⌨️ 텍스트 직접 입력 수동 검사"
])

# -------------------------------------------------------------
# 탭 1: 현품 사진 1:1 비교 대조
# -------------------------------------------------------------
with tab1:
    st.markdown("### 📷 통관 현품 사진 검사 (Gemini Vision + 1:1 대조)")
    st.write("의심 제품의 전면 라벨 또는 원재료명 라벨 사진을 촬영하거나 업로드하세요.")

    col1, col2 = st.columns([1, 1])

    upload_mode = st.radio("사진 입력 방식 선택", ["파일 업로드", "카메라 직접 촬영"], horizontal=True)
    uploaded_file = None

    if upload_mode == "파일 업로드":
        uploaded_file = st.file_uploader("제품 사진 선택 (JPG, PNG)", type=["jpg", "jpeg", "png"])
    else:
        uploaded_file = st.camera_input("웹캠/카메라로 제품 촬영")

    barcode_hint = st.text_input("바코드 번호 (선택사항, 육안 식별 시 보완 입력)")

    if uploaded_file is not None:
        image_bytes = uploaded_file.getvalue()
        
        st.markdown("---")
        if st.button("🚀 AI 위해식품 정밀 검사 시작", type="primary", use_container_width=True):
            with st.spinner("Gemini AI가 라벨 문자를 해독하고 관세청 DB와 1:1 비교 대조 중입니다..."):
                # 1. AI Vision 분석
                vision_result = ai_vision_service.analyze_image(image_bytes)
                
                ocr_data = {}
                if vision_result.get("success") and vision_result.get("data"):
                    ocr_data = vision_result["data"]
                    if barcode_hint and not ocr_data.get("barcode"):
                        ocr_data["barcode"] = barcode_hint
                else:
                    ocr_data = {
                        "product_name": "판독 지연 (수동 확인 권장)",
                        "ingredients": [],
                        "barcode": barcode_hint or "",
                        "error_detail": vision_result.get("error")
                    }

                # 2. DB 매칭 및 1:1 비교
                match_res = db_service.match_product(ocr_data)
                is_matched = match_res.get("matched", False)
                db_record = match_res.get("record")
                reasons = match_res.get("reasons", [])

                st.subheader("📋 1:1 비교 대조 판정 결과")

                # 판정 배너
                if is_matched:
                    st.error("🚨 **[통관 보류 / 반입 차단 대상]** 위해식품·불법의약품 데이터베이스와 일치합니다!")
                else:
                    st.success("✅ **[정상 / 차단 미등록]** 위해식품 차단 데이터베이스에 등재되지 않은 품목입니다.")

                # 사진 1:1 비교 영역
                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown("#### 📷 현품 검사 사진")
                    st.image(image_bytes, caption="촬영/업로드된 실제 검사물품", use_container_width=True)

                with col_right:
                    st.markdown("#### 🏛️ 관세청 DB 공식 등록 원본 사진")
                    db_img_url = match_res.get("db_remote_image_url")
                    local_seq = db_record.get("등록번호") if db_record else None
                    local_img_path = None
                    if local_seq:
                        c1 = PRODUCT_IMAGE_DIR / f"img_{local_seq}.jpg"
                        c2 = PRODUCT_IMAGE_DIR / f"{local_seq}.jpg"
                        if c1.exists():
                            local_img_path = str(c1)
                        elif c2.exists():
                            local_img_path = str(c2)

                    if local_img_path and os.path.exists(local_img_path):
                        st.image(local_img_path, caption=f"DB 등록 사진 (등록번호: {local_seq})", use_container_width=True)
                    elif db_img_url:
                        st.image(db_img_url, caption=f"식품안전나라 공식 제공 이미지", use_container_width=True)
                    else:
                        st.info("등록된 비교 사진이 없거나 조회 중입니다.")

                # 세부 대조 정보
                st.markdown("#### 🔍 세부 대조 내역")
                info_col1, info_col2 = st.columns(2)
                with info_col1:
                    st.write("**[AI 라벨 추출 정보]**")
                    st.write(f"- 제품명: `{ocr_data.get('product_name', '-')}`")
                    st.write(f"- 제조사: `{ocr_data.get('manufacturer', '-')}`")
                    st.write(f"- 바코드: `{ocr_data.get('barcode', '-')}`")
                    st.write(f"- 추출된 성분 수: {len(ocr_data.get('ingredients', []))} 개")
                    if ocr_data.get("ingredients"):
                        st.caption(", ".join(ocr_data["ingredients"][:15]))

                with info_col2:
                    st.write("**[DB 매칭 판정 정보]**")
                    if db_record:
                        st.write(f"- 등록 제품명: `{db_record.get('제품명', '-')}`")
                        st.write(f"- 검출 위해성분: `{db_record.get('성분명', '-')}`")
                        st.write(f"- 반입금지 사유: `{db_record.get('회수사유', '-')}`")
                        st.write(f"- 정보 출처: `{db_record.get('정보출처', '-')}`")
                    else:
                        st.write("일치하는 차단 레코드가 없습니다.")

                if reasons:
                    st.markdown("#### ⚠️ 차단 근거 및 상세 사유")
                    for r in reasons:
                        st.warning(f"• {r}")

# -------------------------------------------------------------
# 탭 2: 차단 DB 통합 검색
# -------------------------------------------------------------
with tab2:
    st.markdown("### 🔍 관세청 위해식품·불법의약품 DB 통합 검색")
    search_q = st.text_input("검색어 입력 (제품명, 성분명, 바코드, 제조사)", "")
    
    if search_q.strip() or st.button("전체 목록 새로고침"):
        res = db_service.search(query=search_q, page=1, page_size=20)
        items = res.get("items", [])
        total = res.get("total", 0)

        st.write(f"검색 결과: 총 **{total:,}** 건")
        if items:
            for item in items:
                with st.expander(f"[{item.get('등록번호', '-')}] {item.get('제품명', '이름 없음')} (성분: {item.get('성분명', '-')})"):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        img_url = item.get("이미지경로")
                        if img_url:
                            st.image(img_url, use_container_width=True)
                        else:
                            st.caption("등록 이미지 없음")
                    with c2:
                        st.write(f"**제조사/국가**: {item.get('제조사', '-')} / {item.get('제조국', '-')}")
                        st.write(f"**검출 위해성분**: {item.get('성분명', '-')}")
                        st.write(f"**회수/차단 사유**: {item.get('회수사유', '-')}")
                        st.write(f"**바코드**: `{item.get('바코드', '-')}`")
                        st.write(f"**정보 출처**: {item.get('정보출처', '-')}")
        else:
            st.info("검색 조건에 맞는 데이터가 없습니다.")

# -------------------------------------------------------------
# 탭 3: 텍스트 직접 입력 수동 검사
# -------------------------------------------------------------
with tab3:
    st.markdown("### ⌨️ 제품 정보 직접 입력 대조")
    t_name = st.text_input("제품명", "")
    t_barcode = st.text_input("바코드 (선택사항)", "")
    t_ing = st.text_area("의심 성분 (쉼표로 구분 입력, 예: yohimbine, sildenafil, melatonin)", "")

    if st.button("수동 대조 실행", type="primary"):
        if not t_name.strip() and not t_ing.strip():
            st.warning("제품명 또는 성분을 입력해 주세요.")
        else:
            ing_list = [x.strip() for x in t_ing.split(",") if x.strip()]
            ocr_data = {
                "product_name": t_name,
                "barcode": t_barcode,
                "ingredients": ing_list
            }
            res = db_service.match_product(ocr_data)
            if res.get("matched"):
                st.error("🚨 [차단 대상] 입력하신 정보가 위해물품 DB와 일치합니다!")
                st.json(res)
            else:
                st.success("✅ [정상] 일치하는 차단 정보가 없습니다.")
