/**
 * 관세청 AI 스마트 검사관 - 식품안전나라 API 실시간 동기화 모듈
 */

class ApiSyncManager {
  constructor() {
    this.initElements();
    this.bindEvents();
    this.currentPage = 1;
    this.currentQuery = "";
  }

  initElements() {
    this.statTotalDb = document.getElementById("statTotalDb");
    this.statApiTotal = document.getElementById("statApiTotal");
    this.statHarmfulTotal = document.getElementById("statHarmfulTotal");
    this.statImagesCount = document.getElementById("statImagesCount");

    this.btnSyncAll = document.getElementById("btnSyncAll");
    this.btnSync100 = document.getElementById("btnSync100");
    this.btnSync500 = document.getElementById("btnSync500");
    this.btnCustomSync = document.getElementById("btnCustomSync");

    this.progressBar = document.getElementById("syncProgressBar");
    this.progressContainer = document.getElementById("syncProgressContainer");
    this.consoleBox = document.getElementById("syncConsoleBox");

    this.searchInput = document.getElementById("dbSearchInput");
    this.btnSearch = document.getElementById("btnDbSearch");
    this.tableBody = document.getElementById("dbTableBody");
    this.paginationInfo = document.getElementById("paginationInfo");
    this.btnPrevPage = document.getElementById("btnPrevPage");
    this.btnNextPage = document.getElementById("btnNextPage");
  }

  bindEvents() {
    if (this.btnSyncAll) {
      this.btnSyncAll.addEventListener("click", () => this.executeSyncAll());
    }
    if (this.btnSync100) {
      this.btnSync100.addEventListener("click", () => this.executeSync(1, 100));
    }
    if (this.btnSync500) {
      this.btnSync500.addEventListener("click", () => this.executeSync(1, 500));
    }
    if (this.btnCustomSync) {
      this.btnCustomSync.addEventListener("click", () => {
        const start = parseInt(prompt("시작 번호를 입력하세요:", "1") || "1");
        const end = parseInt(prompt("종료 번호를 입력하세요 (최대 +999):", String(start + 99)) || "100");
        this.executeSync(start, end);
      });
    }

    if (this.btnSearch && this.searchInput) {
      this.btnSearch.addEventListener("click", () => {
        this.currentQuery = this.searchInput.value.trim();
        this.currentPage = 1;
        this.loadTableData();
      });
      this.searchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          this.currentQuery = this.searchInput.value.trim();
          this.currentPage = 1;
          this.loadTableData();
        }
      });
    }

    if (this.btnPrevPage) {
      this.btnPrevPage.addEventListener("click", () => {
        if (this.currentPage > 1) {
          this.currentPage--;
          this.loadTableData();
        }
      });
    }

    if (this.btnNextPage) {
      this.btnNextPage.addEventListener("click", () => {
        this.currentPage++;
        this.loadTableData();
      });
    }
  }

  log(msg) {
    if (!this.consoleBox) return;
    const time = new Date().toLocaleTimeString();
    this.consoleBox.innerHTML += `<div>[${time}] ${msg}</div>`;
    this.consoleBox.scrollTop = this.consoleBox.scrollHeight;
  }

  async checkStatus() {
    try {
      const res = await fetch("/api/stats");
      const data = await res.json();
      
      const db = data.database || {};
      const api = data.api_connection || {};

      if (this.statTotalDb) this.statTotalDb.textContent = (db.total_records || 0).toLocaleString();
      if (this.statHarmfulTotal) this.statHarmfulTotal.textContent = (db.total_harmful_ingredients || 0).toLocaleString();
      if (this.statApiTotal) {
        this.statApiTotal.textContent = api.connected 
          ? (api.total_count || 0).toLocaleString() 
          : "연결 오류";
      }
      if (this.statImagesCount) {
        this.statImagesCount.textContent = db.has_local_images ? "정상 보유 (4,700+)" : "일부 보유";
      }

      this.log(`🌐 시스템 통계 로드 완료: DB ${db.total_records}건 / 정부 서버 총 ${api.total_count || 0}건`);
    } catch (e) {
      this.log(`🚨 상태 확인 실패: ${e.message}`);
    }
  }

  async executeSyncAll() {
    if (!confirm("식품안전나라 서버의 전체 5,000여 건 차단 데이터를 전건 수집하여 자체 SQLite DB를 전면 갱신하시겠습니까?")) {
      return;
    }
    if (this.progressContainer) this.progressContainer.style.display = "block";
    if (this.progressBar) this.progressBar.style.width = "25%";

    this.log("🔄 식품안전나라 공식 Open API 전체 데이터 일괄 수집 시작...");

    try {
      if (this.progressBar) this.progressBar.style.width = "60%";
      const res = await fetch("/api/sync/all", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP 에러 ${res.status}`);

      const data = await res.json();
      if (this.progressBar) this.progressBar.style.width = "100%";

      this.log(`🎉 전체 갱신 완료! 자체 SQLite DB에 총 ${data.total_count.toLocaleString()}건 저장 완료.`);
      setTimeout(() => {
        if (this.progressContainer) this.progressContainer.style.display = "none";
      }, 1500);

      await this.checkStatus();
      this.currentPage = 1;
      this.loadTableData();
    } catch (e) {
      this.log(`🚨 전체 동기화 오류: ${e.message}`);
      if (this.progressBar) this.progressBar.style.width = "0%";
      alert(`전체 동기화 실패: ${e.message}`);
    }
  }

  async executeSync(start, end) {
    if (this.progressContainer) this.progressContainer.style.display = "block";
    if (this.progressBar) this.progressBar.style.width = "20%";

    this.log(`📥 식품안전나라 Open API(I2715) ${start}~${end} 구간 데이터 수집 요청 중...`);

    try {
      if (this.progressBar) this.progressBar.style.width = "50%";
      const res = await fetch("/api/sync/fetch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start, end, download_images: false })
      });

      if (!res.ok) {
        throw new Error(`HTTP 에러 ${res.status}`);
      }

      if (this.progressBar) this.progressBar.style.width = "90%";
      const data = await res.json();

      this.log(`✅ 동기화 완료! 수집: ${data.fetched_count}건, 신규 추가: ${data.newly_added_count}건 (현재 총 ${data.total_db_count}건)`);
      if (this.progressBar) this.progressBar.style.width = "100%";

      setTimeout(() => {
        if (this.progressContainer) this.progressContainer.style.display = "none";
      }, 1200);

      // 통계 및 테이블 갱신
      await this.checkStatus();
      this.loadTableData();
    } catch (e) {
      this.log(`🚨 수집 중 오류: ${e.message}`);
      if (this.progressBar) this.progressBar.style.width = "0%";
      alert(`API 수집 오류: ${e.message}`);
    }
  }

  async loadTableData() {
    if (!this.tableBody) return;
    this.tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem;">데이터 로딩 중...</td></tr>`;

    try {
      const url = `/api/drugs?q=${encodeURIComponent(this.currentQuery)}&page=${this.currentPage}&page_size=15`;
      const res = await fetch(url);
      const data = await res.json();

      const items = data.items || [];
      if (items.length === 0) {
        this.tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #64748b;">검색 결과가 없습니다.</td></tr>`;
        return;
      }

      let html = "";
      for (const item of items) {
        const seq = item.등록번호 || "-";
        const name = item.제품명 || "-";
        const barcode = item.바코드명 || "-";
        const ingr = item.성분명 || "-";
        const reason = item.통관보류사유내용 || "위해성분 검출";
        const hasLocal = item.로컬이미지존재;

        html += `
          <tr>
            <td><code>${seq}</code></td>
            <td style="font-weight: 600;">${this.escapeHtml(name)}</td>
            <td><code>${this.escapeHtml(barcode)}</code></td>
            <td><span class="tag-harmful">${this.escapeHtml(ingr)}</span></td>
            <td style="color: #f87171;">${this.escapeHtml(reason)}</td>
            <td>
              <button class="btn btn-secondary" style="padding: 0.35rem 0.75rem; font-size: 0.78rem;" 
                onclick="window.ApiSyncManager.showDetailModal('${seq}', '${encodeURIComponent(JSON.stringify(item))}')">
                <i class="fa-solid fa-magnifying-glass"></i> ${hasLocal ? "사진 대조" : "상세"}
              </button>
            </td>
          </tr>
        `;
      }

      this.tableBody.innerHTML = html;

      // 페이징 업데이트
      const total = data.total || 0;
      const totalPages = Math.ceil(total / 15) || 1;
      if (this.paginationInfo) {
        this.paginationInfo.textContent = `${this.currentPage} / ${totalPages} 페이지 (총 ${total.toLocaleString()}건)`;
      }
      if (this.btnPrevPage) this.btnPrevPage.disabled = (this.currentPage <= 1);
      if (this.btnNextPage) this.btnNextPage.disabled = (this.currentPage >= totalPages);

    } catch (e) {
      this.tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #ef4444;">로드 실패: ${e.message}</td></tr>`;
    }
  }

  showDetailModal(seq, encodedItem) {
    const item = JSON.parse(decodeURIComponent(encodedItem));
    const modal = document.getElementById("detailModal");
    const modalBody = document.getElementById("modalBodyContent");
    if (!modal || !modalBody) return;

    let imgHtml = "";
    if (item.로컬이미지존재) {
      imgHtml = `<img src="/api/image/local/${seq}" style="max-height: 280px; width: auto; border-radius: 8px; margin-bottom: 1rem; border: 1px solid rgba(255,255,255,0.1);">`;
    } else if (item.원본이미지URL) {
      const u = item.원본이미지URL.split(",")[0].trim();
      imgHtml = `<img src="${u}" style="max-height: 280px; width: auto; border-radius: 8px; margin-bottom: 1rem; border: 1px solid rgba(255,255,255,0.1);">`;
    }

    modalBody.innerHTML = `
      <div style="text-align: center;">${imgHtml}</div>
      <table class="detail-table">
        <tr><th>등록번호</th><td><code>${item.등록번호}</code></td></tr>
        <tr><th>제품명</th><td><strong>${item.제품명}</strong></td></tr>
        <tr><th>위해성분</th><td><span class="tag-harmful">${item.성분명}</span></td></tr>
        <tr><th>바코드</th><td><code>${item.바코드명 || '없음'}</code></td></tr>
        <tr><th>차단사유</th><td style="color:#f87171;">${item.통관보류사유내용 || '위해성분 검출'}</td></tr>
        <tr><th>제조사/국가</th><td>${item.제조사명 || '-'} / ${item.제조국가명 || '-'}</td></tr>
        <tr><th>등록일자</th><td>${item.등록일자 || '-'}</td></tr>
      </table>
    `;

    modal.style.display = "flex";
  }

  escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
}

window.ApiSyncManager = new ApiSyncManager();
