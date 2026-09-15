import { useEffect, useState } from "react";
import styles from "../../styles/diagnosis.module.css";
import reportWaitImage from "../../assets/ocr_searching.png";

// [2026-09-15] 실제 대기시간 실측치 - backend/api/diagnosis.py 주석
// (51~53행: 업종코드 매칭 11~13초는 이 팝업이 뜨기 전에 이미 끝나 있고, 그 다음 단계인
// 리포트 생성만 추가 7~9초 소요) + 371~373행(후보 최대 3개를 스레드풀로 병렬 실행하도록
// 고쳐서 후보 수만큼 배로 늘어나지 않음) 기준. DiagnosisIndustryResult(최초 폴링)와
// DiagnosisReport(같은 report 엔드포인트를 다시 확인)가 기다리는 대상이 동일해서 두
// 화면 모두 이 값을 공유한다.
export const REPORT_WAIT_MAX_SECONDS = 10;
const REPORT_WAIT_FILL_PERCENT = 92;

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

/** "리포트 분석 중" 대기 팝업 - BizCertUpload/OcrStagePopup과 같은 카드+일러스트+진행바
 * 구성. 저쪽은 경과시간 기준 4단계로 이미지/문구가 바뀌지만, 여기는 실제 API 응답을
 * 기다리는 구조라 이미지·문구는 고정이고 진행바만 maxSeconds에 맞춰 서서히 채워진다 -
 * 실제 응답이 더 걸려도 어색해 보이지 않게 REPORT_WAIT_FILL_PERCENT까지만 채우고
 * 대기하다가, ready가 true가 되는 순간 100%로 완료 처리한다.
 * DiagnosisIndustryResult.tsx(최초 폴링)와 DiagnosisReport.tsx(같은 폴링 재확인)가 공유. */
function ReportWaitPopup({ title, ready, onDone, maxSeconds = REPORT_WAIT_MAX_SECONDS, hideEtaHint }: ReportWaitPopupProps) {
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
    <div className={styles.loadingOverlay}>
      <div className={styles.loadingBox} role="status" aria-live="polite">
        <img src={reportWaitImage} alt="" className={styles.reportWaitImage} />
        <div className={styles.reportWaitProgressTrack}>
          <div
            className={styles.reportWaitProgressFill}
            style={{
              width: `${pct}%`,
              transitionDuration: pct >= 100 ? "0.3s" : `${maxSeconds}s`,
            }}
          />
        </div>
        <p className={styles.loadingText}>{title}</p>
        <p className={styles.loadingHint}>
          잠시만 기다려주세요{hideEtaHint ? "" : ` (최대 ${maxSeconds}초 소요)`}
        </p>
      </div>
    </div>
  );
}

export default ReportWaitPopup;
