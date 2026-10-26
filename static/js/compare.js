/**
 * 관세청·식약처 국민비서 - 해외직구 의약품 안심 통관 체커
 * 대국민 맞춤 1:1 사진 대조 및 반입 가능 여부·사유 상세 해설 렌더러
 */

class ComparisonViewer {
  constructor() {
    this.container = document.getElementById("inspectionResultContainer");
    this.emptyState = document.getElementById("inspectionEmptyState");
    this.photoPreview = document.getElementById("inspectPhotoPreview");
    this.dbPhotoPreview = document.getElementById("dbPhotoPreview");
    this.dbPhotoWrap = document.getElementById("dbPhotoWrap");
    this.noDbImageText = document.getElementById("noDbImageText");

    // 대국민 결과 UI 요소
    this.verdictBanner = document.getElementById("verdictBanner");
    this.verdictBadge = document.getElementById("verdictBadge");
    this.verdictHeadline = document.getElementById("verdictHeadline");
    this.verdictScore = document.getElementById("verdictScore");

    // 대국민 Q&A 카드
    this.whyProhibitedBox = document.getElementById("whyProhibitedBox");
    this.whyProhibitedText = document.getElementById("whyProhibitedText");
    this.healthRisksText = document.getElementById("healthRisksText");
    this.actionGuideBox = document.getElementById("actionGuideBox");
    this.actionGuideText = document.getElementById("actionGuideText");
    this.customsRuleText = document.getElementById("customsRuleText");

    // 상세 대조표
    this.detailTableBody = document.getElementById("detailTableBody");

    this.bindManualSearch();
  }

  bindManualSearch() {
    const btnManual = document.getElementById("btnManualInspect");
    if (btnManual) {
      btnManual.addEventListener("click", () => this.handleManualSearch());
    }
    const inputName = document.getElementById("inputManualName");
    if (inputName) {
      inputName.addEventListener("keypress", (e) => {
        if (e.key === "Enter") this.handleManualSearch();
      });
    }
  }

  async handleManualSearch() {
    const inputName = document.getElementById("inputManualName");
    const inputBarcode = document.getElementById("inputManualBarcode");
    const inputIngr = document.getElementById("inputManualIngr");

    const productName = inputName ? inputName.value.trim() : "";
    if (!productName) {
      alert("조회할 약/영양제 제품명을 입력해 주세요.");
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
    const citizen = match.citizen_summary || {};
    const record = match.record || {};
    const status = (match.status || "PASS").toLowerCase();

    // 1. 현품 촬영 사진 표시
    if (this.photoPreview) {
      if (result.inspected_photo_preview) {
        this.photoPreview.src = result.inspected_photo_preview;
        this.photoPreview.style.display = "block";
      } else {
        this.photoPreview.src = "";
        this.photoPreview.style.display = "none";
      }
    }

    // 2. 정부 차단 DB 원본 등록 사진 표시
    if (this.dbPhotoPreview) {
      let imgSrc = "";
      if (result.db_image_api_url) {
        imgSrc = result.db_image_api_url;
      } else if (result.db_remote_image_url) {
        imgSrc = result.db_remote_image_url.split(",")[0].trim();
      }

      if (imgSrc) {
        this.dbPhotoPreview.src = imgSrc;
        this.dbPhotoPreview.style.display = "block";
        if (this.noDbImageText) this.noDbImageText.style.display = "none";
      } else {
        this.dbPhotoPreview.style.display = "none";
        if (this.noDbImageText) this.noDbImageText.style.display = "flex";
      }
    }

    // 3. 대국민 신호등 판정 배너 업데이트
    if (this.verdictBanner) {
      this.verdictBanner.className = `citizen-verdict-banner ${status}`;
    }

    if (this.verdictBadge) {
      this.verdictBadge.className = `verdict-badge-pill ${status}`;
      this.verdictBadge.innerHTML = citizen.badge_text || match.verdict;
    }

    if (this.verdictHeadline) {
      this.verdictHeadline.textContent = citizen.headline || match.match_reason;
    }

    if (this.verdictScore) {
      this.verdictScore.textContent = `${match.confidence || 95}%`;
    }

    // 4. "왜 반입이 안 되나요?" 상세 설명 업데이트
    if (this.whyProhibitedText) {
      this.whyProhibitedText.textContent = citizen.why_prohibited || "확인된 차단 사유가 없습니다.";
    }
    if (this.healthRisksText) {
      this.healthRisksText.textContent = citizen.health_risks || "제품 권장량을 준수하여 복용하세요.";
    }

    // 5. "어떻게 해야 하나요?" 행동 요령 업데이트
    if (this.actionGuideText) {
      this.actionGuideText.textContent = citizen.action_guide || "자가사용 6병 이내 기준을 준수하세요.";
    }
    if (this.customsRuleText) {
      this.customsRuleText.textContent = citizen.customs_rule || "건강기능식품·의약품은 1인당 최대 6병까지 자가사용 면세 통관이 가능합니다.";
    }

    // 카드 테두리 색상 테마 조정
    if (this.whyProhibitedBox) {
      this.whyProhibitedBox.className = `citizen-info-card ${status}`;
    }
    if (this.actionGuideBox) {
      this.actionGuideBox.className = `citizen-info-card action ${status}`;
    }

    // 6. 1:1 상세 대조 테이블 렌더링
    this.renderDetailTable(ai, record, match, citizen);

    // 부드러운 스크롤 이동
    this.container.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  renderDetailTable(ai, db, match, citizen) {
    if (!this.detailTableBody) return;

    const isDanger = match.status === "DANGER";
    const isWarning = match.status === "WARNING";

    const rows = [
      {
        label: "반입 판정",
        content: `
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <strong style="color: ${isDanger ? '#ef4444' : isWarning ? '#f59e0b' : '#10b981'}; font-size: 1.05rem;">
              ${citizen.badge_text || match.verdict}
            </strong>
            <span style="font-size: 0.8rem; color: var(--text-muted);">(${match.match_stage})</span>
          </div>
        `
      },
      {
        label: "제품명",
        content: `
          <div><strong>[사진 판독]</strong> ${this.escapeHtml(ai.product_name || "미인식")} ${ai.product_name_ko ? `<span style="color:#94a3b8;">(${this.escapeHtml(ai.product_name_ko)})</span>` : ''}</div>
          ${db.제품명 ? `<div style="color: #cbd5e1; font-size: 0.85rem; margin-top: 4px;"><strong>[정부 차단명]</strong> ${this.escapeHtml(db.제품명)}</div>` : ''}
        `
      },
      {
        label: "분류 / 브랜드",
        content: `<span>${this.escapeHtml(ai.category || "해외 의약품/건강식품")}</span> | <span>제조사: <strong>${this.escapeHtml(ai.brand || db.제조사명 || "확인 중")}</strong></span>`
      },
      {
        label: "성분표 분석",
        content: `
          <div>${this.formatIngredients(match.db_harmful_ingredient || ai.harmful_suspects || ai.ingredients)}</div>
        `
      },
      {
        label: "바코드 식별",
        content: `
          <span>현품 라벨: <code>${ai.barcode || "미인식 (라벨 촬영 권장)"}</code></span>
          ${db.바코드명 ? `<span style="margin: 0 8px; color: #64748b;">|</span><span>공식 차단 바코드: <code>${db.바코드명}</code></span>` : ''}
        `
      },
      {
        label: "관련 법적 근거",
        content: `<span style="color: #93c5fd; font-size: 0.85rem;">${citizen.legal_basis || "관세법 제234조 및 약사법 / 수입식품안전관리 특별법"}</span>`
      }
    ];

    let html = "";
    for (const r of rows) {
      html += `
        <tr>
          <th style="width: 28%;">${r.label}</th>
          <td>${r.content}</td>
        </tr>
      `;
    }
    this.detailTableBody.innerHTML = html;
  }

  formatIngredients(ingredients) {
    if (!ingredients) return '<span style="color: #64748b;">검출된 특이 유해성분 없음</span>';
    let list = [];
    if (Array.isArray(ingredients)) {
      list = ingredients;
    } else {
      list = String(ingredients).split(/[,;/+]/).map(s => s.trim()).filter(Boolean);
    }

    if (list.length === 0) return '<span style="color: #64748b;">검출된 특이 유해성분 없음</span>';

    return list.map(item => `<span class="tag-harmful"><i class="fa-solid fa-triangle-exclamation"></i> ${this.escapeHtml(item)}</span>`).join(" ");
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
