import { useState } from "react";
import styles from "./bizCertUpload.module.css";
import ocrSearching from "../../assets/ocr_searching.png";
import ocrWriting from "../../assets/ocr_writing.png";
import ocrIdea from "../../assets/ocr_idea.png";

interface OcrStage {
  image: string;
  title: string;
  subtitle?: string;
  progressPercent: number;
}

// elapsedSeconds 기준 4단계 판정 - BizCertUpload.tsx의 elapsedSeconds(phase==="uploading" 동안
// 1초마다 증가)를 그대로 받아 판정만 여기서 한다. 60초보다 늦게 응답이 와도 4단계 그대로 유지.
function getOcrStage(elapsedSeconds: number): OcrStage {
  if (elapsedSeconds < 5) {
    return {
      image: ocrSearching,
      title: "가입하고 사업자등록증을 확인하고 있어요...",
      subtitle: "수달이 꼼꼼히 읽는 중이에요",
      progressPercent: 25,
    };
  }
  if (elapsedSeconds < 20) {
    return {
      image: ocrSearching,
      title: "사업자등록증을 한 줄씩 살펴보고 있어요...",
      subtitle: "처음이라 준비하는 데 조금 걸려요. 잠시만요!",
      progressPercent: 50,
    };
  }
  if (elapsedSeconds < 40) {
    return {
      image: ocrWriting,
      title: "거의 다 왔어요. 정보를 정리하는 중이에요...",
      progressPercent: 75,
    };
  }
  return {
    image: ocrIdea,
    title: "마지막으로 확인하고 있어요. 조금만 기다려 주세요!",
    progressPercent: 100,
  };
}

interface OcrStagePopupProps {
  elapsedSeconds: number;
  onSkip: () => void;
}

/** OCR 대기 중(phase==="uploading") 보여주는 4단계 진행 팝업. */
function OcrStagePopup({ elapsedSeconds, onSkip }: OcrStagePopupProps) {
  const stage = getOcrStage(elapsedSeconds);
  // "나중에 등록" 클릭 시 바로 onSkip을 부르지 않고 확인 팝업부터 띄운다(시나리오 14).
  // 확인 팝업 안의 "나중에 등록"만 실제로 onSkip()을 호출 - "계속 기다리기"는 이 state만
  // 닫고 OCR 대기 화면(진행 중이던 폴링)은 그대로 이어진다.
  const [confirmSkip, setConfirmSkip] = useState(false);

  return (
    <div className={styles.overlay}>
      <div className={styles.loadingBox} role="status" aria-live="polite">
        <img src={stage.image} alt="" className={styles.ocrStageImage} />
        <div className={styles.ocrProgressTrack}>
          <div className={styles.ocrProgressFill} style={{ width: `${stage.progressPercent}%` }} />
        </div>
        <p className={styles.ocrStageTitle}>{stage.title}</p>
        {stage.subtitle && <p className={styles.ocrStageSubtitle}>{stage.subtitle}</p>}
        <button type="button" className={styles.ocrSkipBtn} onClick={() => setConfirmSkip(true)}>
          나중에 등록
        </button>
      </div>

      {confirmSkip && (
        <div className={styles.skipConfirmOverlay} onClick={() => setConfirmSkip(false)}>
          <div
            className={styles.skipConfirmCard}
            role="dialog"
            aria-modal="true"
            aria-label="사업자등록증 나중에 등록"
            onClick={(e) => e.stopPropagation()}
          >
            <p className={styles.skipConfirmText}>
              사업자등록증은 나중에 등록할까요?
              <br />
              지금 가입만 먼저 끝내고, 사업자등록증은 마이페이지에서 언제든 등록할 수 있어요.
            </p>
            <div className={styles.skipConfirmButtons}>
              <button type="button" className={styles.skipConfirmCancelBtn} onClick={() => setConfirmSkip(false)}>
                계속 기다리기
              </button>
              <button type="button" className={styles.skipConfirmProceedBtn} onClick={onSkip}>
                나중에 등록
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default OcrStagePopup;
