import { useEffect, useState } from "react";
import styles from "./reportWaitPopup.module.css";
import reportWaitImage from "../../assets/ocr_searching.png";

export const REPORT_WAIT_MAX_SECONDS = 10;
const REPORT_WAIT_FILL_PERCENT = 92;

// "최대 N초 소요" / "최대 1분 소요" / "최대 1분 30초 소요" - 60초 넘어가는 화면(예: 서류
// 채우기)도 쓰게 되면서 초 단위만으로는 안 읽혀 분 단위까지 지원.
function formatMaxWaitLabel(seconds: number): string {
  if (seconds < 60) return `${seconds}초`;
  const minutes = Math.floor(seconds / 60);
  const restSeconds = seconds % 60;
  return restSeconds === 0 ? `${minutes}분` : `${minutes}분 ${restSeconds}초`;
}

interface ReportWaitPopupProps {
  title: string;
  /** 실제 응답이 와서 완료됐는지 - true가 되면 진행바를 100%로 채운 뒤 onDone을 부른다. */
  ready: boolean;
  /** 100% 완료 애니메이션(0.3초)까지 다 보여준 다음 호출된다 - 보통 다음 화면 이동. */
  onDone: () => void;
  maxSeconds?: number;
  /** [2026-09-15, 사용자 확인] 업종코드 매칭처럼 소요시간 예측이 덜 중요한 화면에서
   * 하단 힌트의 "(최대 N초 소요)" 표기만 빼고 싶을 때 true. */
  hideEtaHint?: boolean;
}

/** "OO 분석/처리 중" 대기 팝업 - BizCertUpload/OcrStagePopup, StageLoadingPopup과 같은
 * 카드+일러스트+진행바 구성. 저쪽들은 경과시간 기준 여러 단계로 이미지/문구가 바뀌지만,
 * 여기는 실제 API 응답을 기다리는 동안 이미지·문구가 고정이고 진행바만 maxSeconds에
 * 맞춰 서서히 채워진다 - 실제 응답이 더 걸려도 어색해 보이지 않게 REPORT_WAIT_FILL_PERCENT
 * 까지만 채우고 대기하다가, ready가 true가 되는 순간 100%로 완료 처리한다.
 * diagnosis(업종코드/리포트 분석 대기)·matching(서류 채우기 대기) 등 여러 화면이 공유. */
function ReportWaitPopup({
  title,
  ready,
  onDone,
  maxSeconds = REPORT_WAIT_MAX_SECONDS,
  hideEtaHint,
}: ReportWaitPopupProps) {
  const [pct, setPct] = useState(0);

  useEffect(() => {
    // 마운트 직후 0% -> FILL_PERCENT로 바꿔야 CSS transition이 실제로 애니메이션된다
    // (처음부터 그 값으로 렌더되면 transition이 안 먹음) - 다음 페인트 프레임에 올린다.
    const id = requestAnimationFrame(() => setPct(REPORT_WAIT_FILL_PERCENT));
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    if (!ready) return;
    setPct(100);
    const timer = setTimeout(onDone, 300);
    return () => clearTimeout(timer);
  }, [ready, onDone]);

  return (
    <div className={styles.overlay}>
      <div className={styles.loadingBox} role="status" aria-live="polite">
        <img src={reportWaitImage} alt="" className={styles.image} />
        <div className={styles.progressTrack}>
          <div
            className={styles.progressFill}
            style={{
              width: `${pct}%`,
              transitionDuration: pct >= 100 ? "0.3s" : `${maxSeconds}s`,
            }}
          />
        </div>
        <p className={styles.title}>{title}</p>
        <p className={styles.hint}>
          잠시만 기다려주세요{hideEtaHint ? "" : ` (최대 ${formatMaxWaitLabel(maxSeconds)} 소요)`}
        </p>
      </div>
    </div>
  );
}

export default ReportWaitPopup;
