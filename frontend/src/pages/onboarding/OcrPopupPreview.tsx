import { useState } from "react";
import OcrStagePopup from "../../components/BizCertUpload/OcrStagePopup";

const STAGE_SECONDS = [0, 5, 20, 40];

/**
 * [개발용 미리보기] OcrStagePopup(사업자등록증 OCR 대기 4단계 팝업)을 실제 OCR
 * 호출 없이 바로 확인하기 위한 페이지. /dev/ocr-popup-preview 라우트로만 연결된다.
 */
function OcrPopupPreview() {
  const [elapsedSeconds, setElapsedSeconds] = useState(STAGE_SECONDS[0]);

  return (
    <div style={{ padding: 24 }}>
      {/* OcrStagePopup 내부 .overlay가 position:fixed + z-index:200으로 화면 전체를
          덮어서, 이 버튼들이 그 아래(뒤)에 깔려 클릭이 안 먹었다(사용자 확인) -
          버튼 행에 더 높은 z-index를 줘서 overlay 위로 올린다. */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, position: "relative", zIndex: 201 }}>
        {STAGE_SECONDS.map((seconds, index) => (
          <button
            key={seconds}
            type="button"
            onClick={() => setElapsedSeconds(seconds)}
            style={{ padding: "8px 14px", cursor: "pointer" }}
          >
            {index + 1}단계
          </button>
        ))}
      </div>
      <OcrStagePopup elapsedSeconds={elapsedSeconds} onSkip={() => console.log("onSkip 호출됨")} />
    </div>
  );
}

export default OcrPopupPreview;
