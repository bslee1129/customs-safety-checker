import os
import sys
import io
import time
from PIL import Image
import streamlit as st

# 페이지 기본 설정
st.set_page_config(
    page_title="관세청 AI 위해식품·제품안전 스마트 검사관",
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
    .badge-danger {
        background-color: #dc3545;
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .badge-warning {
        background-color: #ffc107;
        color: #212529;
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
    .result-box {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# 헤더 영역
st.markdown("""
<div class="main-header">
    <h1>🛡️ 관세청 AI 위해물품 스마트 통합 검사관 v2.5</h1>
    <p>식약처 해외직구 차단식품 + 국가기술표준원 SafetyKorea 4대 제품안전정보(KC인증·국내리콜·국외리콜·직구안전성) 실시간 통합 대조 시스템</p>
</div>
""", unsafe_allow_html=True)

# 사이드바: 통계 및 동기화 현황
with st.sidebar:
    st.header("📊 시스템 상태 및 API 연동")
    
    # API 키 설정 상태 표시
    current_gemini_key = os.getenv("GEMINI_API_KEY", "")
    current_food_key = os.getenv("FOOD_SAFETY_API_KEY", "")
    current_safety_key = os.getenv("SAFETYKOREA_API_KEY", "")

    if current_gemini_key:
        st.success("✅ Gemini AI Vision: 연동 완료")
    else:
        st.warning("⚠️ Gemini API 키 미등록 (Streamlit Secrets 필요)")

    if current_food_key:
        st.success("✅ 식약처 식품안전나라 API: 연동 완료")
    else:
        st.warning("⚠️ 식품안전나라 API 키 미등록")

    if current_safety_key:
        st.success("✅ 국표원 SafetyKorea API: 연동 완료")
    else:
        st.warning("⚠️ SafetyKorea API 키 미등록")

    st.markdown("---")
    
    # 자체 DB 통계 조회
    stats = db_service.get_stats()
    st.metric(label="총 위해식품 차단 데이터", value=f"{stats['total_records']:,} 건")
    st.metric(label="등록 바코드 수", value=f"{stats['total_barcodes']:,} 개")
    st.metric(label="식별 위해성분 종류", value=f"{stats['total_harmful_ingredients']:,} 종")
    st.caption(f"최종 DB 동기화: {stats['last_sync_time']}")

    st.markdown("---")
    st.subheader("🔄 식약처 Open API 동기화")
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

# 메인 탭 구성
tab1, tab2, tab3, tab4 = st.tabs([
    "📸 현품 사진 1:1 비교 대조 검사 (통합 AI)",
    "🏛️ 국표원 4대 안전정보 통합조회 (SafetyKorea)",
    "🔍 위해식품 차단 DB 통합 검색",
    "⌨️ 제품 텍스트 직접 입력 수동 검사"
])

# -------------------------------------------------------------
# 탭 1: 현품 사진 1:1 비교 대조
# -------------------------------------------------------------
with tab1:
    st.markdown("### 📷 통관 현품 사진 AI 다중 검사 (식약처 + 국표원 4대 안전정보)")
    st.write("의심 제품의 **전면(제품명), 후면(원재료/성분표), 측면(바코드)** 사진을 1장 또는 여러 장 등록하세요.")

    col1, col2 = st.columns([1, 1])

    if "camera_photos" not in st.session_state:
        st.session_state["camera_photos"] = []

    upload_mode = st.radio("사진 입력 방식 선택", ["📁 파일 업로드 (여러 장 가능)", "📷 카메라 직접 촬영 (연속 촬영 가능)"], horizontal=True)
    image_bytes_list = []

    if "파일 업로드" in upload_mode:
        uploaded_files = st.file_uploader(
            "제품 사진 선택 (여러 장 등록 가능: 전면, 후면 성분표, 바코드 등)",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True
        )
        if uploaded_files:
            image_bytes_list = [f.getvalue() for f in uploaded_files]
            st.caption(f"📌 총 {len(image_bytes_list)}장의 사진이 등록되었습니다.")
            preview_cols = st.columns(min(len(image_bytes_list), 4))
            for idx, (img_b, p_col) in enumerate(zip(image_bytes_list, preview_cols)):
                with p_col:
                    st.image(img_b, caption=f"사진 {idx+1}", use_container_width=True)
    else:
        cam_photo = st.camera_input("카메라로 제품 촬영 (전면, 성분표 등)")
        c_btn1, c_btn2 = st.columns([1, 1])
        with c_btn1:
            if cam_photo and st.button("📸 현재 촬영 사진 목록에 추가"):
                st.session_state["camera_photos"].append(cam_photo.getvalue())
                st.success(f"사진이 추가되었습니다! (총 {len(st.session_state['camera_photos'])}장)")
        with c_btn2:
            if st.session_state["camera_photos"] and st.button("🗑️ 촬영 사진 전체 초기화"):
                st.session_state["camera_photos"] = []
                st.info("촬영 목록이 초기화되었습니다.")

        if st.session_state["camera_photos"]:
            image_bytes_list = st.session_state["camera_photos"]
            st.caption(f"📌 등록된 촬영 사진: 총 {len(image_bytes_list)}장")
            preview_cols = st.columns(min(len(image_bytes_list), 4))
            for idx, (img_b, p_col) in enumerate(zip(image_bytes_list, preview_cols)):
                with p_col:
                    st.image(img_b, caption=f"촬영 {idx+1}", use_container_width=True)
        elif cam_photo:
            image_bytes_list = [cam_photo.getvalue()]

    barcode_hint = st.text_input("바코드 번호 (선택사항, 육안 식별 시 보완 입력)")

    if image_bytes_list:
        st.markdown("---")
        if st.button(f"🚀 AI 범정부 통합 정밀 검사 시작 ({len(image_bytes_list)}장 통합 분석)", type="primary", use_container_width=True):
            with st.spinner(f"Gemini AI가 {len(image_bytes_list)}장의 사진을 판독하여 식약처 차단DB 및 국표원 4대 안전정보와 실시간 대조 중입니다..."):
                # 1. AI Vision 다중 사진 통합 분석
                vision_result = ai_vision_service.analyze_image(image_bytes_list)
                
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

                # 2. 식약처 위해식품/의약품 DB 매칭
                match_res = db_service.match_product(ocr_data)
                food_status = match_res.get("status", "PASS")
                food_matched = match_res.get("matched", False) or (food_status in ("DANGER", "WARNING")) or bool(match_res.get("record"))
                db_record = match_res.get("record")
                citizen = match_res.get("citizen_summary", {})
                verdict = match_res.get("verdict", "")
                confidence = match_res.get("confidence", 0)

                # 3. 국표원 SafetyKorea 4대 안전정보 실시간 조회
                p_name = ocr_data.get("product_name", "")
                p_name_ko = ocr_data.get("product_name_ko", "")
                m_name = ocr_data.get("model_name", "")
                b_code = ocr_data.get("barcode", "")
                kc_num = ocr_data.get("kc_cert_num", "")

                safety_res = safetykorea_api.comprehensive_check(
                    product_name=p_name,
                    model_name=m_name,
                    barcode=b_code,
                    kc_cert_num=kc_num,
                    product_name_ko=p_name_ko
                )

                # 종합 판정 결합
                is_danger = food_status == "DANGER" or safety_res.get("has_danger", False)
                is_warning = (not is_danger) and (food_status == "WARNING" or safety_res.get("has_warning", False))

                st.subheader("📋 범정부 AI 1:1 비교 대조 종합 판정 결과")

                # 판정 배너
                if is_danger:
                    st.error("### 🚨 [국내 반입 불가 / 전량 폐기 대상]\n식약처 위해식품 또는 국표원 해외직구 안전성 부적합/리콜 제품과 일치합니다!")
                elif is_warning:
                    st.warning("### ⚠️ [반입 주의 / 정밀 확인 필요]\n처방전 필요 성분 또는 국외 리콜 이력이 확인된 품목입니다.")
                elif safety_res.get("is_kc_certified"):
                    kc = safety_res.get("kc_detail", {})
                    st.success(f"### ✅ [KC 정식 안전인증 확인 - 적합]\n**국가기술표준원 안전확인 기준을 통과한 안전한 정식 수입/제조 물품입니다.**\n- **인증번호**: `{kc.get('certNum', '-')}` | **모델명**: `{kc.get('modelName', '-')}` ({kc.get('certOrganName', '-')})")
                else:
                    st.success("### ✅ [정상 / 차단 미등록]\n식약처 위해식품 및 국표원 4대 안전정보에 등재되지 않은 정상 품목입니다.")

                # 사진 1:1 비교 영역
                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown(f"#### 📷 현품 검사 사진 ({len(image_bytes_list)}장 등록됨)")
                    if len(image_bytes_list) == 1:
                        st.image(image_bytes_list[0], caption="촬영/업로드된 실제 검사물품", use_container_width=True)
                    else:
                        img_tabs = st.tabs([f"사진 {i+1}" for i in range(len(image_bytes_list))])
                        for i, i_tab in enumerate(img_tabs):
                            with i_tab:
                                st.image(image_bytes_list[i], caption=f"검사물품 사진 #{i+1}", use_container_width=True)

                with col_right:
                    st.markdown("#### 🏛️ 정부 DB 공식 등록 원본 사진")
                    db_img_url = match_res.get("db_remote_image_url")
                    
                    # 국표원 해외직구 조사 사진 우선 대조
                    if not db_img_url and safety_res.get("overseas_safety"):
                        os_img = safety_res["overseas_safety"][0].get("imageUrl")
                        if os_img:
                            db_img_url = os_img.split(",")[0]
                    # 국표원 리콜 사진 대조
                    if not db_img_url and safety_res.get("domestic_recalls"):
                        dr_img = safety_res["domestic_recalls"][0].get("imageUrl")
                        if dr_img:
                            db_img_url = dr_img.split(",")[0]

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
                        st.image(local_img_path, caption=f"식약처 차단 사진 (등록번호: {local_seq})", use_container_width=True)
                    elif db_img_url:
                        st.image(db_img_url, caption="정부기관 공식 제공 이미지", use_container_width=True)
                    else:
                        st.info("등록된 원본 비교 사진이 없거나 조회 중입니다.")

                # 세부 대조 정보
                st.markdown("#### 🔍 세부 대조 내역")
                info_col1, info_col2 = st.columns(2)
                with info_col1:
                    st.write("**[AI 라벨 추출 정보]**")
                    st.write(f"- 판독 제품명: `{ocr_data.get('product_name', '-')}`")
                    if ocr_data.get("product_name_ko"):
                        st.write(f"- 한글 제품명: `{ocr_data.get('product_name_ko')}`")
                    st.write(f"- 모델명: `{ocr_data.get('model_name', '-')}`")
                    st.write(f"- KC인증번호: `{ocr_data.get('kc_cert_num', '-')}`")
                    st.write(f"- 브랜드/제조사: `{ocr_data.get('brand', '-')}`")
                    st.write(f"- 바코드: `{ocr_data.get('barcode', '-')}`")

                with info_col2:
                    st.write("**[정부 DB 대조 판정]**")
                    if db_record:
                        st.write(f"- 식약처 차단 제품명: `{db_record.get('제품명', '-')}`")
                        st.write(f"- 검출 위해성분: `{db_record.get('성분명', '-')}`")
                    else:
                        st.write("- 식약처 위해식품: 일치 차단 레코드 없음")

                    if safety_res.get("is_kc_certified"):
                        kc = safety_res.get("kc_detail", {})
                        st.write(f"- **KC인증 상태**: `적합 (인증완료)`")
                        st.write(f"- **인증번호**: `{kc.get('certNum', '-')}`")
                        st.write(f"- **시험연구원**: `{kc.get('certOrganName', '-')}`")
                        st.write(f"- **수입사**: `{kc.get('importerName', '-')}`")
                    elif safety_res.get("certifications"):
                        st.write(f"- **KC인증**: 상태 `{safety_res['certifications'][0].get('certState', '-')}`")
                    else:
                        st.write("- **KC인증**: 미조회 또는 인증정보 없음")

                # 국표원 연동 안전정보 카드
                st.markdown("---")
                st.markdown("#### 🏛️ 국가기술표준원(SafetyKorea) 4대 안전정보 실시간 검사")
                
                if safety_res.get("summary_alerts"):
                    for alert in safety_res["summary_alerts"]:
                        if "✅" in alert:
                            st.success(alert)
                        elif "🚨" in alert:
                            st.error(alert)
                        else:
                            st.warning(alert)
                else:
                    st.info("국가기술표준원 4대 안전정보(KC인증·리콜·직구안전성)에 등록된 특이사항이 없습니다.")

                if safety_res.get("overseas_safety"):
                    with st.expander("🚨 해외직구 안전성조사 부적합 적발 내역", expanded=True):
                        for item in safety_res["overseas_safety"][:3]:
                            st.error(f"**제품명**: {item.get('productName')} | **모델명**: {item.get('modelName', '-')}")
                            st.write(f"**부적합 판정 내용**: {item.get('harmDscr', '-')}")
                            st.write(f"**위해 정보**: {item.get('accidentCaseDscr', '-')}")

                if safety_res.get("domestic_recalls"):
                    with st.expander("🚨 국내 리콜 명령 대상 내역", expanded=True):
                        for item in safety_res["domestic_recalls"][:3]:
                            st.error(f"**제품명**: {item.get('recallProductName')} | **리콜종류**: {item.get('recallTypeName', '-')}")
                            st.write(f"**제품 결함**: {item.get('harmDscr', '-')}")
                            st.write(f"**소비자 행동요령**: {item.get('publishActionDscr', '-')}")

                if is_danger and citizen:
                    st.markdown("---")
                    st.markdown("#### 🛡️ 대국민 안전 정보 및 통관 안내")
                    guide_col1, guide_col2 = st.columns(2)
                    with guide_col1:
                        if citizen.get("why_prohibited"):
                            st.error(f"**🚫 반입 금지 사유**\n\n{citizen['why_prohibited']}")
                        if citizen.get("health_risks"):
                            st.warning(f"**⚠️ 인체 부작용 및 건강 위험성**\n\n{citizen['health_risks']}")
                    with guide_col2:
                        if citizen.get("action_guide"):
                            st.info(f"**💡 국민 행동 요령**\n\n{citizen['action_guide']}")
                        if citizen.get("legal_basis"):
                            st.caption(f"**관련 법령**: {citizen['legal_basis']}")

# -------------------------------------------------------------
# 탭 2: 국표원 4대 안전정보 통합조회 (SafetyKorea)
# -------------------------------------------------------------
with tab2:
    st.markdown("### 🏛️ 국가기술표준원 SafetyKorea 4대 제품안전정보 Open API 통합 조회")
    st.caption("인증키: `bdd3c16d-...` 연동 완료 (공식 규격 인터페이스 적용)")

    sk_sub1, sk_sub2, sk_sub3, sk_sub4 = st.tabs([
        "🏷️ KC인증정보",
        "🚨 국내리콜정보",
        "🌍 국외리콜정보",
        "📦 해외직구 안전성조사결과"
    ])

    # 1. KC인증정보
    with sk_sub1:
        st.subheader("🏷️ KC인증정보 조회")
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
                                if item.get("remark"):
                                    st.write(f"- **상세내용**: {item.get('remark')}")
                    else:
                        st.error(f"조회 실패: {res.get('error')}")

    # 2. 국내리콜정보
    with sk_sub2:
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
                            with st.expander(f"[{item.get('recallTypeName', '리콜')}] {item.get('recallProductName', '-')} ({item.get('recallModelName', '-')})"):
                                st.error(f"**리콜 사업자**: {item.get('recallCmpnyName', '-')} (문의: {item.get('recallInqryTel', '-')})")
                                st.write(f"- **공표일자**: {item.get('publishDate', '-')}")
                                st.write(f"- **제조국가**: {item.get('makingCntryName', '-')}")
                                st.write(f"- **제품 결함**: {item.get('harmDscr', '상세내용 확인')}")
                                st.write(f"- **사고/위해정보**: {item.get('accidentCaseDscr', '-')}")
                                st.write(f"- **소비자 행동요령/조치사항**: {item.get('publishActionDscr', '-')}")
                    else:
                        st.error(f"조회 실패: {res.get('error')}")

    # 3. 국외리콜정보
    with sk_sub3:
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

    # 4. 해외직구 안전성조사결과
    with sk_sub4:
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

# -------------------------------------------------------------
# 탭 3: 차단 DB 통합 검색
# -------------------------------------------------------------
with tab3:
    st.markdown("### 🔍 식약처 위해식품·불법의약품 차단 DB 통합 검색")
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
# 탭 4: 텍스트 직접 입력 수동 검사
# -------------------------------------------------------------
with tab4:
    st.markdown("### ⌨️ 제품 정보 직접 입력 대조 (식약처 + 국표원)")
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
            safety_res = safetykorea_api.comprehensive_check(product_name=t_name, barcode=t_barcode)

            if res.get("matched") or safety_res.get("has_danger"):
                st.error("🚨 [차단 대상] 입력하신 정보가 위해물품 데이터베이스와 일치합니다!")
                st.json({
                    "식약처_매칭결과": res,
                    "국표원_안전정보": safety_res
                })
            else:
                st.success("✅ [정상] 일치하는 차단 정보가 없습니다.")
