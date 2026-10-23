/**
 * 관세청 AI 스마트 검사관 - 메인 앱 및 네비게이션 제어
 */

document.addEventListener("DOMContentLoaded", () => {
  // 탭 네비게이션
  const tabButtons = document.querySelectorAll(".nav-tab-btn");
  const tabViews = document.querySelectorAll(".tab-view");

  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.getAttribute("data-tab");
      
      tabButtons.forEach(b => b.classList.remove("active"));
      tabViews.forEach(v => v.classList.remove("active"));

      btn.classList.add("active");
      const targetView = document.getElementById(targetTab);
      if (targetView) {
        targetView.classList.add("active");
      }

      // 탭 전환 시 작업
      if (targetTab === "tabApiSync") {
        if (window.ApiSyncManager) {
          window.ApiSyncManager.checkStatus();
          window.ApiSyncManager.loadTableData();
        }
      }
    });
  });

  // 모달 닫기
  const modal = document.getElementById("detailModal");
  const btnCloseModal = document.getElementById("btnCloseModal");
  if (btnCloseModal && modal) {
    btnCloseModal.addEventListener("click", () => {
      modal.style.display = "none";
    });
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.style.display = "none";
      }
    });
  }

  // 초기 상태 로드
  if (window.ApiSyncManager) {
    window.ApiSyncManager.checkStatus();
  }
});
