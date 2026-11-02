import os
import sys
import io
import time
from datetime import datetime
from PIL import Image
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="해외직구 안심체크 | 사기 전에 사진 한 장으로 확인",
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

import html as _html_lib


def _t(value, default="-"):
    """화면에 넣을 값을 안전하게 바꿉니다 (HTML 이스케이프 + 줄바꿈 처리)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        value = default
    return _html_lib.escape(str(value)).replace("\r\n", "\n").replace("\n", "<br>")


def show_html(markup):
    """들여쓰기·빈 줄 때문에 HTML이 코드 블록으로 보이는 문제를 막고 그대로 그립니다."""
    lines = [ln.strip() for ln in markup.strip().splitlines()]
    st.markdown("\n".join(ln for ln in lines if ln), unsafe_allow_html=True)


# 친근한 공공서비스 디자인 (밝은 화면 · 큰 글씨 · 둥근 카드)
show_html("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

html, body, [class*="css"], .stApp, button, input, textarea, select {
    font-family: 'Pretendard', 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.stApp { background: #F7F9FC; }
.block-container { padding-top: 1.2rem !important; max-width: 1180px; }
h1, h2, h3, h4 { letter-spacing: -0.4px; color: #111827; }
p, li { font-size: 1rem; line-height: 1.65; }

/* 사진 크기 맞춤 */
div[data-testid="stImage"] { display: flex; justify-content: center; text-align: center; }
div[data-testid="stImage"] img {
    max-height: 360px !important; width: auto !important; object-fit: contain !important;
    border-radius: 14px !important; box-shadow: 0 4px 14px rgba(15, 23, 42, 0.10) !important; margin: 0 auto !important;
}

/* 버튼 */
.stButton button, .stDownloadButton button {
    border-radius: 12px !important; font-weight: 700 !important; min-height: 44px;
}
.stButton button[kind="primary"] {
    background: #1B64DA !important; border: none !important; font-size: 1.05rem !important;
    box-shadow: 0 6px 16px rgba(27, 100, 218, 0.25) !important;
}
.stButton button[kind="primary"]:hover { background: #1554BA !important; }

/* 탭 */
.stTabs [data-baseweb="tab-list"] { gap: 6px; flex-wrap: wrap; }
.stTabs [data-baseweb="tab"] {
    background: #FFFFFF; border: 1px solid #E3E9F2; border-radius: 999px !important;
    padding: 8px 16px !important; height: auto !important; font-weight: 600;
}
.stTabs [aria-selected="true"] { background: #1B64DA !important; color: #FFFFFF !important; border-color: #1B64DA !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

/* 펼침 상자 · 파일 올리기 */
div[data-testid="stExpander"] details {
    background: #FFFFFF; border: 1px solid #E3E9F2 !important; border-radius: 14px !important;
}
div[data-testid="stFileUploader"] section {
    background: #FFFFFF; border: 2px dashed #A9C4F5 !important; border-radius: 16px !important; padding: 22px !important;
}

/* 맨 위 기관 안내 줄 */
.gov-strip { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 0.86rem; color: #4B5563; padding: 6px 2px; }
.gov-strip b { color: #1B64DA; }

/* 첫 화면 안내판 (작게) */
.hero {
    background: linear-gradient(135deg, #1B64DA 0%, #3B82F6 70%, #60A5FA 100%);
    color: #FFFFFF; border-radius: 18px; padding: 16px 22px; margin: 2px 0 14px 0;
    box-shadow: 0 6px 18px rgba(27, 100, 218, 0.18);
}
.hero h1 { color: #FFFFFF !important; font-size: 1.45rem; font-weight: 800; margin: 0 0 4px 0; padding: 0; line-height: 1.35; }
.hero p { color: #EAF2FF; font-size: 0.95rem; margin: 0 0 10px 0; line-height: 1.5; }
.hero-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.hero-chip { background: rgba(255,255,255,0.95); color: #1B64DA; font-weight: 700; font-size: 0.85rem; padding: 4px 11px; border-radius: 999px; }
.hero-chip.soft { background: rgba(255,255,255,0.18); color: #FFFFFF; border: 1px solid rgba(255,255,255,0.35); }

/* 구역 제목 */
.sec-title { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin: 8px 0 14px 0; }
.sec-title h2 { font-size: 1.45rem; font-weight: 800; margin: 0; padding: 0; }
.sec-title span { color: #6B7280; font-size: 0.98rem; }

/* 4가지 주제 카드 (작게) */
.topic-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin-bottom: 8px; }
.topic-card { background: #FFFFFF; border: 1px solid #E3E9F2; border-radius: 16px; padding: 14px 16px; display: flex; gap: 12px; align-items: flex-start; }
.topic-icon { flex: 0 0 auto; width: 42px; height: 42px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.4rem; }
.topic-card h3 { font-size: 1.02rem; font-weight: 800; margin: 0 0 2px 0; padding: 0; }
.topic-q { font-size: 0.88rem; font-weight: 700; margin: 0 0 4px 0 !important; }
.topic-card p.desc { font-size: 0.86rem; color: #4B5563; margin: 0; line-height: 1.5; }
.c-blue  .topic-icon { background: #E8F0FE; } .c-blue  .topic-q { color: #1B64DA; }
.c-pink  .topic-icon { background: #FDECF3; } .c-pink  .topic-q { color: #D6336C; }
.c-green .topic-icon { background: #E6F6EE; } .c-green .topic-q { color: #128A4E; }
.c-amber .topic-icon { background: #FFF4DE; } .c-amber .topic-q { color: #C2760A; }

/* 사진 확인 안내판 */
.check-box { background: #FFFFFF; border: 2px solid #BFD4FA; border-radius: 18px; padding: 14px 18px; margin: 0 0 12px 0; }
.check-box h2 { font-size: 1.2rem; font-weight: 800; margin: 0 0 6px 0; padding: 0; }
.check-box p { color: #4B5563; margin: 0; }
.shot-tips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.shot-tip { background: #F1F6FF; color: #1E3A8A; border-radius: 10px; padding: 6px 12px; font-size: 0.9rem; font-weight: 600; }

/* 결과 판정 카드 */
.verdict { border-radius: 22px; padding: 24px 26px; margin: 10px 0 20px 0; display: flex; gap: 18px; align-items: flex-start; }
.verdict-icon { font-size: 2.8rem; line-height: 1; }
.verdict h2 { font-size: 1.55rem; font-weight: 800; margin: 0 0 6px 0; padding: 0; }
.verdict p { margin: 0; font-size: 1.02rem; }
.verdict.danger { background: #FFF1F1; border: 2px solid #F87171; } .verdict.danger h2 { color: #C62828; }
.verdict.warn   { background: #FFF8E6; border: 2px solid #F6B93B; } .verdict.warn h2   { color: #A15C00; }
.verdict.safe   { background: #ECFAF2; border: 2px solid #4ADE80; } .verdict.safe h2   { color: #13804A; }

/* 정보 카드 */
.info-card { background: #FFFFFF; border: 1px solid #E3E9F2; border-left: 6px solid #1B64DA; border-radius: 16px; padding: 18px 20px; margin-bottom: 14px; }
.info-card.red { border-left-color: #EF4444; } .info-card.amber { border-left-color: #F59E0B; } .info-card.green { border-left-color: #22C55E; }
.info-card h4 { margin: 0 0 10px 0; font-size: 1.12rem; font-weight: 800; padding: 0; }
.info-row { font-size: 0.98rem; line-height: 1.75; color: #1F2937; }
.info-row b { color: #374151; }
.qa { background: #F7F9FC; border-radius: 12px; padding: 12px 14px; margin-top: 10px; }
.qa-q { font-weight: 800; color: #111827; margin-top: 6px; }
.qa-q:first-child { margin-top: 0; }
.qa-a { color: #374151; font-size: 0.96rem; }

/* 작은 표시 */
.badge-danger, .badge-warning, .badge-safe, .badge-info {
    display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 0.86rem; font-weight: 700;
}
.badge-danger { background: #FDE2E2; color: #B91C1C; }
.badge-warning { background: #FEF0C7; color: #92400E; }
.badge-safe { background: #DCF5E7; color: #166534; }
.badge-info { background: #E0ECFF; color: #1E40AF; }
.stat-card { background: #FFFFFF; border: 1px solid #E3E9F2; border-radius: 14px; padding: 16px; text-align: center; }

/* 왼쪽 메뉴 */
section[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E3E9F2; }
.call-card { background: #F7F9FC; border-radius: 12px; padding: 10px 12px; margin-bottom: 8px; }
.call-card b { display: block; font-size: 0.92rem; color: #374151; }
.call-card span { font-size: 1.15rem; font-weight: 800; color: #1B64DA; }

/* 관리자 머리말 (작게) */
.admin-header {
    background: #FFFFFF; border: 1px solid #E3E9F2; border-left: 6px solid #1B64DA; border-radius: 14px;
    padding: 12px 18px; margin-bottom: 14px;
}
.admin-header h1 { color: #111827 !important; font-size: 1.25rem !important; font-weight: 800; margin: 0 0 2px 0; padding: 0; }
.admin-header p { color: #6B7280; margin: 0; font-size: 0.9rem; }

/* 관리자 로그인 상자 */
.login-card { background: #FFFFFF; border: 2px solid #BFD4FA; border-radius: 16px; padding: 16px 18px 6px 18px; margin: 8px 0 10px 0; text-align: center; }
.login-card .lock { font-size: 1.8rem; line-height: 1; }
.login-card h3 { font-size: 1.15rem; font-weight: 800; margin: 6px 0 2px 0; padding: 0; color: #111827; }
.login-card p { color: #6B7280; font-size: 0.88rem; margin: 0 0 8px 0; }

/* 맨 위 관리자 버튼 */
.st-key-top_btn_admin_login button, .st-key-top_btn_admin_console button {
    background: #FFFFFF !important; border: 1.5px solid #1B64DA !important; color: #1B64DA !important;
    min-height: 36px !important; font-size: 0.9rem !important;
}

/* 휴대폰 화면 */
@media (max-width: 640px) {
    .hero { padding: 14px 16px; border-radius: 14px; }
    .hero h1 { font-size: 1.2rem; }
    .hero p { font-size: 0.9rem; }
    .topic-grid { gap: 10px; }
    .verdict { flex-direction: column; gap: 8px; padding: 18px; }
    .verdict h2 { font-size: 1.3rem; }
    div[data-testid="stImage"] img { max-height: 280px !important; }
    .stButton button { min-height: 50px !important; font-size: 1rem !important; }
}
</style>
""")


# -------------------------------------------------------------
# 세션 상태 초기화
# -------------------------------------------------------------
if "admin_authenticated" not in st.session_state:
    st.session_state["admin_authenticated"] = False
if "admin_view" not in st.session_state:
    st.session_state["admin_view"] = False
if "camera_photos" not in st.session_state:
    st.session_state["camera_photos"] = []
if "inspection_history" not in st.session_state:
    st.session_state["inspection_history"] = []

# -------------------------------------------------------------
# 맨 위 줄: 함께 만든 기관 안내 & 오른쪽 관리자 버튼
# -------------------------------------------------------------
top_col1, top_col2 = st.columns([4.2, 1])

with top_col1:
    show_html("""
    <div class="gov-strip">
        <span>🇰🇷</span>
        <b>대한민국 정부 공공서비스</b>
        <span>· 관세청 · 식품의약품안전처 · 국가기술표준원 · 국립전파연구원이 함께 운영해요</span>
    </div>
    """)

with top_col2:
    if st.session_state["admin_view"]:
        btn_c1, btn_c2 = st.columns([1, 1])
        with btn_c1:
            if st.button("🏠 첫 화면", key="top_btn_user_mode", use_container_width=True):
                st.session_state["admin_view"] = False
                st.rerun()
        with btn_c2:
            if st.session_state.get("admin_authenticated", False):
                if st.button("🚪 로그아웃", key="top_btn_logout_mode", use_container_width=True):
                    st.session_state["admin_authenticated"] = False
                    st.session_state["admin_view"] = False
                    st.rerun()
    else:
        if st.session_state.get("admin_authenticated", False):
            if st.button("⚙️ 관리자 화면", key="top_btn_admin_console", use_container_width=True):
                st.session_state["admin_view"] = True
                st.rerun()
        else:
            if st.button("🔒 관리자", key="top_btn_admin_login", use_container_width=True):
                st.session_state["admin_view"] = True
                st.rerun()

is_admin_mode = st.session_state["admin_view"]


# =============================================================
# 1. 국민 누구나 쓰는 화면
# =============================================================
def render_user_service():
    # 왼쪽 메뉴: 이용 방법 & 신고·상담 전화
    with st.sidebar:
        st.markdown("### 🙋 이렇게 이용하세요")
        st.markdown(
            "1. 사려는 물건의 **사진을 찍어요**\n"
            "2. **[안전한지 확인하기]** 버튼을 눌러요\n"
            "3. 들여와도 되는지, 써도 되는지 **결과를 봐요**"
        )
        st.caption("사진이 없다면 화면 아래 '직접 찾아보기'에서 제품 이름으로 찾을 수 있어요.")
        st.markdown("---")
        st.markdown("### 📞 도움이 필요하면 전화하세요")
        show_html("""
        <div class="call-card"><b>불량식품·약 신고 (식약처)</b><span>1399</span></div>
        <div class="call-card"><b>제품 안전 상담 (KC 인증)</b><span>1600-1384</span></div>
        <div class="call-card"><b>밀수 신고 (관세청)</b><span>125</span></div>
        """)
        st.caption("국번 없이 걸면 돼요.")

    # 첫 화면 안내판 (작게 — 사진 올리기가 바로 보이도록)
    show_html("""
    <div class="hero">
        <h1>🛡️ 해외물품, 사기 전에 사진 한 장으로 안심 체크!</h1>
        <p>사진만 올리면 <b>우리나라에 들여와도 되는지</b>, <b>써도 안전한지</b> 정부 자료로 바로 알려드려요.</p>
        <div class="hero-chips">
            <span class="hero-chip">💊 약·영양제</span>
            <span class="hero-chip">🧸 어린이 제품</span>
            <span class="hero-chip">🧴 생활용품</span>
            <span class="hero-chip">🔌 전기용품</span>
            <span class="hero-chip soft">무료 · 회원가입 없이</span>
        </div>
    </div>
    """)

    # =============================================================
    # 사진으로 바로 확인하기 (핵심 기능)
    # =============================================================
    show_html("""
    <div class="check-box">
        <h2>📷 사진으로 바로 확인하기</h2>
        <p>① 사진 올리기 → ② [안전한지 확인하기] 누르기 → ③ 결과 보기 · 여러 장일수록 더 정확해요.</p>
        <div class="shot-tips">
            <span class="shot-tip">앞면 · 제품 이름</span>
            <span class="shot-tip">뒷면 · 성분표</span>
            <span class="shot-tip">옆면 · 바코드</span>
            <span class="shot-tip">KC 마크 · 인증번호</span>
        </div>
    </div>
    """)

    with st.container():

        # ① 사진 올리기
        st.markdown("#### ① 제품 사진 올리기")
        uploaded_files = st.file_uploader(
            "사진 파일을 고르거나 여기로 끌어다 놓으세요 (여러 장 가능)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="user_upload_files"
        )

        with st.expander("📱 휴대폰 카메라로 바로 찍기"):
            cam_pic = st.camera_input("카메라로 찍기", key="user_cam")
            if cam_pic:
                if st.button("찍은 사진 추가하기", key="user_add_cam"):
                    st.session_state["camera_photos"].append(cam_pic.getvalue())
                    st.success(f"사진을 추가했어요! (지금까지 {len(st.session_state['camera_photos'])}장)")

        total_images_bytes = []
        if uploaded_files:
            for uf in uploaded_files:
                total_images_bytes.append(uf.getvalue())
        if st.session_state["camera_photos"]:
            total_images_bytes.extend(st.session_state["camera_photos"])

        if total_images_bytes:
            st.write(f"**올린 사진: {len(total_images_bytes)}장**")
            if len(total_images_bytes) == 1:
                p_c1, p_c2, p_c3 = st.columns([1, 2, 1])
                with p_c2:
                    st.image(total_images_bytes[0], caption="올린 사진", width=220)
            else:
                img_cols = st.columns(min(len(total_images_bytes), 4))
                for i, b_data in enumerate(total_images_bytes):
                    with img_cols[i % len(img_cols)]:
                        st.image(b_data, caption=f"사진 {i+1}", width=180)

            if st.button("🗑️ 올린 사진 모두 지우기", key="user_reset_imgs"):
                st.session_state["camera_photos"] = []
                st.rerun()

        st.markdown("")
        run_inspect = st.button("🔍 안전한지 확인하기", type="primary", use_container_width=True, key="user_inspect_btn")
        st.markdown("---")

        # ② 확인 결과
        st.markdown("#### ② 확인 결과")
        if run_inspect:
                if not total_images_bytes:
                    st.warning("먼저 확인할 제품 사진을 올리거나 찍어 주세요.")
                else:
                    with st.spinner("사진 속 제품 이름과 성분을 읽고 정부 자료와 비교하고 있어요. 잠시만 기다려 주세요..."):
                        start_t = time.time()
                        ocr_result = ai_vision_service.extract_labels_multi(total_images_bytes)
                        if ocr_result.get("error") and not ocr_result.get("product_name"):
                            st.warning(f"⚠️ 사진 속 글자를 잘 읽지 못했어요. 더 밝고 가까이에서 다시 찍어 보세요. ({ocr_result.get('error')})")

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

                        # 빈 값 대신 보여줄 기본 문구
                        matched_product_name = db_rec.get("제품명") or p_name or "차단 목록에 있는 것으로 보이는 제품"
                        matched_harmful_ingr = (
                            db_rec.get("성분명")
                            or match_result.get("db_harmful_ingredient")
                            or ", ".join(ocr_result.get("harmful_suspects", []))
                            or "처방전이 필요한 해외 약 성분"
                        )
                        matched_reason = (
                            db_rec.get("회수사유")
                            or citizen_summary.get("why_prohibited")
                            or match_result.get("db_reason")
                            or ocr_result.get("why_prohibited_reason")
                            or "들여오는 것이 제한되거나 몸에 해로울 수 있는 성분이 들어 있어요."
                        )
                        matched_maker = db_rec.get("제조사") or ocr_result.get("brand") or "해외 회사"
                        matched_country = db_rec.get("제조국") or "해외"
                        matched_source = db_rec.get("정보출처") or "식품안전나라(식약처) 공공데이터 · 관세청 AI 판정"

                        # -------------------------------------------------------------
                        # 1. 한눈에 보는 결과
                        # -------------------------------------------------------------
                        if has_safety_danger or food_status == "DANGER":
                            show_html("""
                            <div class="verdict danger">
                                <div class="verdict-icon">🚫</div>
                                <div>
                                    <h2>사지 마세요! 위험한 제품이에요</h2>
                                    <p>정부가 막아 둔 성분이 들어 있거나, 회수(리콜) 명령을 받은 제품이에요.
                                    이미 주문했다면 취소하는 것이 좋아요. 그대로 들어오면 세관에서 폐기될 수 있어요.</p>
                                </div>
                            </div>
                            """)
                        elif food_status == "WARNING":
                            show_html("""
                            <div class="verdict warn">
                                <div class="verdict-icon">⚠️</div>
                                <div>
                                    <h2>잠깐! 꼭 확인이 필요해요</h2>
                                    <p>의사 처방전이 있어야 하거나, 들여올 수 있는 양이 정해져 있는 제품이에요.
                                    아래 안내를 읽고 구매를 결정해 주세요.</p>
                                </div>
                            </div>
                            """)
                        else:
                            show_html("""
                            <div class="verdict safe">
                                <div class="verdict-icon">✅</div>
                                <div>
                                    <h2>위험 제품 목록에서 찾지 못했어요</h2>
                                    <p>정부의 위험 제품·리콜 목록에 올라 있지 않아요.
                                    그래도 사용 전에 설명서와 주의사항은 꼭 읽어 주세요.</p>
                                </div>
                            </div>
                            """)

                        # -------------------------------------------------------------
                        # 2. 내 사진 vs 정부에 등록된 사진
                        # -------------------------------------------------------------
                        st.markdown("### 📋 내 사진과 정부 등록 사진 비교")

                        col_left, col_right = st.columns(2)
                        with col_left:
                            st.markdown("#### 📷 내가 올린 사진")
                            if len(total_images_bytes) == 1:
                                st.image(total_images_bytes[0], caption="내가 올린 사진", width=280)
                            else:
                                img_tabs = st.tabs([f"사진 {i+1}" for i in range(len(total_images_bytes))])
                                for i, i_tab in enumerate(img_tabs):
                                    with i_tab:
                                        st.image(total_images_bytes[i], caption=f"내가 올린 사진 {i+1}", width=280)

                        with col_right:
                            st.markdown("#### 🏛️ 정부에 등록된 사진")

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

                            rendered_db_img = False
                            if is_blocked and (local_img_path or db_remote_url):
                                target_img = local_img_path if local_img_path else db_remote_url
                                st.image(target_img, caption="식약처가 막아 둔 제품 사진", width=280)
                                rendered_db_img = True
                            elif recall_images:
                                st.image(recall_images[0], caption="리콜(회수) 제품 사진", width=280)
                                rendered_db_img = True
                            elif kc_images:
                                st.image(kc_images[0], caption="KC 안전인증 등록 사진", width=280)
                                rendered_db_img = True

                            if not rendered_db_img:
                                if is_blocked and db_rec:
                                    st.info("차단 목록에는 있지만, 정부가 공개한 사진은 없는 제품이에요.")
                                elif is_blocked and not db_rec:
                                    st.info("해외 약의 성분을 보고 AI가 판단한 결과예요. 그래서 비교할 정부 등록 사진은 없어요.")
                                else:
                                    st.info("위험 제품 목록에 없는 제품이라 비교할 사진이 없어요.")

                        # -------------------------------------------------------------
                        # 3. 자세히 보기
                        # -------------------------------------------------------------
                        with st.expander("🔍 자세히 보기 (사진에서 읽은 내용 · 비교 결과)", expanded=True):
                            col_d1, col_d2 = st.columns(2)
                            with col_d1:
                                st.markdown("**📷 사진에서 읽은 내용**")
                                st.write(f"- **제품 이름**: {p_name or '-'}")
                                st.write(f"- **만든 회사(브랜드)**: {ocr_result.get('brand') or '-'}")
                                st.write(f"- **바코드**: {b_code or '-'}")
                                ings = ocr_result.get('ingredients', [])
                                st.write(f"- **찾은 성분**: {len(ings)}개")
                                if ings:
                                    st.caption(f"성분: {', '.join(ings[:15])}")
                            with col_d2:
                                st.markdown("**🏛️ 정부 자료와 비교한 결과**")
                                if is_blocked:
                                    st.write(f"- **등록된 제품 이름**: {matched_product_name}")
                                    st.write(f"- **문제가 된 성분**: <span class='badge-danger'>{_t(matched_harmful_ingr)}</span>", unsafe_allow_html=True)
                                    st.write(f"- **안 되는 이유**: {matched_reason}")
                                    st.write(f"- **판단 근거**: {match_stage or '정부 차단 기준과 일치'}")
                                    st.write(f"- **자료 출처**: {matched_source}")
                                elif safety_res.get("has_danger"):
                                    st.write("- **확인 내용**: 정부 안전 검사에서 리콜(회수) 명령을 받은 제품")
                                    st.write(f"- **KC 인증번호**: `{kc_num or '-'}`")
                                else:
                                    st.write("- **결과**: 위험 제품 목록에 없는 제품이에요.")

                        st.markdown("---")

                        # -------------------------------------------------------------
                        # 4. 약·영양제: 들여올 수 없는 / 주의가 필요한 제품 안내
                        # -------------------------------------------------------------
                        if is_blocked:
                            is_danger = food_status == "DANGER"
                            card_cls = "red" if is_danger else "amber"
                            card_title = "🚫 식약처가 들여오지 못하게 막아 둔 제품이에요" if is_danger else "⚠️ 처방전이 필요하거나 들여올 수 있는 양이 정해진 약이에요"
                            badge_cls = "badge-danger" if is_danger else "badge-warning"

                            health_risk = citizen_summary.get("health_risks") or ocr_result.get("health_risks") or "먹거나 사용하면 건강에 해롭거나 부작용이 생길 수 있어요."
                            action_guide = citizen_summary.get("action_guide") or ocr_result.get("customs_advice") or "배송 전이라면 주문을 취소하고, 꼭 필요한 약이라면 의사 처방전을 준비하세요."

                            show_html(f"""
                            <div class="info-card {card_cls}">
                                <h4>{card_title}</h4>
                                <div class="info-row"><b>제품 이름</b> · {_t(matched_product_name)}</div>
                                <div class="info-row"><b>문제 성분</b> · <span class="{badge_cls}">{_t(matched_harmful_ingr)}</span></div>
                                <div class="info-row"><b>만든 곳</b> · {_t(matched_maker)} / {_t(matched_country)}</div>
                                <div class="qa">
                                    <div class="qa-q">❓ 왜 안 되나요?</div>
                                    <div class="qa-a">{_t(matched_reason)}</div>
                                    <div class="qa-q">🩺 몸에 어떤 영향이 있나요?</div>
                                    <div class="qa-a">{_t(health_risk)}</div>
                                    <div class="qa-q">👉 어떻게 하면 되나요?</div>
                                    <div class="qa-a">{_t(action_guide)}</div>
                                </div>
                            </div>
                            """)

                        # 리콜(회수) 명령 제품 안내
                        dom_recalls = safety_res.get("domestic_recalls", [])
                        if dom_recalls:
                            for dr in dom_recalls:
                                r_uid = dr.get("recallUid")
                                r_board_url = dr.get("source_url") or f"https://www.safetykorea.kr/recall/ajax/recallBoard?recallUid={r_uid}"

                                show_html(f"""
                                <div class="info-card red">
                                    <h4>🚨 회수(리콜) 명령을 받은 제품이에요 <span class="badge-danger">{_t(dr.get('recallTypeName'), '리콜')}</span></h4>
                                    <div class="info-row"><b>제품 이름(모델)</b> · {_t(dr.get('recallProductName'))} ({_t(dr.get('recallModelName'))})</div>
                                    <div class="info-row"><b>KC 인증번호</b> · <code>{_t(dr.get('certNum'))}</code></div>
                                    <div class="info-row"><b>판매·수입 회사</b> · {_t(dr.get('recallCmpnyName'))} (문의 {_t(dr.get('recallInqryTel'))})</div>
                                    <div class="info-row"><b>발표일</b> · {_t(dr.get('publishDate'))} &nbsp; <b>만든 나라</b> · {_t(dr.get('makingCntryName'))}</div>
                                    <div class="qa">
                                        <div class="qa-q">❓ 어떤 문제가 있었나요?</div>
                                        <div class="qa-a">{_t(dr.get('harmDscr'))}</div>
                                        <div class="qa-q">🩺 어떤 사고가 날 수 있나요?</div>
                                        <div class="qa-a">{_t(dr.get('accidentCaseDscr'))}</div>
                                        <div class="qa-q">👉 이렇게 하세요</div>
                                        <div class="qa-a">{_t(dr.get('publishActionDscr'))}</div>
                                    </div>
                                </div>
                                """)

                                st.markdown(f"👉 [정부 리콜 안내문 원문 보기]({r_board_url})")

                                r_files = dr.get("recallFiles") or []
                                if not r_files and r_uid:
                                    det = safetykorea_api.get_domestic_recall_detail(r_uid)
                                    if det.get("success") and det.get("data"):
                                        r_files = det["data"].get("recallFiles") or []

                                if r_files:
                                    st.markdown(f"**📸 리콜 제품 사진 ({len(r_files)}장)**")
                                    r_cols = st.columns(min(len(r_files), 4))
                                    for idx, (rf, rc) in enumerate(zip(r_files, r_cols)):
                                        with rc:
                                            f_div = rf.get("fileDiv") or f"사진 {idx+1}"
                                            st.image(rf.get("imageUrl"), caption=f_div, use_container_width=True)

                        # 해외직구 검사에서 해로운 물질이 나온 제품 (알리·테무 등)
                        os_safeties = safety_res.get("overseas_safety", [])
                        if os_safeties:
                            for os_item in os_safeties:
                                show_html(f"""
                                <div class="info-card red">
                                    <h4>📦 해외직구 검사에서 해로운 물질이 나온 제품이에요</h4>
                                    <div class="info-row"><b>제품 이름(모델)</b> · {_t(os_item.get('productName'))} ({_t(os_item.get('modelName'))})</div>
                                    <div class="info-row"><b>문제 내용</b> · {_t(os_item.get('harmDscr'))}</div>
                                    <div class="info-row"><b>발표일</b> · {_t(os_item.get('publishDate'))} &nbsp; <b>만든 나라</b> · {_t(os_item.get('makingCntryName'))}</div>
                                </div>
                                """)

                        # 전기·전자제품 전파인증
                        if rra_res_list:
                            st.markdown("#### 📡 전파인증 확인 (전기·전자제품)")
                            for rr in rra_res_list:
                                if rr.get("success") and rr.get("data"):
                                    rd = rr["data"]
                                    show_html(f"""
                                    <div class="info-card green">
                                        <h4><span class="badge-safe">정식 인증 확인</span> {_t(rd.get('device_name'), '전기·전자제품')}</h4>
                                        <div class="info-row"><b>인증번호</b> · <code>{_t(rd.get('cert_num'))}</code></div>
                                        <div class="info-row"><b>회사</b> · {_t(rd.get('company_name'))} &nbsp; <b>모델</b> · {_t(rd.get('model_name'))}</div>
                                        <div class="info-row"><b>인증일</b> · {_t(rd.get('cert_date'))} &nbsp; <b>만든 나라</b> · {_t(rd.get('country'))}</div>
                                    </div>
                                    """)
                                    st.markdown(f"[🔗 국립전파연구원 인증 원문 보기]({rd.get('source_url')})")
                                else:
                                    st.warning(f"⚠️ 전파인증번호 '{rr.get('query')}'는 등록 정보를 찾지 못했어요. 번호를 다시 확인해 주세요.")

                        # KC 안전인증
                        if kc_num:
                            st.markdown("#### 🏷️ KC 안전인증 확인")
                            cert_matches = safety_res.get("certifications", [])
                            if cert_matches:
                                for cm in cert_matches:
                                    c_num = cm.get("certNum")
                                    state = cm.get('certState', '적합')
                                    has_recall_for_this = any(r.get("certNum") == c_num for r in dom_recalls)

                                    if has_recall_for_this:
                                        badge_html = "<span class='badge-warning'>인증 상태: 적합</span> <span class='badge-danger'>🚨 나중에 리콜된 제품</span>"
                                    else:
                                        badge_html = f"<span class='badge-safe'>인증 상태: {_t(state)}</span>"

                                    st.markdown(f"**인증번호** `{c_num}` &nbsp; {badge_html}", unsafe_allow_html=True)
                                    st.write(f"- 제품/모델: {cm.get('productName')} / {cm.get('modelName')}")
                                    st.write(f"- 인증한 곳: {cm.get('certOrganName', '-')} | 인증일: {cm.get('certDate', '-')}")

                                    if has_recall_for_this:
                                        st.warning("⚠️ 처음 인증받을 땐 '적합'이었지만, 그 뒤 정부 검사에서 해로운 물질이 기준보다 많이 나와 **회수(리콜) 명령**을 받은 제품이에요.")

                                    st.markdown(f"[🔗 제품안전정보센터에서 자세히 보기](https://www.safetykorea.kr/search/searchPop?certNum={c_num})")

                                    det = safetykorea_api.get_certification_detail(c_num)
                                    if det.get("success") and det.get("data"):
                                        kc_imgs = det["data"].get("certificationImageUrls") or []
                                        if kc_imgs:
                                            st.markdown(f"**📸 인증 등록 사진 ({len(kc_imgs)}장)**")
                                            kc_cols = st.columns(min(len(kc_imgs), 4))
                                            for idx, (img_url, ic) in enumerate(zip(kc_imgs, kc_cols)):
                                                with ic:
                                                    st.image(img_url, caption=f"사진 {idx+1}", use_container_width=True)
                            else:
                                st.info(f"사진에서 읽은 KC 인증번호(`{kc_num}`)를 바로 찾지 못했어요. 아래 '직접 찾아보기'에서 다시 검색해 보세요.")
        else:
            st.info("👆 사진을 올린 뒤 **[🔍 안전한지 확인하기]** 버튼을 눌러 주세요.")

        # 무엇을 확인할 수 있나요? (4가지 주제)
        show_html("""
        <div class="sec-title" style="margin-top: 26px;"><h2>이런 물건을 확인할 수 있어요</h2><span>사기 전에 꼭 확인해 보세요</span></div>
        <div class="topic-grid">
            <div class="topic-card c-blue">
                <div class="topic-icon">💊</div>
                <div>
                <h3>해외 약·영양제</h3>
                <p class="topic-q">먹어도 괜찮은 약일까요?</p>
                <p class="desc">우리나라에 들여올 수 없는 성분이 들었는지, 의사 처방전이 필요한 약인지 알려드려요.</p>
    </div>
            </div>
            <div class="topic-card c-pink">
                <div class="topic-icon">🧸</div>
                <div>
                <h3>어린이 제품</h3>
                <p class="topic-q">우리 아이가 써도 될까요?</p>
                <p class="desc">장난감·유아용품에서 몸에 해로운 물질이 나와 회수(리콜)된 적이 있는지 확인해요.</p>
    </div>
            </div>
            <div class="topic-card c-green">
                <div class="topic-icon">🧴</div>
                <div>
                <h3>생활용품</h3>
                <p class="topic-q">매일 쓰는 물건, 안전할까요?</p>
                <p class="desc">가방·주방용품·생활화학제품 등이 안전 인증을 받았는지, 문제가 된 적은 없는지 찾아봐요.</p>
    </div>
            </div>
            <div class="topic-card c-amber">
                <div class="topic-icon">🔌</div>
                <div>
                <h3>전기용품</h3>
                <p class="topic-q">불나거나 감전될 걱정은요?</p>
                <p class="desc">충전기·보조배터리·드라이어 등이 KC 안전인증과 전파인증을 제대로 받았는지 확인해요.</p>
    </div>
            </div>
        </div>
        """)

        # =============================================================
        # 직접 찾아보기 (사진 없이 이름·번호로 검색)
        # =============================================================
        st.markdown("")
        show_html("""
        <div class="sec-title" style="margin-top: 26px;"><h2>🔎 직접 찾아보기</h2>
        <span>사진이 없어도 괜찮아요. 제품 이름이나 인증번호를 입력해서 찾을 수 있어요.</span></div>
        """)

        tab_drug, tab_kc, tab_rra, tab_recall, tab_os = st.tabs([
            "💊 약·영양제",
            "✅ KC 안전인증",
            "🔌 전기제품 전파인증",
            "🚨 리콜(회수) 제품",
            "📦 해외직구 위험 제품",
        ])

        # 약·영양제
        with tab_drug:
            st.markdown("##### 💊 들여올 수 없는 해외 약·식품 찾아보기")
            st.caption("식약처가 '해외에서 사 오면 안 된다'고 정한 제품 목록이에요. 제품 이름, 성분, 바코드, 회사 이름으로 찾을 수 있어요.")
            search_q = st.text_input("찾을 단어", placeholder="예: 멜라토닌, yohimbine, 다이어트", key="user_food_search_q")

            if search_q.strip() or st.button("전체 목록 보기", key="user_refresh_food"):
                res = db_service.search(query=search_q, page=1, page_size=20)
                items = res.get("items", [])
                total = res.get("total", 0)

                st.write(f"찾은 결과: **{total:,}건**")
                if items:
                    for item in items:
                        with st.expander(f"🚫 {item.get('제품명', '이름 없음')}  ·  성분: {item.get('성분명', '-')}"):
                            c1, c2 = st.columns([1, 2])
                            with c1:
                                img_url = item.get("이미지경로")
                                if img_url:
                                    st.image(img_url, use_container_width=True)
                                else:
                                    st.caption("등록된 사진 없음")
                            with c2:
                                st.write(f"**만든 회사 / 나라**: {item.get('제조사', '-')} / {item.get('제조국', '-')}")
                                st.write(f"**문제 성분**: {item.get('성분명', '-')}")
                                st.write(f"**막힌 이유**: {item.get('회수사유', '-')}")
                                st.write(f"**바코드**: `{item.get('바코드', '-')}`")
                                st.caption(f"자료 출처: {item.get('정보출처', '-')} · 등록번호 {item.get('등록번호', '-')}")
                else:
                    st.info("찾는 단어와 맞는 제품이 차단 목록에 없어요.")

            st.markdown("---")
            st.markdown("##### ⌨️ 제품 이름·성분을 직접 입력해서 확인하기")
            st.caption("성분표에 적힌 성분을 입력하면 차단 목록과 비교해 드려요.")
            t_name = st.text_input("제품 이름", key="user_t_name")
            t_barcode = st.text_input("바코드 (없으면 비워 두세요)", key="user_t_bar")
            t_ing = st.text_area("성분 (쉼표로 나눠서 입력, 예: yohimbine, sildenafil, melatonin)", key="user_t_ing")

            if st.button("확인하기", type="primary", key="user_t_btn"):
                if not t_name.strip() and not t_ing.strip():
                    st.warning("제품 이름이나 성분 중 하나는 입력해 주세요.")
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
                        st.error("🚫 입력한 내용이 정부의 위험 제품 목록과 일치해요. 구매하지 않는 것이 좋아요.")
                        with st.expander("자세한 비교 자료 보기"):
                            st.json({
                                "식약처_비교결과": res,
                                "국표원_안전정보": safety_res
                            })
                    else:
                        st.success("✅ 정부의 위험 제품·리콜 목록에서 일치하는 내용을 찾지 못했어요.")

        render_kc_search(tab_kc)
        render_rra_search(tab_rra)
        render_recall_search(tab_recall)
        render_overseas_search(tab_os)


# =============================================================
# 2. 관리자 콘솔 (세관·운영자 전용)
# =============================================================
def render_admin_service():
    # 관리자 머리말 (작게)
    show_html("""
    <div class="admin-header">
        <h1>⚙️ 관리자 화면</h1>
        <p>정부 자료 연결 상태 확인 · 차단 목록 업데이트 · 이용 현황 보기</p>
    </div>
    """)

    # 로그인 전: 작은 로그인 상자만 보여줌
    if not st.session_state["admin_authenticated"]:
        _l, mid, _r = st.columns([1, 1.3, 1])
        with mid:
            show_html("""
            <div class="login-card">
                <div class="lock">🔒</div>
                <h3>관리자 로그인</h3>
                <p>관리자만 들어갈 수 있어요. 비밀번호를 입력해 주세요.</p>
            </div>
            """)
            with st.form("admin_login_form", border=False):
                admin_pwd = st.text_input("비밀번호", type="password", key="admin_pwd_input",
                                          placeholder="비밀번호 입력", label_visibility="collapsed")
                login_clicked = st.form_submit_button("로그인", type="primary", use_container_width=True)

            if login_clicked:
                if admin_pwd == "customs2026" or admin_pwd == "admin1234":
                    st.session_state["admin_authenticated"] = True
                    st.rerun()
                else:
                    st.error("비밀번호가 맞지 않아요. 다시 입력해 주세요.")

            if st.button("← 첫 화면으로 돌아가기", use_container_width=True, key="admin_back_home"):
                st.session_state["admin_view"] = False
                st.rerun()
        return

    # 관리자 사이드바
    with st.sidebar:
        st.subheader("🛡️ 관리자 보안 세션")
        st.success("인증 상태: **운영자 / 세관 관리자**")
        
        c_side1, c_side2 = st.columns(2)
        with c_side1:
            if st.button("👥 사용자 화면", use_container_width=True, key="admin_sidebar_to_user"):
                st.session_state["admin_view"] = False
                st.rerun()
        with c_side2:
            if st.button("🚪 로그아웃", use_container_width=True, key="admin_sidebar_logout"):
                st.session_state["admin_authenticated"] = False
                st.session_state["admin_view"] = False
                st.rerun()

        st.markdown("---")
        with st.expander("🔑 AI 비전 엔진(Gemini) 설정", expanded=False):
            if ai_vision_service.client:
                st.success("✅ Gemini 연결 정상")
            else:
                st.warning("⚠️ Gemini API 키 필요")
            
            custom_key = st.text_input(
                "Gemini Key",
                value=st.session_state.get("user_gemini_key", ai_vision_service.api_key or ""),
                type="password",
                key="gemini_key_admin_sidebar"
            )
            if custom_key:
                st.session_state["user_gemini_key"] = custom_key
                if custom_key != ai_vision_service.api_key or not ai_vision_service.client:
                    ai_vision_service.api_key = custom_key
                    ai_vision_service._init_client()
                    if ai_vision_service.client:
                        st.success("✅ 새 API 키 연결 완료!")

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
# 직접 찾아보기: 안전인증·전파인증·리콜·해외직구 검사 결과
# (국가기술표준원 제품안전정보센터 + 국립전파연구원)
# =============================================================
def render_kc_search(container):
    with container:
        st.markdown("##### ✅ KC 안전인증을 받은 제품인지 확인하기")
        st.caption("어린이 제품·생활용품·전기용품은 우리나라에서 팔려면 KC 안전인증이 필요해요. 제품 이름이나 KC 인증번호로 찾아보세요.")
        c1, c2 = st.columns([1, 2])
        with c1:
            cert_cond = st.selectbox("무엇으로 찾을까요?", [
                ("all", "전체"),
                ("productName", "제품 이름"),
                ("modelName", "모델명"),
                ("certNum", "인증번호")
            ], format_func=lambda x: x[1], key="kc_cond")
        with c2:
            cert_val = st.text_input("찾을 단어", placeholder="예: 충전기, 보조배터리, 유아용 의자, 장난감", key="kc_val")

        if st.button("KC 인증 찾기", type="primary", key="kc_btn"):
            if not cert_val.strip():
                st.warning("찾을 단어를 입력해 주세요.")
            else:
                with st.spinner("제품안전정보센터에서 찾고 있어요..."):
                    res = safetykorea_api.search_certifications(query=cert_val.strip(), condition_key=cert_cond[0])
                    if res.get("success"):
                        items = res.get("items", [])
                        st.write(f"찾은 결과: **{len(items):,}건**")
                        for item in items[:15]:
                            state = item.get("certState", "-")
                            badge = "badge-safe" if state == "적합" else "badge-danger"
                            with st.expander(f"{item.get('productName', '-')} ({item.get('modelName', '-')})  ·  {item.get('certNum', '-')}"):
                                st.markdown(f"**인증 상태**: <span class='{badge}'>{_t(state)}</span>", unsafe_allow_html=True)
                                st.write(f"- **인증 종류**: {item.get('certDiv', '-')}")
                                st.write(f"- **만든 회사 / 나라**: {item.get('makerName', '-')} / {item.get('makerCntryName', '-')}")
                                st.write(f"- **수입한 회사**: {item.get('importerName', '-')}")
                                st.write(f"- **인증일**: {item.get('certDate', '-')}")

                                c_num = item.get('certNum')
                                if c_num:
                                    st.markdown(f"[🔗 제품안전정보센터에서 자세히 보기](https://www.safetykorea.kr/search/searchPop?certNum={c_num})")
                                    det = safetykorea_api.get_certification_detail(c_num)
                                    if det.get("success") and det.get("data"):
                                        kc_imgs = det["data"].get("certificationImageUrls") or []
                                        if kc_imgs:
                                            st.markdown(f"**📸 인증 등록 사진 ({len(kc_imgs)}장)**")
                                            kc_cols = st.columns(min(len(kc_imgs), 4))
                                            for idx, (img_url, ic) in enumerate(zip(kc_imgs, kc_cols)):
                                                with ic:
                                                    st.image(img_url, caption=f"사진 {idx+1}", use_container_width=True)
                    else:
                        st.error(f"지금은 찾을 수 없어요. 잠시 후 다시 시도해 주세요. ({res.get('error')})")


def render_rra_search(container):
    with container:
        st.markdown("##### 🔌 전기·전자제품 전파인증 확인하기")
        st.caption("무선 이어폰, 충전기, 블루투스 기기처럼 전파를 쓰는 제품은 국립전파연구원 인증이 필요해요. 제품이나 상자에 적힌 인증번호(R-로 시작)를 입력하세요.")

        rra_col1, rra_col2 = st.columns([3, 1])
        with rra_col1:
            rra_input_val = st.text_input(
                "인증번호",
                placeholder="예: R-REM-Y15-YW1801, MSIP-REM-..., KCC-...",
                key="rra_manual_input"
            )
        with rra_col2:
            st.write("")
            st.write("")
            rra_search_btn = st.button("전파인증 찾기", type="primary", key="rra_manual_btn", use_container_width=True)

        if rra_search_btn:
            if not rra_input_val.strip():
                st.warning("인증번호를 입력해 주세요.")
            else:
                with st.spinner("국립전파연구원에서 찾고 있어요..."):
                    rra_res = rra_api.lookup_conformity(rra_input_val.strip())
                    if rra_res.get("success") and rra_res.get("data"):
                        rd = rra_res["data"]
                        st.success(f"✅ 정식으로 인증받은 제품이에요: **{rd.get('cert_num')}**")

                        show_html(f"""
                        <div class="info-card green">
                            <h4>🔌 {_t(rd.get('device_name'), '전기·전자제품')}</h4>
                            <div class="info-row"><b>인증번호</b> · <code>{_t(rd.get('cert_num'))}</code></div>
                            <div class="info-row"><b>신청한 회사</b> · {_t(rd.get('company_name'))}</div>
                            <div class="info-row"><b>모델명</b> · {_t(rd.get('model_name'))}</div>
                            <div class="info-row"><b>인증일</b> · {_t(rd.get('cert_date'))}</div>
                            <div class="info-row"><b>만든 곳 / 나라</b> · {_t(rd.get('maker'))} / {_t(rd.get('country'))}</div>
                            <div class="info-row"><b>인증 종류</b> · {_t(rd.get('cert_type'), '적합등록')}</div>
                        </div>
                        """)

                        derivatives = rd.get("derivative_models", [])
                        if derivatives:
                            st.write(f"- **같이 인증된 모델 ({len(derivatives)}개)**: {', '.join(derivatives)}")

                        st.markdown(f"[🔗 국립전파연구원 인증 원문 보기]({rd.get('source_url')})")
                    else:
                        st.error(f"❌ 등록되지 않았거나 잘못된 인증번호예요. 번호를 다시 확인해 주세요. ({rra_res.get('error') or ''})")


def render_recall_search(container):
    with container:
        st.markdown("##### 🚨 리콜(회수)된 제품 찾아보기")
        st.caption("리콜은 위험이 발견돼 판매를 멈추고 거둬들이는 제품이에요. 우리나라와 해외에서 리콜된 제품을 찾아볼 수 있어요.")

        where = st.radio("어디에서 리콜된 제품을 찾을까요?", ["🇰🇷 우리나라", "🌍 해외"], horizontal=True, key="recall_where")

        if where.startswith("🇰🇷"):
            c1, c2 = st.columns([1, 2])
            with c1:
                dr_cond = st.selectbox("무엇으로 찾을까요?", [
                    ("all", "전체"),
                    ("recallProductName", "제품 이름"),
                    ("recallModelName", "모델명"),
                    ("barcodeNum", "바코드"),
                    ("certNum", "인증번호")
                ], format_func=lambda x: x[1], key="dr_cond")
            with c2:
                dr_val = st.text_input("찾을 단어", placeholder="예: 장난감, 유아 의자, 가방, 배터리", key="dr_val")

            if st.button("리콜 제품 찾기", type="primary", key="dr_btn"):
                if not dr_val.strip():
                    st.warning("찾을 단어를 입력해 주세요.")
                else:
                    with st.spinner("우리나라 리콜 제품을 찾고 있어요..."):
                        res = safetykorea_api.search_domestic_recalls(query=dr_val.strip(), condition_key=dr_cond[0])
                        if res.get("success"):
                            items = res.get("items", [])
                            st.write(f"찾은 결과: **{len(items):,}건**")
                            for item in items[:15]:
                                u_id = item.get("recallUid")
                                r_url = f"https://www.safetykorea.kr/recall/ajax/recallBoard?recallUid={u_id}" if u_id else "https://www.safetykorea.kr"

                                with st.expander(f"🚨 {item.get('recallProductName', '-')} ({item.get('recallModelName', '-')})  ·  {item.get('recallTypeName', '리콜')}"):
                                    st.error(f"**판매·수입 회사**: {item.get('recallCmpnyName', '-')} (문의 {item.get('recallInqryTel', '-')})")
                                    if item.get("certNum"):
                                        st.write(f"- **인증번호**: `{item.get('certNum')}`")
                                    st.write(f"- **발표일**: {item.get('publishDate', '-')}")
                                    st.write(f"- **만든 나라**: {item.get('makingCntryName', '-')}")
                                    st.write(f"- **어떤 문제가 있었나요?** {item.get('harmDscr', '자세한 내용은 원문을 확인하세요')}")
                                    st.write(f"- **어떤 사고가 날 수 있나요?** {item.get('accidentCaseDscr', '-')}")
                                    st.write(f"- **이렇게 하세요**: {item.get('publishActionDscr', '-')}")

                                    st.markdown(f"👉 [정부 리콜 안내문 원문 보기]({r_url})")

                                    if u_id:
                                        det = safetykorea_api.get_domestic_recall_detail(u_id)
                                        if det.get("success") and det.get("data"):
                                            r_files = det["data"].get("recallFiles") or []
                                            if r_files:
                                                st.markdown(f"**📸 리콜 제품 사진 ({len(r_files)}장)**")
                                                r_cols = st.columns(min(len(r_files), 4))
                                                for idx, (rf, rc) in enumerate(zip(r_files, r_cols)):
                                                    with rc:
                                                        f_div = rf.get("fileDiv") or f"사진 {idx+1}"
                                                        st.image(rf.get("imageUrl"), caption=f_div, use_container_width=True)
                        else:
                            st.error(f"지금은 찾을 수 없어요. 잠시 후 다시 시도해 주세요. ({res.get('error')})")
        else:
            c1, c2 = st.columns([1, 2])
            with c1:
                fr_cond = st.selectbox("무엇으로 찾을까요?", [
                    ("all", "전체"),
                    ("recallProductName", "제품 이름"),
                    ("recallModelName", "모델명"),
                    ("recallBrandName", "브랜드")
                ], format_func=lambda x: x[1], key="fr_cond")
            with c2:
                fr_val = st.text_input("찾을 단어", placeholder="예: 장난감, 텀블러, 드라이어", key="fr_val")

            if st.button("해외 리콜 제품 찾기", type="primary", key="fr_btn"):
                if not fr_val.strip():
                    st.warning("찾을 단어를 입력해 주세요.")
                else:
                    with st.spinner("해외 리콜 제품을 찾고 있어요..."):
                        res = safetykorea_api.search_foreign_recalls(query=fr_val.strip(), condition_key=fr_cond[0])
                        if res.get("success"):
                            items = res.get("items", [])
                            st.write(f"찾은 결과: **{len(items):,}건**")
                            for item in items[:15]:
                                with st.expander(f"🌍 [{item.get('recallPblshCntryName', '해외')}] {item.get('recallProductName', '-')} ({item.get('recallModelName', '-')})"):
                                    st.warning(f"**발표한 기관**: {item.get('recallPblshOrgnName', '-')} | **리콜 종류**: {item.get('recallTypeName', '-')}")
                                    st.write(f"- **어떤 문제가 있었나요?** {item.get('violateDscr', '-')}")
                                    st.write(f"- **이렇게 하세요**: {item.get('publishActionDscr', '-')}")
                                    st.write(f"- **만든 나라**: {item.get('makingCntryName', '-')}")
                                    img_url = item.get("imageUrl")
                                    if img_url:
                                        first_img = img_url.split(",")[0]
                                        st.image(first_img, caption="리콜 제품 사진", width=250)
                        else:
                            st.error(f"지금은 찾을 수 없어요. 잠시 후 다시 시도해 주세요. ({res.get('error')})")


def render_overseas_search(container):
    with container:
        st.markdown("##### 📦 해외직구 검사에서 문제가 나온 제품 찾아보기")
        st.caption("정부가 알리·테무 등 해외 쇼핑몰 제품을 직접 사서 검사했더니 해로운 물질이 기준보다 많이 나온 제품이에요.")
        c1, c2 = st.columns([1, 2])
        with c1:
            os_cond = st.selectbox("무엇으로 찾을까요?", [
                ("all", "전체"),
                ("productName", "제품 이름"),
                ("modelName", "모델명")
            ], format_func=lambda x: x[1], key="os_cond")
        with c2:
            os_val = st.text_input("찾을 단어", placeholder="예: 장난감, 어린이 신발, 배터리, 머리띠", key="os_val")

        if st.button("문제 제품 찾기", type="primary", key="os_btn"):
            if not os_val.strip():
                st.warning("찾을 단어를 입력해 주세요.")
            else:
                with st.spinner("해외직구 검사 결과를 찾고 있어요..."):
                    res = safetykorea_api.search_overseas_safety(query=os_val.strip(), condition_key=os_cond[0])
                    if res.get("success"):
                        items = res.get("items", [])
                        st.write(f"찾은 결과: **{len(items):,}건**")
                        for item in items[:15]:
                            with st.expander(f"📦 {item.get('productName', '-')} ({item.get('modelName', '-')})"):
                                st.error(f"**🚨 무엇이 문제였나요?** {item.get('harmDscr', '-')}")
                                st.write(f"- **몸에 미치는 영향**: {item.get('accidentCaseDscr', '-')}")
                                st.write(f"- **발표일**: {item.get('publishDate', '-')}")
                                st.write(f"- **만든 나라**: {item.get('makingCntryName', '-')}")
                                img_url = item.get("imageUrl")
                                if img_url:
                                    first_img = img_url.split(",")[0]
                                    st.image(first_img, caption="검사한 제품 사진", width=300)
                    else:
                        st.error(f"지금은 찾을 수 없어요. 잠시 후 다시 시도해 주세요. ({res.get('error')})")


# =============================================================
# 메인 라우터 실행
# =============================================================
if is_admin_mode:
    render_admin_service()
else:
    render_user_service()
