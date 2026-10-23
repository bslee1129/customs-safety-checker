# 관세청 AI 위해식품·불법의약품 스마트 검사관 (Customs Safety Checker)

대한민국 관세청 및 식품의약품안전처 데이터를 연동하여, 해외직구 반입금지 위해식품과 불법의약품을 현장에서 스마트폰/웹캠으로 즉시 판독·대조하는 **범정부 AX 혁신 플랫폼**입니다.

---

## 🌟 주요 기능

### 1. 실시간 API 데이터 수집 및 동기화 (Task 1)
- **식품안전나라 공식 Open API (I2715)** 실시간 연동
- 최신 위해식품 차단정보(일련번호, 제품명, 위해성분, 제조사, 통관보류사유, 원본 이미지 등) 실시간 동기화
- 로컬 DB 자동 병합 및 인덱싱 (기존 8,000여 건 고속 검색 지원)
- 직관적인 수집 프로그레스 바 및 실시간 로그 콘솔 제공

### 2. 현품 사진 촬영 및 1:1 비교 대조 검사 (Task 2)
- **스마트폰 / 웹캠 실시간 카메라 스트리밍**: 전면/후면 카메라 전환 지원
- **사진 캡처 및 이미지 파일 업로드**: 고해상도 제품 포장, 라벨, 성분표, 바코드 촬영
- **Google Gemini 2.5 Flash 멀티모달 비전 OCR**:
  - 제품 영문/한글명, 브랜드, 바코드, 전체 성분표 자동 추출
  - 지정 차단 위해성분(Sennoside, Yohimbine, Sildenafil 등) 자동 검출
- **1:1 Side-by-Side Dual Viewer**:
  - [좌측] 현장에서 방금 촬영한 현품 사진
  - [우측] 관세청·식약처 차단 DB 등록 원본 증거사진
  - [상단 배너] 판정 결과 (통관보류 / 주의 / 정상) 및 신뢰도 일치율(%)
  - [하단 대조표] 제품명, 위해성분, 바코드, 처분 사유, 제조사 1:1 비교표

---

## 🏗️ 시스템 아키텍처

```
customs-safety-checker/
├── server.py                  # FastAPI 웹 서버 및 REST API 엔드포인트
├── config.py                  # 환경변수 및 전역 경로 설정
├── requirements.txt           # 의존성 패키지 목록
├── .env.example               # 환경변수 템플릿
├── services/
│   ├── food_safety_api.py     # 식품안전나라 I2715 Open API 수집 서비스
│   ├── db_service.py          # 8,000여 건 차단 DB 색인 및 3단계 비교 판정
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
```ini
GEMINI_API_KEY=your_gemini_api_key_here
FOOD_SAFETY_API_KEY=4856a47da3de44c7b172
FOOD_SAFETY_SERVICE_ID=I2715
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
