# 해외직구 안심 약체크 (SafeDrug) - 관세청·식약처 대국민 안심 통관 서비스

해외직구 또는 해외여행 중 구매하려는 **해외 의약품·영양제의 사진을 찍으면**, 인공지능(AI)과 식품안전나라 정부 공공데이터를 통해 **1) 해당 약이 위험한지, 2) 국내 반입이 가능한지, 3) 왜 반입이 안 되는지(부작용 및 법적 사유)**를 1초 만에 알기 쉽게 판별해 주는 **대국민 안전 혁신 플랫폼**입니다.

---

## 🌟 대국민 핵심 서비스

### 1. 사진 한 장으로 해외 의약품 반입 가능 여부 즉시 판별
- **스마트폰 카메라 / 웹캠 / 사진 파일 업로드 지원**: 약 포장 앞면, 라벨, 성분표(Supplement Facts)를 비추기만 하면 자동 인식
- **Google Gemini 멀티모달 비전 AI**: 영문 라벨, 성분표, 바코드 정밀 OCR 판독
- **3단계 신호등 안심 판정**:
  - 🟢 **국내 반입 가능 (안전)**: 자가사용 기준(6병 이내) 준수 시 통관 가능
  - 🟡 **반입 주의 (처방전 필요)**: 멜라토닌 등 국내 전문의약품 성분, 의사 처방전 필수 안내
  - 🔴 **국내 반입 불가 (폐기 대상)**: 요힘빈, 센나, 실데나필 등 차단 위해성분 검출 시 즉시 경고

### 2. "왜 반입이 안 되나요?" 국민 눈높이 상세 해설
- **건강상 위험성 & 부작용 설명**: 심근경색, 간독성, 중독성 등 인체에 미치는 구체적 위해 요인 해설
- **법적 차단 근거 안내**: 관세법 제234조(수출입금지), 약사법, 식품위생법 차단 고시 안내
- **국민 행동 요령**: 구매 전 결제 취소 방법, 세관 폐기 및 과태료 예방 안내
- **1:1 사진 대조 뷰어**: 내가 찍은 사진 vs 식품안전나라 공식 차단 DB 증거사진 비교

### 3. 식품안전나라 공식 Open API 전용 자체 SQLite DB (5,055건)
- **엑셀 완전 배제**: 정부 공식 Open API (I2715)에서 직접 수집한 5,055건의 위해식품 데이터를 자체 SQLite DB(`data/customs_safety.db`)에 영구 보관
- 원클릭 공식 DB 전체 동기화 및 실시간 검색 지원

---

## 🏗️ 시스템 아키텍처

```
customs-safety-checker/
├── server.py                  # FastAPI 웹 서버 및 REST API 엔드포인트
├── config.py                  # 환경변수 및 자체 DB 경로 설정
├── sync_food_safety_db.py     # 식품안전나라 공식 API 전건 수집 & SQLite 적재 스크립트
├── requirements.txt           # 의존성 패키지 목록
├── .env.example               # 환경변수 템플릿
├── data/
│   └── customs_safety.db      # 자체 SQLite DB (식품안전나라 공식 수집 데이터 5,055건)
├── services/
│   ├── food_safety_api.py     # 식품안전나라 I2715 Open API 수집 서비스
│   ├── db_service.py          # 자체 SQLite DB 관리 및 3단계 비교 판정
│   └── ai_vision_service.py   # Gemini 멀티모달 비전 OCR 판독 서비스
├── static/
│   ├── css/
│   │   └── style.css          # 다크/블루 톤 모던 프리미엄 CSS
│   ├── js/
│   │   ├── camera.js          # 실시간 웹캠/모바일 카메라 촬영 제어
│   │   ├── compare.js         # 1:1 사진 대조 및 상세 비교 결과 렌더러
│   │   ├── api_sync.js        # API 실시간 동기화 및 테이블 대시보드
│   │   └── app.js             # 탭 네비게이션 및 전역 초기화
│   └── assets/
│       └── logo.png           # 관세청 엠블럼
└── templates/
    └── index.html             # 싱글 페이지 반응형 웹 대시보드
```

---

## 🚀 빠른 시작 (Getting Started)

### 1. 환경 설정
`.env` 파일에 API 키를 설정합니다:
```bash
cp .env.example .env
```
`.env` 내용:
GEMINI_API_KEY=your_gemini_api_key_here
FOOD_SAFETY_API_KEY=your_food_safety_api_key_here
FOOD_SAFETY_SERVICE_ID=I2715
SAFETYKOREA_API_KEY=your_safetykorea_api_key_here
HOST=0.0.0.0
PORT=8000
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 서버 실행
```bash
python server.py
```
브라우저에서 `http://localhost:8000`에 접속하여 검사관 시스템을 이용할 수 있습니다.

---

## 🐙 GitHub 원격 저장소 연결 방법

새로운 GitHub 리포지토리(`https://github.com/`)에 올리는 방법입니다:

```bash
# 1. 새 프로젝트 폴더로 이동
cd d:\AX붐업\범정부AX\customs-safety-checker

# 2. 첫 커밋 생성
git add .
git commit -m "feat: 관세청 AI 스마트 검사관 v2.0 신규 구축"

# 3. 기본 브랜치 이름을 main으로 변경
git branch -M main

# 4. 나의 GitHub 원격 저장소 주소 연결
# (주의: <사용자아이디>를 본인의 GitHub 사용자명으로 변경하세요)
git remote add origin https://github.com/<사용자아이디>/customs-safety-checker.git

# 5. GitHub에 푸시
git push -u origin main
```
