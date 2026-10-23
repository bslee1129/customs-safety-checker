/**
 * 관세청 AI 스마트 검사관 - 1:1 사진 대조 및 검사 결과 뷰어
 */

class ComparisonViewer {
  constructor() {
    this.container = document.getElementById("inspectionResultContainer");
    this.photoPreview = document.getElementById("inspectPhotoPreview");
    this.dbPhotoPreview = document.getElementById("dbPhotoPreview");
    this.verdictBanner = document.getElementById("verdictBanner");
    this.verdictTitle = document.getElementById("verdictTitle");
    this.verdictDesc = document.getElementById("verdictDesc");
    this.verdictScore = document.getElementById("verdictScore");
    this.detailTableBody = document.getElementById("detailTableBody");
    this.emptyState = document.getElementById("inspectionEmptyState");

    this.bindManualSearch();
  }

  bindManualSearch() {
    const btnManual = document.getElementById("btnManualInspect");
    if (btnManual) {
      btnManual.addEventListener("click", () => this.handleManualSearch());
    }
  }

  async handleManualSearch() {
    const inputName = document.getElementById("inputManualName");
    const inputBarcode = document.getElementById("inputManualBarcode");
    const inputIngr = document.getElementById("inputManualIngr");

    const productName = inputName ? inputName.value.trim() : "";
    if (!productName) {
      alert("제품명을 입력해 주세요.");
      return;
    }

    const payload = {
      product_name: productName,
      barcode: inputBarcode ? inputBarcode.value.trim() : "",
      ingredients: inputIngr && inputIngr.value.trim() 
        ? inputIngr.value.split(",").map(s => s.trim()).filter(Boolean)
        : []
    };

    try {
      const res = await fetch("/api/inspect/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      this.render(data);
    } catch (e) {
      alert(`조회 실패: ${e.message}`);
    }
  }

  render(result) {
    if (!result || !result.match_result) return;

    if (this.emptyState) this.emptyState.style.display = "none";
    if (this.container) this.container.style.display = "block";

    const match = result.match_result;
    const ai = result.ai_extracted || {};
    const record = match.record || {};

    // 1. 현품 촬영 사진 렌더링
    if (this.photoPreview) {
      if (result.inspected_photo_preview) {
        this.photoPreview.src = result.inspected_photo_preview;
        this.photoPreview.style.display = "block";
      } else {
        this.photoPreview.src = "";
        this.photoPreview.style.display = "none";
      }
    }

    // 2. DB 등록 원본 사진 렌더링
    if (this.dbPhotoPreview) {
      const dbImgWrap = document.getElementById("dbPhotoWrap");
      const noDbImgText = document.getElementById("noDbImageText");

      let imgSrc = "";
      if (result.db_image_api_url) {
        imgSrc = result.db_image_api_url;
      } else if (result.db_remote_image_url) {
        // 쉼표로 여러 개 있을 경우 첫 번째 URL
        imgSrc = result.db_remote_image_url.split(",")[0].trim();
      }

      if (imgSrc) {
        this.dbPhotoPreview.src = imgSrc;
        this.dbPhotoPreview.style.display = "block";
        if (noDbImgText) noDbImgText.style.display = "none";
      } else {
        this.dbPhotoPreview.style.display = "none";
        if (noDbImgText) noDbImgText.style.display = "flex";
      }
    }

    // 3. 판정 배너 상태 렌더링
    const status = (match.status || "PASS").toLowerCase();
    this.verdictBanner.className = `verdict-banner ${status}`;

    let iconHtml = '<i class="fa-solid fa-circle-check"></i>';
    if (status === "danger") iconHtml = '<i class="fa-solid fa-triangle-exclamation"></i>';
    else if (status === "warning") iconHtml = '<i class="fa-solid fa-circle-exclamation"></i>';

    this.verdictTitle.innerHTML = `${iconHtml} ${match.verdict}`;
    this.verdictDesc.textContent = match.match_reason || "특이사항이 발견되지 않았습니다.";
    this.verdictScore.textContent = `${match.confidence || 0}%`;

    // 4. 상세 대조 테이블 렌더링
    this.renderDetailTable(ai, record, match);

    // 모바일 등에서 결과 위치로 부드럽게 스크롤
    this.container.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  renderDetailTable(ai, db, match) {
    if (!this.detailTableBody) return;

    const rows = [
      {
        label: "판정 단계",
        content: `<strong>${match.match_stage || "일반 대조"}</strong>`
      },
      {
        label: "제품명",
        content: `
          <div><strong>[현품 AI 판독]</strong> ${this.escapeHtml(ai.product_name || "미인식")}</div>
          <div style="color: #94a3b8; font-size: 0.82rem; margin-top: 2px;">
            <strong>[DB 등록명]</strong> ${this.escapeHtml(db.제품명 || match.db_product_name || "해당 없음")}
          </div>
        `
      },
      {
        label: "위해 성분",
        content: this.formatIngredients(match.db_harmful_ingredient || ai.harmful_suspects)
      },
      {
        label: "바코드",
        content: `
          <span>현품: <code>${ai.barcode || "인식안됨"}</code></span>
          <span style="margin: 0 8px; color: #64748b;">|</span>
          <span>DB: <code>${db.바코드명 || "해당 없음"}</code></span>
        `
      },
      {
        label: "처분/사유",
        content: `<span style="color: ${match.status === 'DANGER' ? '#f87171' : '#fbbf24'}; font-weight: 600;">
          ${this.escapeHtml(db.통관보류사유내용 || match.db_reason || "통관 가능")}
        </span>`
      },
      {
        label: "제조사 / 출처",
        content: `${this.escapeHtml(db.제조사명 || ai.brand || "미상")} (${this.escapeHtml(db.정보출처 || "공공DB")})`
      }
    ];

    let html = "";
    for (const r of rows) {
      html += `
        <tr>
          <th>${r.label}</th>
          <td>${r.content}</td>
        </tr>
      `;
    }
    this.detailTableBody.innerHTML = html;
  }

  formatIngredients(ingredients) {
    if (!ingredients) return '<span style="color: #64748b;">검출 없음</span>';
    let list = [];
    if (Array.isArray(ingredients)) {
      list = ingredients;
    } else {
      list = ingredients.split(/[,;/+]/).map(s => s.trim()).filter(Boolean);
    }

    if (list.length === 0) return '<span style="color: #64748b;">검출 없음</span>';

    return list.map(item => `<span class="tag-harmful">${this.escapeHtml(item)}</span>`).join(" ");
  }

  escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
}

window.ComparisonViewer = new ComparisonViewer();
