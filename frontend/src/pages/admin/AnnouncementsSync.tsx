import { useCallback, useEffect, useRef, useState } from "react";
import styles from "../../styles/announcementsSync.module.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const SOURCES: { value: string; label: string }[] = [
  { value: "bizinfo", label: "기업마당" },
  { value: "kstartup", label: "창업진흥원" },
];

const POLL_INTERVAL_MS = 4000;

type SyncStatus = { source: string; running: boolean; log: string };

type ItemResult = {
  index: number;
  total: number;
  rawId: string;
  extractOk: boolean;
  extractStatus: string;
  // null = 이 줄엔 업종분류 정보가 없음(예전 형식으로 찍힌 실행 로그)
  ksicOk: boolean | null;
  ksicStatus: string | null;
};

// backend/preprocessing/sync_bizinfo_announcements.py::map_ksic()가 찍는 건별 요약 줄을
// 파싱한다. 두 형식을 다 지원: 새 형식("| 업종분류 ..." 포함)과, 그 전에 이미 시작된
// 실행이 남긴 예전 형식(업종분류 없이 본문추출만). K-Startup은 이 단계 자체가 없어서
// (업종무관 고정) 파싱 결과가 항상 빈 배열 - 그 경우 원본 로그 요약만 보여준다.
const ITEM_LINE_RE_WITH_KSIC =
  /^\[(\d+)\/(\d+)\] raw_bizinfo_id=(\S+) \| 본문추출 (성공|실패)\(([^)]*)\) \| 업종분류 (성공|실패)\(([^)]*)\)/;
const ITEM_LINE_RE_LEGACY = /^\[(\d+)\/(\d+)\] raw_bizinfo_id=(\S+) 본문 추출 (성공|실패)\(([^)]*)\)/;

function parseItems(log: string): ItemResult[] {
  const items: ItemResult[] = [];
  for (const line of log.split("\n")) {
    const trimmed = line.trim();
    const full = ITEM_LINE_RE_WITH_KSIC.exec(trimmed);
    if (full) {
      items.push({
        index: Number(full[1]),
        total: Number(full[2]),
        rawId: full[3],
        extractOk: full[4] === "성공",
        extractStatus: full[5],
        ksicOk: full[6] === "성공",
        ksicStatus: full[7],
      });
      continue;
    }
    const legacy = ITEM_LINE_RE_LEGACY.exec(trimmed);
    if (legacy) {
      items.push({
        index: Number(legacy[1]),
        total: Number(legacy[2]),
        rawId: legacy[3],
        extractOk: legacy[4] === "성공",
        extractStatus: legacy[5],
        ksicOk: null,
        ksicStatus: null,
      });
    }
  }
  return items;
}

function parseFinishMarker(log: string): { kind: "success" | "fail"; at: string } | null {
  const lines = log.split("\n");
  for (let i = lines.length - 1; i >= 0; i--) {
    const m = /^=== (성공|실패): (\S+)/.exec(lines[i].trim());
    if (m) return { kind: m[1] === "성공" ? "success" : "fail", at: m[2] };
  }
  return null;
}

function parseUpsertCount(log: string): number | null {
  const m = /UPSERT 완료: (\d+)건/.exec(log);
  return m ? Number(m[1]) : null;
}

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
  const [showRawLog, setShowRawLog] = useState(false);
  const [doneNotice, setDoneNotice] = useState<string | null>(null);

  // 폴링 중 running: true -> false로 바뀌는 "완료 순간"만 잡아서 알림을 띄우기
  // 위한 이전 값 기억. source를 바꾸면 그 소스 기준으로 다시 추적한다.
  const prevRunningRef = useRef<boolean | null>(null);

  const fetchStatus = useCallback(async (src: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/admin/sync-status?source=${src}`);
      const data: { success: boolean; data?: SyncStatus } = await res.json();
      if (!data.success || !data.data) return;

      if (prevRunningRef.current === true && data.data.running === false) {
        const finish = parseFinishMarker(data.data.log);
        const upsertCount = parseUpsertCount(data.data.log);
        const label = SOURCES.find((s) => s.value === src)?.label ?? src;
        if (finish?.kind === "success") {
          setDoneNotice(`${label} 저장 완료 — ${upsertCount ?? 0}건 반영됨`);
        } else if (finish?.kind === "fail") {
          setDoneNotice(`${label} 실행이 실패로 끝났습니다. 로그를 확인해주세요.`);
        } else {
          setDoneNotice(`${label} 실행이 중단됐습니다 (중간에 멈춤 — 아직 저장 안 됐을 수 있음).`);
        }
      }
      prevRunningRef.current = data.data.running;
      setStatus(data.data);
    } catch {
      /* 폴링 실패는 조용히 무시 (다음 주기에 재시도) */
    }
  }, []);

  // source 바뀌면 즉시 한 번 조회 + 폴링 재시작
  useEffect(() => {
    prevRunningRef.current = null;
    setDoneNotice(null);
    fetchStatus(source);
    const id = window.setInterval(() => fetchStatus(source), POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [source, fetchStatus]);

  const handleRun = async () => {
    setStarting(true);
    setDoneNotice(null);
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
  const log = status?.log ?? "";
  const items = parseItems(log);
  // 업종분류 "특정불가"는 실제 실패가 아니라 정상 케이스(공고 성격상 업종을
  // 하나로 못 정하는 경우) - 본문추출 실패와 구분해서 보여준다.
  const getItemStatus = (it: ItemResult): "success" | "unclassified" | "fail" => {
    if (!it.extractOk) return "fail";
    if (it.ksicOk === false) return "unclassified";
    return "success";
  };
  const successCount = items.filter((it) => getItemStatus(it) === "success").length;
  const unclassifiedCount = items.filter((it) => getItemStatus(it) === "unclassified").length;
  const failCount = items.filter((it) => getItemStatus(it) === "fail").length;

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

      {doneNotice && (
        <div className={styles.doneNotice}>
          <span>{doneNotice}</span>
          <button type="button" className={styles.doneNoticeClose} onClick={() => setDoneNotice(null)}>
            닫기
          </button>
        </div>
      )}

      <div className={styles.logCard}>
        <div className={styles.logHead}>
          <span className={styles.logTitle}>
            실행 결과 — {sourceLabel}
            {items.length > 0 && (
              <span className={styles.countSummary}>
                {" "}
                (성공 {successCount} / 업종 미확정 {unclassifiedCount} / 실패 {failCount} / 총{" "}
                {items[items.length - 1]?.total ?? items.length})
              </span>
            )}
          </span>
          <span className={running ? styles.badgeRunning : styles.badgeIdle}>
            {running ? "진행 중" : "대기"}
          </span>
        </div>

        {items.length > 0 ? (
          <ul className={styles.resultList}>
            {[...items].reverse().map((it) => {
              const itemStatus = getItemStatus(it);
              const badgeClass =
                itemStatus === "success"
                  ? styles.badgeSuccess
                  : itemStatus === "unclassified"
                    ? styles.badgeUnclassified
                    : styles.badgeFail;
              const badgeLabel =
                itemStatus === "success" ? "성공" : itemStatus === "unclassified" ? "업종 미확정" : "실패";
              return (
                <li key={it.index} className={styles.resultItem}>
                  <span className={styles.resultIndex}>
                    {it.index}/{it.total}
                  </span>
                  <span className={badgeClass}>{badgeLabel}</span>
                  <span className={styles.resultDetail}>
                    raw_bizinfo_id={it.rawId} · 본문추출 {it.extractOk ? "성공" : `실패(${it.extractStatus})`}
                    {it.ksicOk !== null && (
                      <> · 업종분류 {it.ksicOk ? "성공" : `특정불가(정상)`}</>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className={styles.noResultYet}>
            {log.trim() ? "건별 결과가 아직 없습니다 (K-Startup은 이 단계가 없습니다)." : "아직 실행 기록이 없습니다."}
          </p>
        )}

        <button type="button" className={styles.rawLogToggle} onClick={() => setShowRawLog((v) => !v)}>
          {showRawLog ? "원본 로그 숨기기" : "원본 로그 보기 (문제 확인용)"}
        </button>
        {showRawLog && <pre className={styles.logBody}>{log.trim() ? log : "아직 실행 기록이 없습니다."}</pre>}
      </div>
    </>
  );
}

export default AnnouncementsSync;
