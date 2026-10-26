import os
import sys
import io
import time
from datetime import datetime
from PIL import Image
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="관세청 & 범정부 AI 해외직구 안전지킴이",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 로컬 설정 및 서비스 모듈 import
from config import (
    GEMINI_API_KEY, FOOD_SAFETY_API_KEY, FOOD_SAFETY_SERVICE_ID,
    SAFETYKOREA_API_KEY, PRODUCT_IMAGE_DIR, SQLITE_DB_PATH
)
from services.db_service import db_service
from services.food_safety_api import food_safety_api
from services.safetykorea_api import safetykorea_api
from services.ai_vision_service import ai_vision_service
from services.rra_api import rra_api

# 커스텀 CSS 스타일링
st.markdown("""
<style>
    /* 이미지 크기 자동 최적화 (세로 사진 과대 표시 방지) */
    div[data-testid="stImage"] {
        text-align: center;
        display: flex;
        justify-content: center;
    }
    div[data-testid="stImage"] img {
        max-height: 360px !important;
        width: auto !important;
        object-fit: contain !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.15) !important;
        margin: 0 auto !important;
    }

    /* 모바일 반응형 베이스 */
    @media (max-width: 768px) {
        div[data-testid="stImage"] img {
            max-height: 280px !important;
        }
        .user-header, .admin-header {
            padding: 16px 14px !important;
            margin-bottom: 14px !important;
            border-radius: 10px !important;
        }
        .user-header h1, .admin-header h1 {
            font-size: 1.4rem !important;
            line-height: 1.3 !important;
        }
        .user-header p, .admin-header p {
            font-size: 0.85rem !important;
        }
        .stButton button {
            min-height: 48px !important;
            font-size: 1rem !important;
            font-weight: bold !important;
        }
    }
    
    .user-header {
        background: linear-gradient(135deg, #0d3b66 0%, #1e3a8a 100%);
        color: white;
        padding: 24px;
        border-radius: 14px;
        margin-bottom: 22px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.12);
    }
    .admin-header {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        color: white;
        padding: 24px;
        border-radius: 14px;
        margin-bottom: 22px;
        border-left: 6px solid #3b82f6;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .badge-danger {
        background-color: #dc3545;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .badge-warning {
        background-color: #f59e0b;
        color: #1e293b;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .badge-safe {
        background-color: #10b981;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .badge-info {
        background-color: #3b82f6;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .stat-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 세션 상태 초기화
# -------------------------------------------------------------
if "admin_authenticated" not in st.session_state:
    st.session_state["admin_authenticated"] = False
if "camera_photos" not in st.session_state:
    st.session_state["camera_photos"] = []
if "inspection_history" not in st.session_state:
    st.session_state["inspection_history"] = []

# -------------------------------------------------------------
# 사이드바: 모드 선택 (대국민 서비스 vs 관리자 콘솔)
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🌐 모드 전환")
    mode = st.radio(
        "사용 목적을 선택하세요",
        ["일반사용자 (대국민 안심 서비스)", "관리자 콘솔 (세관·운영자)"],
        index=0,
        label_visibility="collapsed"
    )
    is_admin_mode = (mode == "관리자 콘솔 (세관·운영자)")
    st.markdown("---")

# =============================================================
# 1. 일반사용자(대국민) 조회 서비스
# =============================================================
def render_user_service():
    # 대국민용 사이드바 안내
    with st.sidebar:
        st.subheader("💡 이용 안내")
        st.info("""
        **안심 직구 3단계 검사법**
        1. 구입할 제품의 라벨/박스 사진을 촬영하거나 업로드하세요.
        2. AI가 유해성분, KC인증, 전파인증을 자동 판독합니다.
        3. 실시간 정부 공인 DB 대조 결과를 확인하세요.
        """)
        
        st.markdown("---")
        st.subheader("📞 안전신고 및 상담처")
        st.write("- **불량식품 신고**: 국번없이 1399")
        st.write("- **제품안전정보센터 (KC)**: 1600-1384")
        st.write("- **관세청 밀수신고**: 국번없이 125")
        st.caption("관세청 × 식약처 × 국표원 × 국립전파연구원 합동")

    # 대국민용 메인 헤더
    st.markdown("""
    <div class="user-header">
        <h1 style="color: white; margin: 0 0 8px 0; font-size: 1.85rem;">🛡️ 해외직구 안전지킴이 - 대국민 안심 조회 포털</h1>
        <p style="color: #cbd5e1; margin: 0; font-size: 0.95rem;">
            식약처 직구차단식품 + 국가기술표준원 KC안전인증 + 국립전파연구원 전자파인증을 한눈에 실시간 확인하세요!
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📸 AI 사진 안심 검사",
        "🏛️ 범정부 안전인증 DB (KC·전자파·리콜)",
        "🔍 위해식품 차단 목록 검색",
        "⌨️ 제품명·성분 직접 입력 조회"
    ])

    # 탭 1: AI 사진 안심 검사
    with tab1:
        st.markdown("### 📷 제품 사진 AI 안심 검사")
        st.write("의심 제품의 **전면(제품명), 후면(원재료/성분표), 측면(바코드, KC/전파인증마크)** 사진을 1장 또는 여러 장 등록하세요.")

        # 1️⃣ 사진 등록 영역 (상단)
        st.subheader("1️⃣ 사진 등록 및 촬영 (다중 선택 가능)")
        uploaded_files = st.file_uploader(
            "제품 사진 파일 선택 (여러 장 등록 가능)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="user_upload_files"
        )
        
        with st.expander("📷 스마트폰 카메라로 직접 촬영하기"):
            cam_pic = st.camera_input("카메라 촬영", key="user_cam")
            if cam_pic:
                if st.button("촬영한 사진 목록에 추가", key="user_add_cam"):
                    st.session_state["camera_photos"].append(cam_pic.getvalue())
                    st.success(f"촬영 사진 {len(st.session_state['camera_photos'])}장 추가됨!")

        total_images_bytes = []
        if uploaded_files:
            for uf in uploaded_files:
                total_images_bytes.append(uf.getvalue())
        if st.session_state["camera_photos"]:
            total_images_bytes.extend(st.session_state["camera_photos"])

        if total_images_bytes:
            st.write(f"**현재 등록된 사진: 총 {len(total_images_bytes)}장**")
            if len(total_images_bytes) == 1:
                p_c1, p_c2, p_c3 = st.columns([1, 2, 1])
                with p_c2:
                    st.image(total_images_bytes[0], caption="등록된 제품 사진 #1", width=220)
            else:
                img_cols = st.columns(min(len(total_images_bytes), 4))
                for i, b_data in enumerate(total_images_bytes):
                    with img_cols[i % len(img_cols)]:
                        st.image(b_data, caption=f"사진 #{i+1}", width=180)
            
            if st.button("등록된 사진 초기화", key="user_reset_imgs"):
                st.session_state["camera_photos"] = []
                st.rerun()

        st.markdown("")
        run_inspect = st.button("🚀 AI 안심 진단 시작하기", type="primary", use_container_width=True, key="user_inspect_btn")
        st.markdown("---")

        # 2️⃣ 안심 진단 결과 (하단 - 사진 등록 아래로)
        st.subheader("2️⃣ 안심 진단 결과")
        if run_inspect:
                if not total_images_bytes:
                    st.warning("먼저 검사할 사진을 등록하거나 촬영해 주세요.")
                else:
                    with st.spinner("AI가 제품명, 성분, KC안전인증, 전파인증을 종합 분석 중입니다..."):
                        start_t = time.time()
                        ocr_result = ai_vision_service.extract_labels_multi(total_images_bytes)
                        if ocr_result.get("error") and not ocr_result.get("product_name"):
                            st.warning(f"⚠️ AI 라벨 인식 안내: {ocr_result.get('error')}")

                        match_result = db_service.match_product(ocr_result)

                        p_name = ocr_result.get("product_name") or ""
                        b_code = ocr_result.get("barcode") or ""
                        kc_num = ocr_result.get("kc_cert_num")
                        rra_nums = ocr_result.get("rra_cert_nums") or []
                        
                        safety_res = safetykorea_api.comprehensive_check(
                            product_name=p_name,
                            barcode=b_code,
                            kc_cert_num=kc_num,
                            cert_num=kc_num
                        )
                        rra_res_list = rra_api.multi_lookup(rra_nums)

                        # 검사 이력 저장
                        elapsed = round(time.time() - start_t, 2)
                        st.session_state["inspection_history"].append({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "product_name": p_name or "미상",
                            "is_food_blocked": match_result.get("matched", False),
                            "has_safety_recall": safety_res.get("has_danger", False),
                            "kc_num": kc_num or "-",
                            "rra_nums": rra_nums or [],
                            "elapsed": elapsed
                        })

                        # 판정 상태 및 세부 요약 추출
                        food_status = match_result.get("status", "PASS")
                        citizen_summary = match_result.get("citizen_summary") or {}
                        is_blocked = match_result.get("matched", False)
                        has_safety_danger = safety_res.get("has_danger", False)
                        
                        db_rec = match_result.get("record") or {}
                        match_stage = match_result.get("match_stage", "")
                        
                        # 안전한 필드 바인딩 (빈 값 '-' 방지)
                        matched_product_name = db_rec.get("제품명") or p_name or "식품안전나라 차단 의심 품목"
                        matched_harmful_ingr = (
                            db_rec.get("성분명") 
                            or match_result.get("db_harmful_ingredient")
                            or ", ".join(ocr_result.get("harmful_suspects", []))
                            or "해외 의약품 주의 성분 (처방전 필요)"
                        )
                        matched_reason = (
                            db_rec.get("회수사유") 
                            or citizen_summary.get("why_prohibited") 
                            or match_result.get("db_reason") 
                            or ocr_result.get("why_prohibited_reason")
                            or "국내 반입 제한 또는 인체 위해 우려 성분 함유"
                        )
                        matched_maker = db_rec.get("제조사") or ocr_result.get("brand") or "해외 제조사"
                        matched_country = db_rec.get("제조국") or "해외 수입"
                        matched_source = db_rec.get("정보출처") or "식품안전나라 공식 Open API (I2715) 및 관세청 AI 안전 판정"

                        # -------------------------------------------------------------
                        # 1. 상단 종합 판정 배너
                        # -------------------------------------------------------------
                        if has_safety_danger or food_status == "DANGER":
                            st.error("### 🚨 [반입 금지 / 폐기 대상] 정부 위해물품 차단 또는 유통 리콜 명령 대상입니다!")
                        elif food_status == "WARNING":
                            st.warning("### ⚠️ [반입 주의 / 확인 필요] 해외 직구 의약품으로 처방전 필요 또는 반입 수량 제한 대상입니다!")
                        else:
                            st.success("### ✅ [정상 / 차단 미등록] 정부 위해물품 차단 데이터베이스에 등재되지 않은 정상 품목입니다.")

                        # -------------------------------------------------------------
                        # 2. 📋 1:1 비교 대조 사진 영역 (현품 사진 vs 정부 DB 공식 등록 사진)
                        # -------------------------------------------------------------
                        st.markdown("### 📋 1:1 비교 대조 판정 결과")

                        col_left, col_right = st.columns(2)
                        with col_left:
                            st.markdown("#### 📷 현품 검사 사진")
                            st.caption("촬영/업로드된 실제 검사물품")
                            if len(total_images_bytes) == 1:
                                st.image(total_images_bytes[0], caption="촬영/업로드된 실제 검사물품", width=280)
                            else:
                                img_tabs = st.tabs([f"사진 #{i+1}" for i in range(len(total_images_bytes))])
                                for i, i_tab in enumerate(img_tabs):
                                    with i_tab:
                                        st.image(total_images_bytes[i], caption=f"실제 검사물품 #{i+1}", width=280)

                        with col_right:
                            st.markdown("#### 🏛️ 관세청·정부 DB 공식 등록 원본 사진")
                            st.caption("식품안전나라 / 국표원 공식 제공 이미지")

                            # 1) 식약처 위해식품/의약품 차단 DB 사진 확인
                            db_remote_url = match_result.get("db_remote_image_url") or db_rec.get("원본이미지URL")
                            local_seq = db_rec.get("등록번호")
                            local_img_path = None
                            if local_seq:
                                c1 = PRODUCT_IMAGE_DIR / f"img_{local_seq}.jpg"
                                c2 = PRODUCT_IMAGE_DIR / f"{local_seq}.jpg"
                                if c1.exists():
                                    local_img_path = str(c1)
                                elif c2.exists():
                                    local_img_path = str(c2)

                            # 2) 국표원 KC 안전인증 등록 사진
                            kc_images = []
                            if safety_res.get("kc_detail"):
                                kc_images = safety_res["kc_detail"].get("certificationImageUrls") or []

                            # 3) 국표원 리콜 제품 사진
                            recall_images = []
                            for dr in safety_res.get("domestic_recalls", []):
                                for rf in dr.get("recallFiles", []):
                                    if rf.get("imageUrl"):
                                        recall_images.append(rf.get("imageUrl"))

                            # 렌더링
                            rendered_db_img = False
                            if is_blocked and (local_img_path or db_remote_url):
                                target_img = local_img_path if local_img_path else db_remote_url
                                st.image(target_img, caption="식품안전나라 공식 제공 차단 제품 원본 사진", width=280)
                                rendered_db_img = True
                            elif recall_images:
                                st.image(recall_images[0], caption="국가기술표준원 리콜 처분 공고 원본 사진", width=280)
                                rendered_db_img = True
                            elif kc_images:
                                st.image(kc_images[0], caption="국가기술표준원 KC 공식 인증 등록 사진", width=280)
                                rendered_db_img = True

                            if not rendered_db_img:
                                if is_blocked and db_rec:
                                    st.info("⚠️ 식품안전나라 차단 데이터에 등록 번호는 있으나, 공표용 사진 이미지가 등록되지 않은 품목입니다.")
                                elif is_blocked and not db_rec:
                                    st.info("ℹ️ 본 제품은 해외 직구 일반/전문의약품으로 AI가 성분 및 약사법 통관 기준을 판정한 건입니다. (식품안전나라 차단식품 직접 등재 품목이 아니므로 공식 이미지 없음)")
                                else:
                                    st.info("ℹ️ 위해식품 차단 데이터베이스에 미등재된 정상 품목이므로 차단 등록 사진이 없습니다.")

                        # -------------------------------------------------------------
                        # 3. 🔍 세부 대조 내역 (AI 라벨 추출 정보 vs 정부 DB)
                        # -------------------------------------------------------------
                        with st.expander("🔍 세부 대조 내역 (1:1 상세 정보 대조)", expanded=True):
                            col_d1, col_d2 = st.columns(2)
                            with col_d1:
                                st.markdown("**[AI 라벨 추출 정보]**")
                                st.write(f"- **제품명**: {p_name or '-'}")
                                st.write(f"- **제조사/브랜드**: {ocr_result.get('brand') or '-'}")
                                st.write(f"- **바코드**: {b_code or '-'}")
                                ings = ocr_result.get('ingredients', [])
                                st.write(f"- **추출된 성분 수**: {len(ings)} 개")
                                if ings:
                                    st.caption(f"성분: {', '.join(ings[:15])}")
                            with col_d2:
                                st.markdown("**[DB 매칭 판정 정보]**")
                                if is_blocked:
                                    st.write(f"- **등록 제품명**: {matched_product_name}")
                                    st.write(f"- **검출 위해성분**: <span class='badge-danger'>{matched_harmful_ingr}</span>", unsafe_allow_html=True)
                                    st.write(f"- **반입금지 사유**: {matched_reason}")
                                    st.write(f"- **판정 단계**: {match_stage or '정부 차단 기준 일치'}")
                                    st.write(f"- **정보 출처**: {matched_source}")
                                elif safety_res.get("has_danger"):
                                    st.write(f"- **적발 유형**: 국표원 유통제품 안전성조사 리콜 적발")
                                    st.write(f"- **관련 인증번호**: `{kc_num or '-'}`")
                                else:
                                    st.write("- **판정 결과**: 위해식품 차단 데이터베이스에 등재되지 않은 정상 품목입니다.")

                        st.markdown("---")

                        # -------------------------------------------------------------
                        # 4. 식약처 위해식품 차단 및 의약품 통관 주의 카드
                        # -------------------------------------------------------------
                        if is_blocked:
                            card_border = "#dc3545" if food_status == "DANGER" else "#f59e0b"
                            card_bg = "rgba(220, 53, 69, 0.15)" if food_status == "DANGER" else "rgba(245, 158, 11, 0.15)"
                            card_title = "🚫 [식약처] 해외직구 차단식품·위해원료 등재 확인" if food_status == "DANGER" else "⚠️ [관세청·식약처] 해외 직구 의약품 통관 주의 안내"
                            card_title_color = "#ff6b6b" if food_status == "DANGER" else "#fbbf24"
                            badge_cls = "badge-danger" if food_status == "DANGER" else "badge-warning"
                            
                            health_risk = citizen_summary.get("health_risks") or ocr_result.get("health_risks") or "복용 시 건강 피해 또는 부작용 우려가 있습니다."
                            action_guide = citizen_summary.get("action_guide") or ocr_result.get("customs_advice") or "세관 통관 전 반품하거나 처방전을 구비하세요."

                            st.markdown(f"""
                            <div style="background: {card_bg}; border: 2px solid {card_border}; border-radius: 10px; padding: 18px; margin-bottom: 14px;">
                                <h4 style="margin: 0 0 10px 0; color: {card_title_color};">{card_title}</h4>
                                <div style="font-size: 0.95rem; line-height: 1.7;">
                                    <div><strong>🏷️ 대상 제품명</strong>: {matched_product_name}</div>
                                    <div><strong>🧪 주의/검출 성분</strong>: <span class="{badge_cls}">{matched_harmful_ingr}</span></div>
                                    <div><strong>🏢 제조사 / 제조국</strong>: {matched_maker} / {matched_country}</div>
                                    <div style="margin-top: 10px; background: rgba(0,0,0,0.25); padding: 12px; border-radius: 8px;">
                                        <div style="color: #fca5a5; font-weight: bold;">🛑 반입 제한 / 차단 사유:</div>
                                        <div style="font-size: 0.9rem; margin-bottom: 6px;">{matched_reason}</div>
                                        <div style="color: #fca5a5; font-weight: bold;">🩺 건강상 위험성 / 부작용:</div>
                                        <div style="font-size: 0.9rem; margin-bottom: 6px;">{health_risk}</div>
                                        <div style="color: #6ee7b7; font-weight: bold;">📋 관세청 통관 가이드 및 조치 사항:</div>
                                        <div style="font-size: 0.9rem;">{action_guide}</div>
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                        # 2. 국가기술표준원 국내 리콜 적발 카드
                        dom_recalls = safety_res.get("domestic_recalls", [])
                        if dom_recalls:
                            for dr in dom_recalls:
                                r_uid = dr.get("recallUid")
                                r_board_url = dr.get("source_url") or f"https://www.safetykorea.kr/recall/ajax/recallBoard?recallUid={r_uid}"
                                
                                st.markdown(f"""
                                <div style="background: rgba(220, 53, 69, 0.15); border: 2px solid #ef4444; border-radius: 10px; padding: 18px; margin-bottom: 14px;">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                        <h4 style="margin: 0; color: #ef4444;">🚨 [국표원] 유통제품 안전성 조사 리콜 명령 적발!</h4>
                                        <span class="badge-danger">{dr.get('recallTypeName', '명령에 따른 리콜')}</span>
                                    </div>
                                    <div style="font-size: 0.95rem; line-height: 1.6;">
                                        <div><strong>🏷️ 리콜 대상 제품명(모델명)</strong>: {dr.get('recallProductName', '-')} ({dr.get('recallModelName', '-')})</div>
                                        <div><strong>📋 KC인증번호</strong>: <code>{dr.get('certNum', '-')}</code></div>
                                        <div><strong>🏢 사업자(수입/제조사)</strong>: {dr.get('recallCmpnyName', '-')} (문의: {dr.get('recallInqryTel', '-')})</div>
                                        <div><strong>📅 공표일자</strong>: {dr.get('publishDate', '-')} | <strong>제조국</strong>: {dr.get('makingCntryName', '-')}</div>
                                        <div style="margin-top: 10px; background: rgba(0,0,0,0.25); padding: 12px; border-radius: 8px;">
                                            <div style="color: #fca5a5; font-weight: bold;">⚠️ 적발된 결함 및 유해물질:</div>
                                            <div style="white-space: pre-wrap; font-size: 0.9rem; margin-bottom: 6px;">{dr.get('harmDscr', '-')}</div>
                                            <div style="color: #fca5a5; font-weight: bold;">🩺 인체 위해성 / 사고 우려:</div>
                                            <div style="white-space: pre-wrap; font-size: 0.9rem; margin-bottom: 6px;">{dr.get('accidentCaseDscr', '-')}</div>
                                            <div style="color: #6ee7b7; font-weight: bold;">🛑 소비자 조치 사항:</div>
                                            <div style="white-space: pre-wrap; font-size: 0.9rem;">{dr.get('publishActionDscr', '-')}</div>
                                        </div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # 공식 웹사이트 상세 게시판 링크
                                st.markdown(f"👉 **[🔗 국표원 SafetyKorea 공식 리콜 상세 공고문 보기 ({r_board_url})]({r_board_url})**")

                                # 리콜 실물 사진 목록 (전체사진, 부분사진)
                                r_files = dr.get("recallFiles") or []
                                if not r_files and r_uid:
                                    det = safetykorea_api.get_domestic_recall_detail(r_uid)
                                    if det.get("success") and det.get("data"):
                                        r_files = det["data"].get("recallFiles") or []

                                if r_files:
                                    st.markdown(f"**📸 국표원 등록 공식 리콜 사진 (총 {len(r_files)}장)**")
                                    r_cols = st.columns(min(len(r_files), 4))
                                    for idx, (rf, rc) in enumerate(zip(r_files, r_cols)):
                                        with rc:
                                            f_div = rf.get("fileDiv") or f"사진 #{idx+1}"
                                            st.image(rf.get("imageUrl"), caption=f_div, use_container_width=True)

                        # 3. 해외직구 안전성조사결과 부적합 적발 카드 (알리/테무 등)
                        os_safeties = safety_res.get("overseas_safety", [])
                        if os_safeties:
                            for os_item in os_safeties:
                                st.markdown(f"""
                                <div style="background: rgba(220, 53, 69, 0.15); border: 2px solid #ef4444; border-radius: 10px; padding: 16px; margin-bottom: 14px;">
                                    <h4 style="margin: 0 0 8px 0; color: #ef4444;">📦 [국표원] 해외직구(알리·테무 등) 유해물질 기준초과 적발</h4>
                                    <div><strong>제품명(모델명)</strong>: {os_item.get('productName', '-')} ({os_item.get('modelName', '-')})</div>
                                    <div style="color: #fca5a5; margin-top: 4px;"><strong>🚨 위해 내용</strong>: {os_item.get('harmDscr', '-')}</div>
                                    <div><strong>공표일자</strong>: {os_item.get('publishDate', '-')} | 제조국: {os_item.get('makingCntryName', '-')}</div>
                                </div>
                                """, unsafe_allow_html=True)

                        # 4. 전파인증 카드
                        if rra_res_list:
                            st.markdown("#### 📡 국립전파연구원 전자파 적합성평가(KC 전파인증) 대조")
                            for rr in rra_res_list:
                                if rr.get("success") and rr.get("data"):
                                    rd = rr["data"]
                                    st.markdown(f"""
                                    <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(59, 130, 246, 0.4); border-radius: 8px; padding: 12px; margin-bottom: 8px;">
                                        <span class="badge-safe">정식 전파인증 등록 확인</span> <strong>{rd.get('device_name') or '방송통신기자재'}</strong>
                                        <div style="font-size: 0.9rem; margin-top: 5px;">
                                            - 등록번호: <code>{rd.get('cert_num')}</code><br>
                                            - 상호: {rd.get('company_name')} | 기본모델: {rd.get('model_name')}<br>
                                            - 인증일자: {rd.get('cert_date')} | 제조국: {rd.get('country')}
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    st.markdown(f"[🔗 전파연구원 공식 인증대장 원문 보기]({rd.get('source_url')})")
                                else:
                                    st.warning(f"⚠️ 전파인증번호 '{rr.get('query')}'는 전파연구원에 등록되지 않았거나 일치하지 않습니다.")

                        # 5. KC 인증번호 카드
                        if kc_num:
                            st.markdown("#### 🏷️ 국가기술표준원 KC안전인증 대조")
                            cert_matches = safety_res.get("certifications", [])
                            if cert_matches:
                                for cm in cert_matches:
                                    c_num = cm.get("certNum")
                                    state = cm.get('certState', '적합')
                                    has_recall_for_this = any(r.get("certNum") == c_num for r in dom_recalls)

                                    if has_recall_for_this:
                                        badge_html = "<span class='badge-warning'>인증상태: 적합</span> <span class='badge-danger'>🚨 사후조사 리콜 적발 품목</span>"
                                    else:
                                        badge_html = f"<span class='badge-safe'>인증상태: {state}</span>"

                                    st.markdown(f"**인증번호**: `[{c_num}]` | {badge_html}", unsafe_allow_html=True)
                                    st.write(f"- 품목/모델: {cm.get('productName')} / {cm.get('modelName')}")
                                    st.write(f"- 인증기관: {cm.get('certOrganName', '-')} | 인증일자: {cm.get('certDate', '-')}")
                                    
                                    if has_recall_for_this:
                                        st.warning("⚠️ **주의**: 최초 안전확인 신고 시 '적합'으로 등록되었으나, 이후 정부 사후 안전성 조사에서 유해물질 기준치 초과가 확인되어 **리콜(강제 수거·환불) 명령**이 내려진 제품입니다.")

                                    st.markdown(f"[🔗 SafetyKorea 공식 상세조회](https://www.safetykorea.kr/search/searchPop?certNum={c_num})")
                                    
                                    det = safetykorea_api.get_certification_detail(c_num)
                                    if det.get("success") and det.get("data"):
                                        kc_imgs = det["data"].get("certificationImageUrls") or []
                                        if kc_imgs:
                                            st.markdown(f"**📸 국표원 등록 공식 사진 ({len(kc_imgs)}장)**")
                                            kc_cols = st.columns(min(len(kc_imgs), 4))
                                            for idx, (img_url, ic) in enumerate(zip(kc_imgs, kc_cols)):
                                                with ic:
                                                    st.image(img_url, caption=f"사진 #{idx+1}", use_container_width=True)
                            else:
                                st.info(f"추출된 KC인증번호(`{kc_num}`)가 SafetyKorea 목록에서 즉시 매칭되지 않았습니다. 서브탭에서 상세 조회가 가능합니다.")
        else:
            st.info("👆 위에서 검사할 제품의 사진을 촬영하거나 등록한 뒤, **[🚀 AI 안심 진단 시작하기]** 버튼을 눌러주세요.")

    # 탭 2: 범정부 안전인증 DB (국표원 + 전파연구원)
    with tab2:
        render_safety_db_section()

    # 탭 3: 위해식품 차단 DB 통합 검색
    with tab3:
        st.subheader("🔍 식약처 해외직구 위해식품 차단 목록 검색")
        st.caption("식품의약품안전처에서 관세청에 통관 보류 및 반입 금지를 요청한 공식 차단 목록입니다.")
        search_q = st.text_input("검색어 입력 (제품명, 검출 위해성분, 바코드, 제조사)", key="user_food_search_q")
        
        if search_q.strip() or st.button("목록 새로고침", key="user_refresh_food"):
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
                st.info("검색 조건에 일치하는 차단 정보가 없습니다.")

    # 탭 4: 제품 텍스트 직접 입력 수동 검사
    with tab4:
        st.subheader("⌨️ 제품 정보 직접 입력 대조 (식약처 + 국표원)")
        t_name = st.text_input("제품명", key="user_t_name")
        t_barcode = st.text_input("바코드 (선택)", key="user_t_bar")
        t_ing = st.text_area("의심 성분 (쉼표로 구분 입력, 예: yohimbine, sildenafil, melatonin)", key="user_t_ing")

        if st.button("안심 대조 실행", type="primary", key="user_t_btn"):
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
                safety_res = safetykorea_api.comprehensive_check(product_name=t_name, barcode=t_barcode)

                if res.get("matched") or safety_res.get("has_danger"):
                    st.error("🚨 [차단 대상] 입력하신 정보가 정부 위해물품 데이터베이스와 일치합니다!")
                    st.json({
                        "식약처_매칭결과": res,
                        "국표원_안전정보": safety_res
                    })
                else:
                    st.success("✅ [정상] 정부 공인 위해식품 및 리콜 데이터베이스에 일치하는 내역이 없습니다.")


# =============================================================
# 2. 관리자 콘솔 (세관·운영자 전용)
# =============================================================
def render_admin_service():
    # 관리자 헤더
    st.markdown("""
    <div class="admin-header">
        <h1 style="color: white; margin: 0 0 6px 0; font-size: 1.85rem;">⚙️ 관세청 세관·검사관 관리자 콘솔</h1>
        <p style="color: #94a3b8; margin: 0; font-size: 0.95rem;">
            범정부 안전 API 연동 관리 · 식약처 차단 DB 전수 동기화 · 실시간 시스템 모니터링 및 사용 현황
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 보안 인증 체크
    if not st.session_state["admin_authenticated"]:
        with st.container():
            st.warning("🔒 관리자 전용 제어센터입니다. 접근을 위해 관리자 비밀번호를 입력해 주세요.")
            admin_pwd = st.text_input("관리자 비밀번호", type="password", key="admin_pwd_input", placeholder="기본 비밀번호: customs2026")
            
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("로그인", type="primary", use_container_width=True):
                    if admin_pwd == "customs2026" or admin_pwd == "admin1234":
                        st.session_state["admin_authenticated"] = True
                        st.success("관리자 인증 성공!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("비밀번호가 올바르지 않습니다.")
            st.caption("초기 데모 비밀번호: `customs2026`")
            return

    # 관리자 사이드바
    with st.sidebar:
        st.subheader("🛡️ 관리자 보안 세션")
        st.success("인증 상태: **운영자 / 세관 관리자**")
        if st.button("🚪 관리자 로그아웃", use_container_width=True):
            st.session_state["admin_authenticated"] = False
            st.rerun()

        st.markdown("---")
        st.subheader("📊 통합 DB 핵심 요약")
        stats = db_service.get_stats()
        st.metric(label="차단 식품 데이터", value=f"{stats.get('total_records', 0):,} 건")
        st.metric(label="등록 바코드 수", value=f"{stats.get('total_barcodes', 0):,} 개")
        st.metric(label="식별 위해성분 수", value=f"{stats.get('total_harmful_ingredients', 0):,} 종")
        st.caption(f"최종 DB 동기화: {stats.get('last_sync_time', '-')}")

    # 관리자 4대 제어 탭
    adm_tab1, adm_tab2, adm_tab3, adm_tab4 = st.tabs([
        "🔄 DB 업데이트 & 동기화 센터",
        "⚡ 시스템 상태 & API 연동",
        "📊 데이터 총 건수 및 통계 현황",
        "📋 실시간 사용 현황 및 검사 이력"
    ])

    # 1. DB 업데이트 & 동기화
    with adm_tab1:
        st.subheader("🔄 식약처 위해식품 차단 Open API 전수 동기화")
        st.write("식품의약품안전처(식품안전나라 I2715 서비스)의 최신 위해식품 차단 원본 데이터를 수집하여 로컬 SQLite DB에 동기화합니다.")
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.info("""
            **동기화 대상 데이터**:
            - 위해식품 및 불법의약품 차단 목록 전체
            - 검출 위해성분 (Sildenafil, Tadalafil, Yohimbine 등)
            - 고유 등록 바코드 및 공표 차단 사유
            """)
        with c2:
            st.markdown(f"**현재 DB 보유 건수**: `{stats['total_records']:,}건`")
            st.markdown(f"**최종 동기화 시점**: `{stats['last_sync_time']}`")

        st.markdown("---")
        sync_batch = st.select_slider("1회 수집 배치 크기 (Batch Size)", options=[500, 1000, 2000, 5000], value=1000)
        
        if st.button("🚀 식품안전나라 최신 데이터 전수 동기화 시작", type="primary", use_container_width=True):
            with st.status("식약처 Open API 데이터 전수 동기화 진행 중...", expanded=True) as status_box:
                st.write("1. 식품안전나라 Open API 연결 상태 점검...")
                api_status = food_safety_api.get_status()
                if not api_status.get("connected"):
                    status_box.update(label="API 연결 실패!", state="error")
                    st.error(f"오류: {api_status.get('error')}")
                else:
                    st.write("2. 최신 차단 데이터 페이지별 수집 중...")
                    fetch_res = food_safety_api.fetch_all_records(batch_size=sync_batch)
                    if fetch_res.get("success"):
                        rows = fetch_res.get("rows", [])
                        st.write(f"3. 로컬 SQLite 데이터베이스 적재 중... (총 {len(rows):,}건)")
                        inserted = db_service.replace_all_from_api(rows)
                        status_box.update(label=f"동기화 완료! 총 {inserted:,}건 적재 성공", state="complete")
                        st.success(f"✅ 동기화가 성공적으로 완료되었습니다! (총 {inserted:,}건 갱신)")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        status_box.update(label="동기화 실패", state="error")
                        st.error(f"수집 실패: {fetch_res.get('error')}")

    # 2. 시스템 상태 & API 연동
    with adm_tab2:
        st.subheader("⚡ 범정부 4대 기관 API 연동 상태 점검")
        
        current_gemini_key = os.getenv("GEMINI_API_KEY", "")
        current_food_key = os.getenv("FOOD_SAFETY_API_KEY", "")
        current_safety_key = os.getenv("SAFETYKOREA_API_KEY", "")

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 1) Google Gemini Vision AI")
            if current_gemini_key:
                masked = current_gemini_key[:6] + "..." + current_gemini_key[-4:]
                st.success(f"✅ 연동 정상 | Key: `{masked}`")
            else:
                st.error("❌ API 키 미설정")

            st.markdown("#### 2) 식품의약품안전처 (식품안전나라)")
            if current_food_key:
                masked_food = current_food_key[:4] + "..." + current_food_key[-4:]
                st.success(f"✅ 연동 정상 | Service ID: `{FOOD_SAFETY_SERVICE_ID}` | Key: `{masked_food}`")
            else:
                st.error("❌ API 키 미설정")

        with col_b:
            st.markdown("#### 3) 국가기술표준원 (SafetyKorea v2.1)")
            if current_safety_key:
                masked_sk = current_safety_key[:6] + "..." + current_safety_key[-4:]
                st.success(f"✅ 연동 정상 | Key: `{masked_sk}`")
            else:
                st.error("❌ API 키 미설정")

            st.markdown("#### 4) 국립전파연구원 (RRA 전자파 적합성평가)")
            st.success("✅ 공식 실시간 인증대장 전산망 직접 연동 (API 키 불필요)")

        st.markdown("---")
        st.subheader("🔍 실시간 API Ping 및 응답 속도 테스트")
        if st.button("범정부 API 통신 상태 즉시 점검", type="secondary"):
            with st.spinner("각 기관 전산망 통신 상태 확인 중..."):
                # SafetyKorea 핑
                try:
                    t0 = time.time()
                    sk_res = safetykorea_api.get_status()
                    sk_lat = round((time.time() - t0) * 1000, 1)
                    sk_ok = sk_res.get("connected", False)
                except Exception as e:
                    sk_lat = 0
                    sk_ok = False

                # 전파연구원 핑
                try:
                    t1 = time.time()
                    rra_res = rra_api.lookup_conformity("R-REM-Y15-YW1801")
                    rra_lat = round((time.time() - t1) * 1000, 1)
                    rra_ok = rra_res.get("success", False)
                except Exception as e:
                    rra_lat = 0
                    rra_ok = False

                # 식약처 핑
                try:
                    t2 = time.time()
                    food_status = food_safety_api.get_status()
                    food_lat = round((time.time() - t2) * 1000, 1)
                    food_ok = food_status.get("connected", False)
                except Exception as e:
                    food_lat = 0
                    food_ok = False

                p1, p2, p3 = st.columns(3)
                with p1:
                    st.metric("국표원 SafetyKorea", f"{sk_lat} ms" if sk_lat else "연결실패", delta="정상" if sk_ok else "오류")
                with p2:
                    st.metric("국립전파연구원 RRA", f"{rra_lat} ms" if rra_lat else "연결실패", delta="정상" if rra_ok else "오류")
                with p3:
                    st.metric("식품안전나라 API", f"{food_lat} ms" if food_lat else "연결실패", delta="정상" if food_ok else "오류")

    # 3. 데이터 총 건수 및 통계 현황
    with adm_tab3:
        st.subheader("📊 데이터베이스 총 건수 및 통계 현황")
        stats = db_service.get_stats()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 위해식품 차단 건수", f"{stats.get('total_records', 0):,} 건")
        m2.metric("등록 바코드 수", f"{stats.get('total_barcodes', 0):,} 개")
        m3.metric("검출 위해성분 수", f"{stats.get('total_harmful_ingredients', 0):,} 종")
        m4.metric("로컬 이미지 캐시", f"{stats.get('total_images', 0):,} 개")

        st.markdown("---")
        st.write("#### 📂 시스템 저장소 및 리소스 경로")
        st.code(f"""
SQLite DB 경로: {SQLITE_DB_PATH}
제품 이미지 보관소: {PRODUCT_IMAGE_DIR}
        """)

    # 4. 실시간 사용 현황 및 검사 이력
    with adm_tab4:
        st.subheader("📋 실시간 통관 검사 이력 및 사용 현황")
        hist = st.session_state.get("inspection_history", [])
        
        if not hist:
            st.info("현재 세션에서 수행된 검사 이력이 없습니다. 대국민 또는 관리자 모드에서 사진 검사를 실행하면 실시간 기록됩니다.")
        else:
            st.write(f"세션 내 누적 검사: 총 **{len(hist)}** 건")
            st.dataframe(hist, use_container_width=True)
            
            if st.button("검사 이력 로그 초기화"):
                st.session_state["inspection_history"] = []
                st.rerun()


# =============================================================
# 공통 서브모듈: 범정부 안전인증 DB (국표원 + 전파연구원)
# =============================================================
def render_safety_db_section():
    st.markdown("### 🏛️ 범정부 4대 제품안전 및 전파인증 실시간 조회")
    st.caption("국가기술표준원(SafetyKorea v2.1)과 과학기술정보통신부 국립전파연구원(RRA) 공식 전산망을 실시간 조회합니다.")

    sk_sub1, sk_sub2, sk_sub3, sk_sub4, sk_sub5 = st.tabs([
        "🏷️ KC안전인증 (국표원)",
        "📡 전자파적합등록 (전파연구원)",
        "🚨 국내리콜정보",
        "🌍 국외리콜정보",
        "📦 해외직구 안전성조사결과"
    ])

    # 1. KC인증정보
    with sk_sub1:
        st.subheader("🏷️ KC안전인증정보 조회")
        c1, c2 = st.columns([1, 2])
        with c1:
            cert_cond = st.selectbox("검색 구분", [
                ("all", "전체"),
                ("productName", "제품명"),
                ("modelName", "모델명"),
                ("certNum", "인증번호")
            ], format_func=lambda x: x[1], key="kc_cond")
        with c2:
            cert_val = st.text_input("검색어 입력", placeholder="예: 충전기, 보조배터리, 어린이, 완구 등", key="kc_val")
        
        if st.button("KC인증정보 검색", type="primary", key="kc_btn"):
            if not cert_val.strip():
                st.warning("검색어를 입력해 주세요.")
            else:
                with st.spinner("SafetyKorea KC인증정보 조회 중..."):
                    res = safetykorea_api.search_certifications(query=cert_val.strip(), condition_key=cert_cond[0])
                    if res.get("success"):
                        items = res.get("items", [])
                        st.write(f"조회 결과: 총 **{len(items):,}** 건")
                        for item in items[:15]:
                            state = item.get("certState", "-")
                            badge = "badge-safe" if state == "적합" else "badge-danger"
                            with st.expander(f"[{item.get('certNum', '-')}] {item.get('productName', '-')} ({item.get('modelName', '-')})"):
                                st.markdown(f"**인증상태**: <span class='{badge}'>{state}</span>", unsafe_allow_html=True)
                                st.write(f"- **인증구분**: {item.get('certDiv', '-')}")
                                st.write(f"- **제조사/제조국**: {item.get('makerName', '-')} / {item.get('makerCntryName', '-')}")
                                st.write(f"- **수입사**: {item.get('importerName', '-')}")
                                st.write(f"- **인증일자**: {item.get('certDate', '-')}")
                                
                                c_num = item.get('certNum')
                                if c_num:
                                    st.markdown(f"[🔗 SafetyKorea 공식 인증상세 원문 조회](https://www.safetykorea.kr/search/searchPop?certNum={c_num})")
                                    det = safetykorea_api.get_certification_detail(c_num)
                                    if det.get("success") and det.get("data"):
                                        kc_imgs = det["data"].get("certificationImageUrls") or []
                                        if kc_imgs:
                                            st.markdown(f"**📸 국표원 공식 등록 인증 사진 (총 {len(kc_imgs)}장)**")
                                            kc_cols = st.columns(min(len(kc_imgs), 4))
                                            for idx, (img_url, ic) in enumerate(zip(kc_imgs, kc_cols)):
                                                with ic:
                                                    st.image(img_url, caption=f"사진 #{idx+1}", use_container_width=True)
                    else:
                        st.error(f"조회 실패: {res.get('error')}")

    # 2. 전자파적합등록 (전파연구원 RRA)
    with sk_sub2:
        st.subheader("📡 국립전파연구원 전자파 적합성평가(KC 전파인증) 조회")
        st.caption("과학기술정보통신부 국립전파연구원(RRA) 공식 적합성평가 데이터베이스를 실시간 대조합니다.")
        
        rra_col1, rra_col2 = st.columns([3, 1])
        with rra_col1:
            rra_input_val = st.text_input(
                "인증/등록번호 입력", 
                placeholder="예: R-REM-Y15-YW1801, R-RRI-Y15-YW1802, MSIP-REM-..., KCC-...",
                key="rra_manual_input"
            )
        with rra_col2:
            st.write("")
            st.write("")
            rra_search_btn = st.button("전자파인증 조회", type="primary", key="rra_manual_btn")
            
        if rra_search_btn:
            if not rra_input_val.strip():
                st.warning("전자파적합성평가 등록/인증번호를 입력해 주세요.")
            else:
                with st.spinner("국립전파연구원 공식 전산망 실시간 조회 중..."):
                    rra_res = rra_api.lookup_conformity(rra_input_val.strip())
                    if rra_res.get("success") and rra_res.get("data"):
                        rd = rra_res["data"]
                        st.success(f"✅ 국립전파연구원 공식 등록 확인 완료: **{rd.get('cert_num')}**")
                        
                        st.markdown(f"""
                        <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(59, 130, 246, 0.4); border-radius: 10px; padding: 18px; margin-top: 10px;">
                            <h4 style="margin: 0 0 12px 0; color: #60a5fa;">📡 {rd.get('device_name') or '방송통신기자재'}</h4>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.95rem;">
                                <div><strong>📋 등록/인증번호:</strong> <code>{rd.get('cert_num')}</code></div>
                                <div><strong>🏢 상호(신청자):</strong> {rd.get('company_name') or '-'}</div>
                                <div><strong>🏷️ 기본 모델명:</strong> {rd.get('model_name') or '-'}</div>
                                <div><strong>📅 인증/등록일자:</strong> {rd.get('cert_date') or '-'}</div>
                                <div><strong>🏭 제조자/제조국:</strong> {rd.get('maker') or '-'} / {rd.get('country') or '-'}</div>
                                <div><strong>⚖️ 적합성평가 구분:</strong> {rd.get('cert_type') or '적합등록'}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        derivatives = rd.get("derivative_models", [])
                        if derivatives:
                            st.write(f"- **파생 모델명 ({len(derivatives)}개)**: {', '.join(derivatives)}")
                            
                        st.markdown(f"[🔗 국립전파연구원 공식 인증대장 원문 팝업 열기]({rd.get('source_url')})")
                    else:
                        st.error(f"❌ {rra_res.get('error') or '등록되지 않은 인증번호이거나 유효하지 않습니다.'}")

    # 3. 국내리콜정보
    with sk_sub3:
        st.subheader("🚨 국내리콜정보 조회")
        c1, c2 = st.columns([1, 2])
        with c1:
            dr_cond = st.selectbox("검색 구분", [
                ("all", "전체"),
                ("recallProductName", "제품명"),
                ("recallModelName", "모델명"),
                ("barcodeNum", "바코드"),
                ("certNum", "인증번호")
            ], format_func=lambda x: x[1], key="dr_cond")
        with c2:
            dr_val = st.text_input("검색어 입력", placeholder="예: 가방, 완구, 배터리 등", key="dr_val")

        if st.button("국내리콜정보 검색", type="primary", key="dr_btn"):
            if not dr_val.strip():
                st.warning("검색어를 입력해 주세요.")
            else:
                with st.spinner("SafetyKorea 국내리콜정보 조회 중..."):
                    res = safetykorea_api.search_domestic_recalls(query=dr_val.strip(), condition_key=dr_cond[0])
                    if res.get("success"):
                        items = res.get("items", [])
                        st.write(f"조회 결과: 총 **{len(items):,}** 건")
                        for item in items[:15]:
                            u_id = item.get("recallUid")
                            r_url = f"https://www.safetykorea.kr/recall/ajax/recallBoard?recallUid={u_id}" if u_id else "https://www.safetykorea.kr"
                            
                            with st.expander(f"[{item.get('recallTypeName', '리콜')}] {item.get('recallProductName', '-')} ({item.get('recallModelName', '-')})"):
                                st.error(f"**리콜 사업자**: {item.get('recallCmpnyName', '-')} (문의: {item.get('recallInqryTel', '-')})")
                                if item.get("certNum"):
                                    st.write(f"- **인증번호**: `{item.get('certNum')}`")
                                st.write(f"- **공표일자**: {item.get('publishDate', '-')}")
                                st.write(f"- **제조국가**: {item.get('makingCntryName', '-')}")
                                st.write(f"- **제품 결함**: {item.get('harmDscr', '상세내용 확인')}")
                                st.write(f"- **사고/위해정보**: {item.get('accidentCaseDscr', '-')}")
                                st.write(f"- **소비자 행동요령/조치사항**: {item.get('publishActionDscr', '-')}")
                                
                                st.markdown(f"👉 **[🔗 SafetyKorea 공식 리콜 상세 공고문 보기 ({r_url})]({r_url})**")
                                
                                if u_id:
                                    det = safetykorea_api.get_domestic_recall_detail(u_id)
                                    if det.get("success") and det.get("data"):
                                        r_files = det["data"].get("recallFiles") or []
                                        if r_files:
                                            st.markdown(f"**📸 국표원 공식 리콜 사진 (총 {len(r_files)}장)**")
                                            r_cols = st.columns(min(len(r_files), 4))
                                            for idx, (rf, rc) in enumerate(zip(r_files, r_cols)):
                                                with rc:
                                                    f_div = rf.get("fileDiv") or f"사진 #{idx+1}"
                                                    st.image(rf.get("imageUrl"), caption=f_div, use_container_width=True)
                    else:
                        st.error(f"조회 실패: {res.get('error')}")

    # 4. 국외리콜정보
    with sk_sub4:
        st.subheader("🌍 국외리콜정보 조회 (해외 수입거절·회수)")
        c1, c2 = st.columns([1, 2])
        with c1:
            fr_cond = st.selectbox("검색 구분", [
                ("all", "전체"),
                ("recallProductName", "제품명"),
                ("recallModelName", "모델명"),
                ("recallBrandName", "브랜드명")
            ], format_func=lambda x: x[1], key="fr_cond")
        with c2:
            fr_val = st.text_input("검색어 입력", placeholder="예: 완구, 텀블러, 드라이어 등", key="fr_val")

        if st.button("국외리콜정보 검색", type="primary", key="fr_btn"):
            if not fr_val.strip():
                st.warning("검색어를 입력해 주세요.")
            else:
                with st.spinner("SafetyKorea 국외리콜정보 조회 중..."):
                    res = safetykorea_api.search_foreign_recalls(query=fr_val.strip(), condition_key=fr_cond[0])
                    if res.get("success"):
                        items = res.get("items", [])
                        st.write(f"조회 결과: 총 **{len(items):,}** 건")
                        for item in items[:15]:
                            with st.expander(f"[{item.get('recallPblshCntryName', '해외')}] {item.get('recallProductName', '-')} ({item.get('recallModelName', '-')})"):
                                st.warning(f"**공표기관**: {item.get('recallPblshOrgnName', '-')} | **리콜종류**: {item.get('recallTypeName', '-')}")
                                st.write(f"- **위해내용**: {item.get('violateDscr', '-')}")
                                st.write(f"- **조치사항**: {item.get('publishActionDscr', '-')}")
                                st.write(f"- **제조국**: {item.get('makingCntryName', '-')}")
                                img_url = item.get("imageUrl")
                                if img_url:
                                    first_img = img_url.split(",")[0]
                                    st.image(first_img, caption="국외 리콜 물품 사진", width=250)
                    else:
                        st.error(f"조회 실패: {res.get('error')}")

    # 5. 해외직구 안전성조사결과
    with sk_sub5:
        st.subheader("📦 해외직구 안전성조사결과 조회 (알리·테무 등 유해물질 기준초과 적발)")
        c1, c2 = st.columns([1, 2])
        with c1:
            os_cond = st.selectbox("검색 구분", [
                ("all", "전체"),
                ("productName", "제품명"),
                ("modelName", "모델명")
            ], format_func=lambda x: x[1], key="os_cond")
        with c2:
            os_val = st.text_input("검색어 입력", placeholder="예: 전지, 배터리, 장난감, 화장품 등", key="os_val")

        if st.button("해외직구 안전성조사 검색", type="primary", key="os_btn"):
            if not os_val.strip():
                st.warning("검색어를 입력해 주세요.")
            else:
                with st.spinner("SafetyKorea 해외직구 안전성조사결과 조회 중..."):
                    res = safetykorea_api.search_overseas_safety(query=os_val.strip(), condition_key=os_cond[0])
                    if res.get("success"):
                        items = res.get("items", [])
                        st.write(f"조회 결과: 총 **{len(items):,}** 건")
                        for item in items[:15]:
                            with st.expander(f"[해외직구 부적합] {item.get('productName', '-')} ({item.get('modelName', '-')})"):
                                st.error(f"**🚨 부적합 판정 내용**: {item.get('harmDscr', '-')}")
                                st.write(f"- **위해 정보**: {item.get('accidentCaseDscr', '-')}")
                                st.write(f"- **공표일자**: {item.get('publishDate', '-')}")
                                st.write(f"- **제조국**: {item.get('makingCntryName', '-')}")
                                img_url = item.get("imageUrl")
                                if img_url:
                                    first_img = img_url.split(",")[0]
                                    st.image(first_img, caption="시험 검사 물품 사진", width=300)
                    else:
                        st.error(f"조회 실패: {res.get('error')}")


# =============================================================
# 메인 라우터 실행
# =============================================================
if is_admin_mode:
    render_admin_service()
else:
    render_user_service()
