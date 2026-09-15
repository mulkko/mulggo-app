import { useEffect, useState } from "react";
import styles from "./stageLoadingPopup.module.css";

export interface LoadingStage {
  /** 이 시점(초) 이후부터 이 단계로 전환. 배열의 첫 stage는 0이어야 함. */
  afterSeconds: number;
  title: string;
  image?: string;
  progressPercent: number;
}

interface StageLoadingPopupProps {
  stages: LoadingStage[];
  /** 단계와 무관하게 항상 하단에 보여줄 안내문구 (예상 소요시간 등). */
  hint?: string;
}

/**
 * [2026-09-15] 사업자등록증 업로드 OCR 진행 팝업(OcrStagePopup.tsx)과 같은 톤(흰 카드 +
 * 이미지 + 진행바)으로 맞춘 범용 단계별 로딩 팝업 - 경과시간에 따라 문구/진행률만 바뀐다.
 * OcrStagePopup은 "나중에 등록" 스킵 버튼 등 OCR 전용 로직이 있어 그대로 재사용하기
 * 어려워 시각 스펙만 뽑아 새로 만들었다(사용자 확인).
 */
function StageLoadingPopup({ stages, hint }: StageLoadingPopupProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  const stage = [...stages].reverse().find((s) => elapsedSeconds >= s.afterSeconds) ?? stages[0];

  return (
    <div className={styles.overlay}>
      <div className={styles.loadingBox} role="status" aria-live="polite">
        {stage.image && <img src={stage.image} alt="" className={styles.stageImage} />}
        <div className={styles.progressTrack}>
          <div className={styles.progressFill} style={{ width: `${stage.progressPercent}%` }} />
        </div>
        <p className={styles.stageTitle}>{stage.title}</p>
        {hint && <p className={styles.hint}>{hint}</p>}
      </div>
    </div>
  );
}

export default StageLoadingPopup;
