import sys
import time
from services.food_safety_api import food_safety_api
from services.db_service import db_service

def run_sync():
    print("=" * 60)
    print(" [식품안전나라 공식 Open API -> 자체 SQLite DB 갱신 작업] ")
    print("=" * 60)

    # 1. API 상태 및 총 건수 확인
    status = food_safety_api.get_status()
    if not status.get("connected"):
        print(f"[ERROR] 식품안전나라 API 연결 실패: {status.get('error')}")
        return False

    total_count = status.get("total_count", 0)
    print(f"[1/3] 식품안전나라 API 연결 성공! 총 차단 데이터 건수: {total_count:,}건")

    # 2. 전체 데이터 일괄 수집 (1000건 단위)
    print(f"[2/3] API 데이터 전건 수집 시작...")
    start_time = time.time()
    fetch_result = food_safety_api.fetch_all_records(batch_size=1000)
    
    if not fetch_result.get("success"):
        print(f"[ERROR] API 수집 실패: {fetch_result.get('error')}")
        return False

    records = fetch_result.get("rows", [])
    elapsed = time.time() - start_time
    print(f"[SUCCESS] API 데이터 {len(records):,}건 수집 완료 (소요시간: {elapsed:.2f}초)")

    # 3. 자체 SQLite DB에 전량 교체 저장
    print(f"[3/3] 자체 SQLite DB (customs_safety.db)에 전량 갱신 적재 중...")
    inserted = db_service.replace_all_from_api(records)
    print(f"[SUCCESS] 자체 SQLite DB 적재 완료! 총 {inserted:,}건 등록됨.")

    # 4. 검증 및 통계 출력
    stats = db_service.get_stats()
    print("\n" + "=" * 60)
    print(" [자체 DB 갱신 결과 통계] ")
    print(f" - DB 파일 경로: {stats['db_file']}")
    print(f" - 총 위해식품 차단 데이터 건수: {stats['total_records']:,}건")
    print(f" - 등록된 바코드 수: {stats['total_barcodes']:,}개")
    print(f" - 식별된 위해성분 종류: {stats['total_harmful_ingredients']:,}개")
    print(f" - 최종 동기화 일시: {stats['last_sync_time']}")
    print("=" * 60)

    # 최신 3건 샘플 미리보기
    sample_res = db_service.search(page=1, page_size=3)
    print("\n[최신 등록 샘플 3건]")
    for idx, item in enumerate(sample_res["items"], 1):
        print(f" {idx}. [{item.get('등록번호')}] {item.get('제품명')} (성분: {item.get('성분명')}) / {item.get('정보출처')}")

    return True

if __name__ == "__main__":
    success = run_sync()
    if not success:
        sys.exit(1)
