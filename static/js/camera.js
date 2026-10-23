/**
 * 관세청 AI 스마트 검사관 - 카메라 제어 및 사진 캡처 모듈
 */

class CameraManager {
  constructor() {
    this.videoElement = document.getElementById("cameraVideo");
    this.canvasElement = document.getElementById("capturedPhotoCanvas");
    this.stream = null;
    this.currentFacingMode = "environment"; // 모바일 기본: 후면 카메라
    this.isScanning = false;
    this.capturedBlob = null;

    this.initElements();
    this.bindEvents();
  }

  initElements() {
    this.btnStart = document.getElementById("btnStartCamera");
    this.btnCapture = document.getElementById("btnCapturePhoto");
    this.btnSwitch = document.getElementById("btnSwitchCamera");
    this.btnUploadTrigger = document.getElementById("btnUploadTrigger");
    this.fileInput = document.getElementById("filePhotoInput");
    this.scannerLine = document.getElementById("laserScannerLine");
    this.cameraStatusText = document.getElementById("cameraStatusText");
  }

  bindEvents() {
    if (this.btnStart) {
      this.btnStart.addEventListener("click", () => this.startCamera());
    }
    if (this.btnCapture) {
      this.btnCapture.addEventListener("click", () => this.captureAndInspect());
    }
    if (this.btnSwitch) {
      this.btnSwitch.addEventListener("click", () => this.switchCamera());
    }
    if (this.btnUploadTrigger && this.fileInput) {
      this.btnUploadTrigger.addEventListener("click", () => this.fileInput.click());
      this.fileInput.addEventListener("change", (e) => this.handleFileUpload(e));
    }
  }

  async startCamera() {
    try {
      if (this.stream) {
        this.stopCamera();
      }

      this.updateStatus("카메라 연결 중...", "warning");
      const constraints = {
        video: {
          facingMode: this.currentFacingMode,
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        },
        audio: false
      };

      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.videoElement.srcObject = this.stream;
      await this.videoElement.play();

      this.updateStatus("실시간 카메라 가동 중 (촬영 대기)", "success");
      if (this.btnCapture) this.btnCapture.disabled = false;
      if (this.btnStart) this.btnStart.style.display = "none";
    } catch (err) {
      console.error("카메라 실행 오류:", err);
      this.updateStatus("카메라 접근 실패. 파일 업로드 기능을 이용해 주세요.", "danger");
      alert("카메라를 켤 수 없습니다. 브라우저의 카메라 권한을 확인해 주시거나 [사진 파일 업로드]를 이용해 주세요.");
    }
  }

  stopCamera() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
  }

  async switchCamera() {
    this.currentFacingMode = (this.currentFacingMode === "environment") ? "user" : "environment";
    await this.startCamera();
  }

  setScanning(active) {
    this.isScanning = active;
    if (this.scannerLine) {
      this.scannerLine.style.display = active ? "block" : "none";
    }
    if (this.btnCapture) {
      this.btnCapture.disabled = active;
    }
  }

  updateStatus(text, type = "normal") {
    if (!this.cameraStatusText) return;
    this.cameraStatusText.textContent = text;
    this.cameraStatusText.className = "status-badge " + type;
  }

  async captureAndInspect() {
    if (!this.videoElement || !this.stream) {
      alert("먼저 카메라를 시작해 주세요.");
      return;
    }

    // 캔버스에 비디오 프레임 그리기
    const width = this.videoElement.videoWidth || 1280;
    const height = this.videoElement.videoHeight || 720;
    this.canvasElement.width = width;
    this.canvasElement.height = height;

    const ctx = this.canvasElement.getContext("2d");
    ctx.drawImage(this.videoElement, 0, 0, width, height);

    this.canvasElement.toBlob(async (blob) => {
      if (!blob) {
        alert("사진 캡처에 실패했습니다.");
        return;
      }
      this.capturedBlob = blob;
      await this.sendPhotoForInspection(blob);
    }, "image/jpeg", 0.92);
  }

  async handleFileUpload(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    this.capturedBlob = file;
    await this.sendPhotoForInspection(file);
    // 입력 리셋
    event.target.value = "";
  }

  async sendPhotoForInspection(blobOrFile) {
    this.setScanning(true);
    this.updateStatus("AI 멀티모달 Vision 분석 & DB 1:1 대조 중...", "warning");

    const formData = new FormData();
    formData.append("file", blobOrFile, "inspect_photo.jpg");

    // 바코드 힌트 입력값이 있으면 전달
    const barcodeInput = document.getElementById("inputBarcodeHint");
    if (barcodeInput && barcodeInput.value.trim()) {
      formData.append("barcode_hint", barcodeInput.value.trim());
    }

    try {
      const response = await fetch("/api/inspect/photo", {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "검사 요청 처리 중 서버 오류");
      }

      const result = await response.json();
      console.log("검사 결과:", result);

      // 1:1 비교 대조 뷰어에 렌더링
      if (window.ComparisonViewer) {
        window.ComparisonViewer.render(result);
      }

      this.updateStatus("AI 분석 및 1:1 대조 완료", "success");
    } catch (err) {
      console.error("검사 실패:", err);
      alert(`검사 오류 발생: ${err.message}`);
      this.updateStatus("검사 오류 발생", "danger");
    } finally {
      this.setScanning(false);
    }
  }
}

window.CameraManager = new CameraManager();
