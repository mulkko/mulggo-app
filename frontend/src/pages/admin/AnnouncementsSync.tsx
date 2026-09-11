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
  // 기업마당 원문 사이트에서 찾을 수 있는 실제 공고번호. raw_bizinfo_id(우리 DB
  // 내부 번호)와 다르다 - null이면 이 줄이 옛 형식(pblanc_id 추가 전) 로그.
  pblancId: string | null;
  // 원본 첨부파일명(확장자 포함, 여러 개면 "@"로 이어붙음). null이면 옛 형식.
  fileName: string | null;
  extractOk: boolean;
  extractStatus: string;
  // null = 이 줄엔 업종분류 정보가 없음(더 옛 형식으로 찍힌 실행 로그)
  ksicOk: boolean | null;
  ksicStatus: string | null;
};

// backend/preprocessing/sync_bizinfo_announcements.py::map_ksic()가 찍는 건별 요약 줄을
// 파싱한다. 로그가 누적되면서(2026-09-11부터 안 지워짐) 한 파일 안에 세 형식이
// 섞일 수 있어 전부 지원: 최신(pblanc_id+첨부파일 포함) / 중간(업종분류만 있고
// pblanc_id·첨부파일 없음) / 가장 예전(업종분류도 없음). K-Startup은 이 단계
// 자체가 없어서(업종무관 고정) 파싱 결과가 항상 빈 배열 - 그 경우 원본 로그
// 요약만 보여준다.
const ITEM_LINE_RE_FULL =
  /^\[(\d+)\/(\d+)\] raw_bizinfo_id=(\S+) pblanc_id=(\S+) \| 첨부파일=(.*?) \| 본문추출 (성공|실패)\(([^)]*)\) \| 업종분류 (성공|실패)\(([^)]*)\)/;
const ITEM_LINE_RE_WITH_KSIC =
  /^\[(\d+)\/(\d+)\] raw_bizinfo_id=(\S+) \| 본문추출 (성공|실패)\(([^)]*)\) \| 업종분류 (성공|실패)\(([^)]*)\)/;
const ITEM_LINE_RE_LEGACY = /^\[(\d+)\/(\d+)\] raw_bizinfo_id=(\S+) 본문 추출 (성공|실패)\(([^)]*)\)/;

function parseItems(log: string): ItemResult[] {
  const items: ItemResult[] = [];
  for (const line of log.split("\n")) {
    const trimmed = line.trim();
    const full = ITEM_LINE_RE_FULL.exec(trimmed);
    if (full) {
      items.push({
        index: Number(full[1]),
        total: Number(full[2]),
        rawId: full[3],
        pblancId: full[4],
        fileName: full[5] === "-" ? null : full[5],
        extractOk: full[6] === "성공",
        extractStatus: full[7],
        ksicOk: full[8] === "성공",
        ksicStatus: full[9],
      });
      continue;
    }
    const withKsic = ITEM_LINE_RE_WITH_KSIC.exec(trimmed);
    if (withKsic) {
      items.push({
        index: Number(withKsic[1]),
        total: Number(withKsic[2]),
        rawId: withKsic[3],
        pblancId: null,
        fileName: null,
        extractOk: withKsic[4] === "성공",
        extractStatus: withKsic[5],
        ksicOk: withKsic[6] === "성공",
        ksicStatus: withKsic[7],
      });
      continue;
    }
    const legacy = ITEM_LINE_RE_LEGACY.exec(trimmed);
    if (legacy) {
      items.push({
        index: Number(legacy[1]),
        total: Number(legacy[2]),
        rawId: legacy[3],
        pblancId: null,
        fileName: null,
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

// 로그가 배치마다 누적되므로 마지막 실행분(맨 아래)의 값을 찾아야 한다 - 첫
// 매치를 쓰면 예전 배치의 값을 잘못 가져온다.
function lastMatch(log: string, re: RegExp): string | null {
  const matches = [...log.matchAll(re)];
  return matches.length ? matches[matches.length - 1][1] : null;
}

function parseUpsertCount(log: string): number | null {
  const m = lastMatch(log, /UPSERT 완료: (\d+)건/g);
  return m ? Number(m) : null;
}

function parseLastRawCount(log: string): number | null {
  const m = lastMatch(log, /RAW 조회: (\d+)건/g);
  return m ? Number(m) : null;
}

const offsetStorageKey = (source: string) => `mulkko_admin_sync_offset_${source}`;

function loadStoredOffset(source: string): number {
  const raw = window.localStorage.getItem(offsetStorageKey(source));
  const n = raw ? Number(raw) : 0;
  return Number.isFinite(n) && n >= 0 ? n : 0;
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
  const [limit, setLimit] = useState(""); // 빈 값 = 남은 전체 처리
  // 재검증 배치가 다음에 시작할 위치. 사람이 기억해뒀다가 직접 늘리는 대신,
  // 실행이 성공적으로 끝날 때마다 이번에 실제로 처리한 건수만큼 자동으로
  // 전진시키고 소스별로 localStorage에 저장한다(페이지 새로고침해도 유지).
  const [nextOffset, setNextOffset] = useState(() => loadStoredOffset(SOURCES[0].value));
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

          // 이번 실행이 실제로 조회한 건수만큼 다음 시작 위치를 전진시킨다.
          // 0건 조회됐다는 건 이 위치부터는 더 처리할 게 없다는 뜻이라
          // 다음 재검증 사이클을 위해 0으로 되돌린다.
          const rawCount = parseLastRawCount(data.data.log);
          const prevOffset = loadStoredOffset(src);
          const newOffset = rawCount && rawCount > 0 ? prevOffset + rawCount : 0;
          window.localStorage.setItem(offsetStorageKey(src), String(newOffset));
          setNextOffset(newOffset);
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

  // source 바뀌면 즉시 한 번 조회 + 폴링 재시작 + 그 소스의 저장된 시작 위치를 불러온다
  useEffect(() => {
    prevRunningRef.current = null;
    setDoneNotice(null);
    setNextOffset(loadStoredOffset(source));
    fetchStatus(source);
    const id = window.setInterval(() => fetchStatus(source), POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [source, fetchStatus]);

  const handleRun = async () => {
    setStarting(true);
    setDoneNotice(null);
    try {
      const limitParam = limit.trim() ? `&limit=${limit.trim()}` : "";
      const offsetParam = nextOffset > 0 ? `&offset=${nextOffset}` : "";
      // [2026-09-11] 이 화면은 이미 announcements에 반영된 공고까지 포함해서
      // 항상 전부 재검증한다(reprocess_all=true 고정) - "이미 반영돼서 실행이
      // 안 되는" 문제(only_unprocessed=True 기본값) 때문. AdminHome의
      // "배치하기"는 이 파라미터를 안 보내므로 기존 동작(미반영분만) 그대로다.
      // 시작 위치(offset)는 사람이 직접 늘리지 않고, 실행이 끝날 때마다
      // fetchStatus에서 자동으로 계산해 nextOffset/localStorage에 저장해둔다.
      const res = await fetch(
        `${API_BASE_URL}/admin/sync?source=${source}${limitParam}${offsetParam}&reprocess_all=true`,
        { method: "POST" },
      );
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

  // "초기화": 다음 시작 위치를 0으로 되돌리는 것뿐 아니라, 로그 파일도 비운다.
  // 로그 형식이 바뀌거나(예: 2026-09-11 pblanc_id/첨부파일 추가) 그냥 처음부터
  // 다시 보고 싶을 때, 옛 형식 줄이랑 새 형식 줄이 한 파일에 섞여 헷갈리는
  // 걸 막기 위함 - 실제 반영된 데이터(announcements)는 안 건드리고 로그만 지운다.
  const handleReset = async () => {
    if (!window.confirm(`${sourceLabel}의 실행 로그를 비우고 시작 위치를 처음으로 되돌립니다. 계속할까요?`)) {
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/admin/sync-log/clear?source=${source}`, { method: "POST" });
      const data: { success: boolean; error?: { message: string } } = await res.json();
      if (!data.success) {
        alert(`초기화 실패: ${data.error?.message ?? "알 수 없는 오류"}`);
        return;
      }
      window.localStorage.setItem(offsetStorageKey(source), "0");
      setNextOffset(0);
      fetchStatus(source);
    } catch {
      alert("초기화 요청에 실패했습니다.");
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

  // [2026-09-11] DB엔 실패 이력을 남기는 테이블이 없어서, 로그(누적 파일)가
  // 유일한 기록이다 - 나중에 다시 보고 싶으면 지금 화면에 떠 있는 걸 파일로
  // 내려받는 수밖에 없다. 그래서 브라우저에서 바로 txt/csv로 저장하는 버튼만
  // 붙인다(백엔드 API 변경 없이 클라이언트에서 즉석으로 생성).
  // 윈도우 메모장/엑셀은 BOM 없는 UTF-8 텍스트를 시스템 코드페이지(CP949)로
  // 잘못 읽어서 한글이 깨진다 - txt/csv 둘 다 여기서 공통으로 BOM을 붙인다.
  const downloadFile = (filename: string, content: string, mime: string) => {
    const url = URL.createObjectURL(new Blob(["﻿" + content], { type: mime }));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const timestamp = () => new Date().toISOString().replace(/[:.]/g, "-");

  const handleDownloadTxt = () => {
    downloadFile(`sync_${source}_${timestamp()}.txt`, log, "text/plain;charset=utf-8");
  };

  const csvEscape = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);

  const handleDownloadCsv = () => {
    const header = [
      "번호",
      "raw_bizinfo_id",
      "공고번호(pblanc_id)",
      "첨부파일명",
      "본문추출",
      "본문추출상세",
      "업종분류",
      "업종분류상세",
    ];
    const rows = items.map((it) => [
      `${it.index}/${it.total}`,
      it.rawId,
      it.pblancId ?? "",
      it.fileName ?? "",
      it.extractOk ? "성공" : "실패",
      it.extractStatus,
      it.ksicOk === null ? "" : it.ksicOk ? "성공" : "특정불가",
      it.ksicStatus ?? "",
    ]);
    const body = [header, ...rows].map((row) => row.map(csvEscape).join(",")).join("\n");
    downloadFile(`sync_${source}_${timestamp()}.csv`, body, "text/csv;charset=utf-8");
  };

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
          <span className={styles.offsetInfo}>다음 시작 위치: {nextOffset.toLocaleString()}</span>
          <button
            type="button"
            className={styles.downloadBtn}
            onClick={handleReset}
            disabled={running || starting}
          >
            초기화(로그 비우기)
          </button>
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
          <code>announcements</code> 통합 테이블에 반영합니다. (raw 테이블은 안 건드립니다.)
        </p>
        <ul>
          <li>
            [2026-09-11] 지금은 이미 반영된 공고까지 <strong>전부 다시</strong> 처리합니다(재검증용,
            건너뛰지 않음) — 실패 로그를 다시 확인하려는 용도라, 이미 반영됐다고 "실행"이
            그냥 아무 일도 안 하고 끝나던 문제를 임시로 우회한 것입니다. 기업마당은 캐시가
            비어있는 상태라 다시 첨부 다운로드+OCR부터 합니다(무거움).
          </li>
          <li>기업마당: 첨부파일 다운로드 + OCR 포함이라 수 시간 걸릴 수 있습니다.</li>
          <li>창업진흥원: 업종 분류 없이 "업종무관"으로 반영 (팀 결정), 몇 분이면 끝납니다.</li>
          <li>
            <strong>건수</strong>로 한 번에 처리할 양만 정하면 됩니다 — "다음 시작 위치"는 실행이
            끝날 때마다 자동으로 전진하고 브라우저에 저장되니, 그냥 같은 소스로 "실행"을
            여러 번 누르기만 하면 이어서 처리됩니다(직접 계산/기억할 필요 없음). 전부 끝까지
            처리하면 시작 위치가 자동으로 0으로 돌아갑니다. 처음부터 다시 돌리고 싶으면
            "초기화"를 누르세요.
          </li>
          <li>
            실행 로그는 실행마다 지워지지 않고 같은 파일에 계속 쌓입니다. 아래 "실행 결과"의
            누적 총/성공/실패 건수는 지금까지 쌓인 모든 배치를 합산한 값입니다. "초기화(로그
            비우기)"를 누르면 시작 위치가 0으로 돌아가는 것과 함께 지금까지 쌓인 로그 파일도
            비웁니다(반영된 데이터는 안 건드림) — 예전 형식 로그랑 섞여서 헷갈릴 때 쓰세요.
          </li>
          <li>
            실행 중 서버가 재시작되면 중단되고 로그가 끊깁니다. 그 경우 "다음 시작 위치"가
            이번 실행 시작 시점 그대로 남아있으니(끝나야 전진함) "실행"만 다시 누르면 됩니다.
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
                (성공 {successCount} / 업종 미확정 {unclassifiedCount} / 실패 {failCount} / 누적 총{" "}
                {items.length}건 — 로그 파일에 쌓인 모든 배치 합산)
              </span>
            )}
          </span>
          <div className={styles.logHeadActions}>
            <button
              type="button"
              className={styles.downloadBtn}
              onClick={handleDownloadTxt}
              disabled={!log.trim()}
            >
              TXT 다운로드
            </button>
            <button
              type="button"
              className={styles.downloadBtn}
              onClick={handleDownloadCsv}
              disabled={items.length === 0}
            >
              CSV 다운로드
            </button>
            <span className={running ? styles.badgeRunning : styles.badgeIdle}>
              {running ? "진행 중" : "대기"}
            </span>
          </div>
        </div>

        {items.length > 0 ? (
          <ul className={styles.resultList}>
            {[...items].reverse().map((it, i) => {
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
                // 로그가 배치마다 이어붙으면서 it.index가 배치마다 1부터 다시
                // 시작해 중복될 수 있어 배열 위치(i)까지 같이 키로 쓴다.
                <li key={`${i}-${it.rawId}-${it.index}`} className={styles.resultItem}>
                  <span className={styles.resultIndex}>
                    {it.index}/{it.total}
                  </span>
                  <span className={badgeClass}>{badgeLabel}</span>
                  <span className={styles.resultDetail}>
                    raw_bizinfo_id={it.rawId}
                    {it.pblancId && <> · 공고번호={it.pblancId}</>}
                    {it.fileName && <> · 첨부={it.fileName}</>}
                    {" · "}본문추출 {it.extractOk ? "성공" : `실패(${it.extractStatus})`}
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
