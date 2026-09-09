import { useCallback, useEffect, useState } from "react";
import styles from "../../styles/announcementsSync.module.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const SOURCES: { value: string; label: string }[] = [
  { value: "bizinfo", label: "기업마당" },
  { value: "kstartup", label: "창업진흥원" },
];

const POLL_INTERVAL_MS = 4000;

type SyncStatus = { source: string; running: boolean; log: string };

/**
 * [임시] raw(announcements_raw_*) -> announcements 통합 반영 실행/모니터 화면.
 *
 * - "실행" 클릭 -> POST /admin/sync?source=... (백엔드가 별도 파이썬 프로세스로
 *   sync_*_announcements.py 를 돌리고 logs/sync_<source>.log 에 stdout 기록)
 * - GET /admin/sync-status 를 폴링해서 로그 텍스트를 그대로 보여준다.
 * - 세션이 끊기거나 에러가 나도, 페이지를 다시 열면 로그 파일 내용(마지막 상태)이
 *   그대로 텍스트로 보인다. 성공 시 "=== 성공 ... ===", 실패 시 "=== 실패 ... ==="
 *   마커가 로그에 남는다.
 */
function AnnouncementsSync() {
  const [source, setSource] = useState(SOURCES[0].value);
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [limit, setLimit] = useState(""); // 빈 값 = 전체(1500여 건 다) 처리

  const fetchStatus = useCallback(async (src: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/admin/sync-status?source=${src}`);
      const data: { success: boolean; data?: SyncStatus } = await res.json();
      if (data.success && data.data) setStatus(data.data);
    } catch {
      /* 폴링 실패는 조용히 무시 (다음 주기에 재시도) */
    }
  }, []);

  // source 바뀌면 즉시 한 번 조회 + 폴링 재시작
  useEffect(() => {
    fetchStatus(source);
    const id = window.setInterval(() => fetchStatus(source), POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [source, fetchStatus]);

  const handleRun = async () => {
    setStarting(true);
    try {
      const limitParam = limit.trim() ? `&limit=${limit.trim()}` : "";
      const res = await fetch(`${API_BASE_URL}/admin/sync?source=${source}${limitParam}`, { method: "POST" });
      const data: { success: boolean; error?: { message: string } } = await res.json();
      if (!data.success) {
        alert(`실행 실패: ${data.error?.message ?? "알 수 없는 오류"}`);
      }
      fetchStatus(source);
    } catch {
      alert("실행 요청에 실패했습니다.");
    } finally {
      setStarting(false);
    }
  };

  const running = status?.running ?? false;
  const sourceLabel = SOURCES.find((s) => s.value === source)?.label ?? source;

  return (
    <>
      <div className={styles.header}>
        <h1 className={styles.pageTitle}>통합 반영 (임시)</h1>
        <div className={styles.headerActions}>
          <select
            className={styles.select}
            value={source}
            onChange={(e) => {
              setStatus(null);
              setSource(e.target.value);
            }}
            disabled={running || starting}
            aria-label="반영할 공고 출처 선택"
          >
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <input
            type="number"
            min={1}
            className={styles.select}
            placeholder="건수(비우면 전체)"
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            disabled={running || starting}
            aria-label="이번 실행에서 처리할 건수 (비우면 전체)"
          />
          <button
            type="button"
            className="btnPrimary"
            onClick={handleRun}
            disabled={running || starting}
          >
            {running ? "진행 중..." : starting ? "시작 중..." : "실행"}
          </button>
        </div>
      </div>

      <div className={styles.notice}>
        <p>
          <strong>{sourceLabel}</strong>의 raw 데이터를 읽어 지역·업종 매핑 후{" "}
          <code>announcements</code> 통합 테이블에 반영합니다. (raw 테이블은 안 건드리고,
          이미 반영된 공고는 건너뜁니다.)
        </p>
        <ul>
          <li>기업마당: 첨부파일 다운로드 + OCR 포함이라 수 시간 걸릴 수 있습니다.</li>
          <li>창업진흥원: 업종 분류 없이 "업종무관"으로 반영 (팀 결정), 몇 분이면 끝납니다.</li>
          <li>
            건수를 입력하면 이번 실행은 그만큼만 처리합니다(테스트로 10~100건 먼저 확인하거나,
            200건씩 나눠 돌리는 용도). 이미 반영된 공고는 자동으로 건너뛰므로, 같은 값으로
            "실행"을 반복하면 다음 구간이 이어서 처리됩니다.
          </li>
          <li>
            실행 중 서버가 재시작되면 중단되고 로그가 끊깁니다. 그 경우 "실행"을 다시
            누르면 안 끝난 공고만 이어서 처리합니다.
          </li>
        </ul>
      </div>

      <div className={styles.logCard}>
        <div className={styles.logHead}>
          <span className={styles.logTitle}>실행 로그 — {sourceLabel}</span>
          <span className={running ? styles.badgeRunning : styles.badgeIdle}>
            {running ? "진행 중" : "대기"}
          </span>
        </div>
        <pre className={styles.logBody}>
          {status?.log?.trim() ? status.log : "아직 실행 기록이 없습니다."}
        </pre>
      </div>
    </>
  );
}

export default AnnouncementsSync;
