import { useEffect, useState } from "react";
import styles from "./stageLoadingPopup.module.css";

export interface LoadingStage {
  /** 이 시점(초) 이후부터 이 단계로 전환. 배열의 첫 stage는 0이어야 함. */
  afterSeconds: number;
  title: string;
  image?: string;
}

interface StageLoadingPopupProps {
  stages: LoadingStage[];
  /** 단계와 무관하게 항상 하단에 보여줄 안내문구 (예상 소요시간 등). */
  hint?: string;
  /** 실제 응답이 와서 완료됐는지 - true가 되면 진행바를 100%로 채운 뒤 onDone을 부른다. */
  ready: boolean;
  /** 100% 완료 애니메이션(0.3초)까지 다 보여준 다음 호출된다 - 보통 다음 화면 이동. */
  onDone: () => void;
  /** 진행바가 fillPercent까지 서서히 차오르는 데 걸리는 예상 시간(초). */
  maxSeconds?: number;
  fillPercent?: number;
}

const DEFAULT_MAX_SECONDS = 10;
const DEFAULT_FILL_PERCENT = 92;

/**
 * [2026-09-15, 사용자 확인] 진행바 처리를 ReportWaitPopup(diagnosis/ReportWaitPopup.tsx)과
 * 동일 방식으로 통일 - maxSeconds 동안 fillPercent까지 서서히 채우고 대기하다가, 실제
 * 응답(ready)이 오면 100%로 스냅한 뒤 0.3초 뒤 onDone을 부른다. 다만 이 컴포넌트는
 * ReportWaitPopup과 달리 경과시간에 따라 이미지·문구가 여러 단계로 바뀔 수 있다(stages) -
 * 진행바 채움 자체는 단계와 무관하게 하나로 쭉 이어진다(단계별로 progressPercent를
 * 따로 두지 않음).
 */
function StageLoadingPopup({
  stages,
  hint,
  ready,
  onDone,
  maxSeconds = DEFAULT_MAX_SECONDS,
  fillPercent = DEFAULT_FILL_PERCENT,
}: StageLoadingPopupProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [pct, setPct] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    // 마운트 직후 0% -> fillPercent로 바꿔야 CSS transition이 실제로 애니메이션된다
    // (처음부터 그 값으로 렌더되면 transition이 안 먹음) - 다음 페인트 프레임에 올린다.
    const id = requestAnimationFrame(() => setPct(fillPercent));
    return () => cancelAnimationFrame(id);
  }, [fillPercent]);

  useEffect(() => {
    if (!ready) return;
    setPct(100);
    const timer = setTimeout(onDone, 300);
    return () => clearTimeout(timer);
  }, [ready, onDone]);

  const stage = [...stages].reverse().find((s) => elapsedSeconds >= s.afterSeconds) ?? stages[0];

  return (
    <div className={styles.overlay}>
      <div className={styles.loadingBox} role="status" aria-live="polite">
        {stage.image && <img src={stage.image} alt="" className={styles.stageImage} />}
        <div className={styles.progressTrack}>
          <div
            className={styles.progressFill}
            style={{ width: `${pct}%`, transitionDuration: pct >= 100 ? "0.3s" : `${maxSeconds}s` }}
          />
        </div>
        <p className={styles.stageTitle}>{stage.title}</p>
        {hint && <p className={styles.hint}>{hint}</p>}
      </div>
    </div>
  );
}

export default StageLoadingPopup;
