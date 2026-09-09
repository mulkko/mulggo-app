import { useEffect, useState } from "react";
import styles from "../../styles/adminHome.module.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

type ChartRow = { name: string; count: string; width: number };

// TODO: 중소벤처24는 API 연동 전까지 주석 처리.
// 연동되면 실제 건수로 채우고 주석 풀 것.
const OTHER_CHART_BASE: ChartRow[] = [
  // { name: "중소벤처24", count: "7건", width: 65 },
];

const BAR_TRACK_WIDTH = 130;

type BatchLog = {
  source: string;
  fetched_count: number;
  inserted_count: number;
  status: "success" | "error";
  ran_at: string;
};

type Backlog = { source: string; raw: number; done: number; pending: number };

const SOURCE_LABELS: Record<string, string> = {
  bizinfo: "기업마당",
  kstartup: "K-스타트업",
};

function formatLogTime(isoString: string): string {
  const d = new Date(isoString);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// 수동호출 대상 소스. 새 소스가 붙으면 여기 한 줄만 추가하면 된다
// (백엔드 CRAWLERS dict의 키와 일치해야 함).
const CRAWL_SOURCES: { value: string; label: string }[] = [
  { value: "bizinfo", label: "기업마당" },
  { value: "kstartup", label: "K-스타트업" },
];

// K-Startup은 오픈API 전체를 훑어 수 분~십수 분 걸린다. 그동안 완료 여부를
// 배치 로그로 폴링한다.
const CRAWL_POLL_INTERVAL_MS = 5000;
const CRAWL_POLL_TIMEOUT_MS = 20 * 60 * 1000;

function AdminHome() {
  const [bizinfoCount, setBizinfoCount] = useState<number | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [kstartupCount, setKstartupCount] = useState<number | null>(null);
  const [kstartupError, setKstartupError] = useState(false);
  const [batchLogs, setBatchLogs] = useState<BatchLog[]>([]);
  const [backlog, setBacklog] = useState<Backlog[]>([]);
  const [crawlSource, setCrawlSource] = useState(CRAWL_SOURCES[0].value);
  // 현재 백그라운드로 수집 중인 소스(없으면 null). 진행 중엔 셀렉트·버튼 잠금.
  const [crawlingSource, setCrawlingSource] = useState<string | null>(null);
  // "배치하기" 버튼으로 미반영분 통합 반영을 실행 중인지(진행 중엔 버튼 잠금).
  const [runningBatch, setRunningBatch] = useState(false);

  const fetchCount = () => {
    fetch(`${API_BASE_URL}/admin/bizinfo-count`)
      .then((res) => res.json())
      .then((data: { count: number }) => setBizinfoCount(data.count))
      .catch(() => setLoadError(true));
  };

  const fetchKstartupCount = () => {
    fetch(`${API_BASE_URL}/admin/kstartup-count`)
      .then((res) => res.json())
      .then((data: { count: number }) => setKstartupCount(data.count))
      .catch(() => setKstartupError(true));
  };

  const fetchBatchLogs = () => {
    fetch(`${API_BASE_URL}/admin/batch-logs`)
      .then((res) => res.json())
      .then((data: { success: boolean; data: { logs: BatchLog[] } }) => setBatchLogs(data.data.logs))
      .catch(() => {});
  };

  // [2026-09-09] 수집(raw)은 됐는데 통합 반영("실행" 버튼)이 안 됐거나 전처리
  // 중 조용히 실패해서 announcements까지 못 들어간 건수 - 수집 현황만 봐서는
  // 안 보이던 부분이라 별도로 추가함.
  const fetchBacklog = () => {
    fetch(`${API_BASE_URL}/admin/backlog`)
      .then((res) => res.json())
      .then((data: { success: boolean; data: Backlog[] }) => setBacklog(data.data))
      .catch(() => {});
  };

  useEffect(() => {
    fetchCount();
    fetchKstartupCount();
    fetchBatchLogs();
    fetchBacklog();
  }, []);

  // 수집이 끝날 때까지(= 해당 소스의 배치 로그가 새로 쌓일 때까지) 폴링.
  // ran_at 문자열이 직전 최신값과 달라지면 완료로 본다(타임존/시계오차 영향 없음).
  const pollCrawlDone = async (src: string, prevLatestRanAt: string | null) => {
    const deadline = Date.now() + CRAWL_POLL_TIMEOUT_MS;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, CRAWL_POLL_INTERVAL_MS));
      const logs: BatchLog[] = await fetch(`${API_BASE_URL}/admin/batch-logs`)
        .then((res) => res.json())
        .then((data: { data: { logs: BatchLog[] } }) => data.data.logs)
        .catch(() => []);
      if (logs.length) setBatchLogs(logs);

      const newest = logs.find((log) => log.source === src);
      if (newest && newest.ran_at !== prevLatestRanAt) {
        setCrawlingSource(null);
        fetchCount();
        fetchKstartupCount();
        const label = newest.status === "success" ? "완료" : "실패";
        alert(`${src} 수집 ${label}: 신규 ${newest.inserted_count}건`);
        return;
      }
    }
    // 타임아웃: 서버에선 계속 돌 수 있으나 UI 잠금만 해제한다.
    setCrawlingSource(null);
  };

  const handleManualCrawl = async () => {
    const src = crawlSource;
    const prevLatestRanAt = batchLogs.find((log) => log.source === src)?.ran_at ?? null;
    setCrawlingSource(src);
    try {
      const res = await fetch(`${API_BASE_URL}/admin/crawl?source=${src}`, { method: "POST" });
      const data: { success: boolean; error?: { message: string } } = await res.json();
      if (!data.success) {
        alert(`수집 시작 실패: ${data.error?.message ?? "알 수 없는 오류"}`);
        setCrawlingSource(null);
        return;
      }
      // 시작 알림은 전체 화면 스피너 오버레이가 대신한다.
      fetchBatchLogs();
      pollCrawlDone(src, prevLatestRanAt);
    } catch {
      alert("수집 시작 요청에 실패했습니다.");
      setCrawlingSource(null);
    }
  };

  // source 하나의 /admin/sync가 끝날 때까지 폴링(진행 중이 아니게 될 때까지).
  const pollSyncDone = async (source: string) => {
    const deadline = Date.now() + CRAWL_POLL_TIMEOUT_MS;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, CRAWL_POLL_INTERVAL_MS));
      const running: boolean = await fetch(`${API_BASE_URL}/admin/sync-status?source=${source}`)
        .then((res) => res.json())
        .then((data: { data?: { running: boolean } }) => data.data?.running ?? false)
        .catch(() => false);
      if (!running) return;
    }
  };

  // "배치하기": 미반영(raw는 있는데 announcements엔 없는) 건이 있는 소스만
  // 골라서 통합 반영("실행")을 그대로 실행한다. AnnouncementsSync.tsx의
  // "실행"과 동일한 API(only_unprocessed=True 기본값)라 이미 반영된 건
  // 자동으로 건너뛰고 미반영분만 처리한다.
  const handleRunBatch = async () => {
    const pendingSources = backlog.filter((b) => b.pending > 0).map((b) => b.source);
    if (pendingSources.length === 0) {
      alert("미반영 건이 없습니다.");
      return;
    }

    setRunningBatch(true);
    try {
      await Promise.all(
        pendingSources.map((source) =>
          fetch(`${API_BASE_URL}/admin/sync?source=${source}`, { method: "POST" }),
        ),
      );
      await Promise.all(pendingSources.map((source) => pollSyncDone(source)));
    } finally {
      setRunningBatch(false);
      fetchBacklog();
      fetchBatchLogs();
    }
  };

  // raw 테이블 전체를 CSV로 내려받는다. 서버가 attachment 헤더를 주므로
  // 앵커 클릭만으로 다운로드되고 현재 페이지는 그대로 유지된다.
  const downloadCsv = (source: string) => {
    const a = document.createElement("a");
    a.href = `${API_BASE_URL}/admin/export?source=${source}`;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const countLabel = loadError ? "불러오기 실패" : bizinfoCount === null ? "확인 중..." : `${bizinfoCount.toLocaleString()}건`;
  const kstartupLabel = kstartupError
    ? "불러오기 실패"
    : kstartupCount === null
      ? "확인 중..."
      : `${kstartupCount.toLocaleString()}건`;

  // 기관별 실제 건수 비율대로 막대 너비 계산 (제일 큰 값이 트랙을 꽉 채움)
  const maxCount = Math.max(bizinfoCount ?? 0, kstartupCount ?? 0) || 1;
  const bizinfoWidth = bizinfoCount ? Math.round((bizinfoCount / maxCount) * BAR_TRACK_WIDTH) : 0;
  const kstartupWidth = kstartupCount ? Math.round((kstartupCount / maxCount) * BAR_TRACK_WIDTH) : 0;

  const bizinfoRow = { name: "기업마당", count: countLabel, width: bizinfoWidth };
  const kstartupRow = { name: "K-스타트업(창업진흥원)", count: kstartupLabel, width: kstartupWidth };
  const todayChart = [bizinfoRow, kstartupRow, ...OTHER_CHART_BASE];
  const cumulativeChart = [bizinfoRow, kstartupRow, ...OTHER_CHART_BASE];

  return (
    <>
      {crawlingSource !== null && (
        <div className={styles.crawlOverlay}>
          <div className={styles.crawlOverlayInner}>
            <div className={styles.crawlSpinner} />
            <p className={styles.crawlOverlayText}>
              {CRAWL_SOURCES.find((s) => s.value === crawlingSource)?.label} 수집 중...
            </p>
          </div>
        </div>
      )}

      <div className={styles.header}>
        <h1 className={styles.pageTitle}>공고 수집 현황</h1>
        <div className={styles.headerActions}>
          {/* TODO: 스타일가이드에 셀렉트박스 정식 추가되면 .sourceSelect 교체(공용 클래스/컴포넌트로) */}
          <select
            className={styles.sourceSelect}
            value={crawlSource}
            onChange={(e) => setCrawlSource(e.target.value)}
            disabled={crawlingSource !== null}
            aria-label="수집할 공고 출처 선택"
          >
            {CRAWL_SOURCES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            className={`btnSecondary ${styles.crawlBtn}`}
            onClick={handleManualCrawl}
            disabled={crawlingSource !== null}
          >
            {crawlingSource !== null ? "수집 중..." : "수동호출"}
          </button>
          {/* 수동호출(.btnSecondary)과 크기·padding 동일, 배경색만 하늘색(--color-primary-blue) */}
          <button
            type="button"
            className={`btnSecondary ${styles.csvBtn}`}
            onClick={() => downloadCsv("bizinfo")}
          >
            기업마당 CSV
          </button>
          <button
            type="button"
            className={`btnSecondary ${styles.csvBtn}`}
            onClick={() => downloadCsv("kstartup")}
          >
            창업진흥원 CSV
          </button>
        </div>
      </div>

      <div className={styles.summaryCard}>
        <div className={styles.cardHeaderRow}>
          <p className={styles.cardHeaderTitle}>오늘 자동 수집 요약</p>
          <div className={styles.statusIndicator}>
            <span className={styles.statusDot} />
            <p className={styles.statusLabel}>정상</p>
          </div>
        </div>
        <div className={styles.countBlock}>
          <p className={styles.countNum}>{countLabel}</p>
          <p className={styles.countSuffixBold}>신규 추가</p>
        </div>
        <p className={styles.crawlerTimeInfo}>
          마지막 실행 2026.08.26 06:00 · 다음 실행 2026.08.27 06:00 (매일 06:00 자동 수집)
        </p>
      </div>

      <div className={styles.summaryCardPlain}>
        <div className={styles.cardHeaderRow}>
          <p className={styles.cardHeaderTitle}>오늘까지 누적 현황</p>
        </div>
        <div className={styles.countBlock}>
          <p className={styles.countNum}>{countLabel}</p>
          <p className={styles.countSuffixMedium}>누적 현황</p>
        </div>
        <p className={styles.crawlerTimeInfo}>
          집계 시작 2026.09.05 · 오늘 기준 2026.09.05 06:00 누적
        </p>
      </div>

      <div className={styles.splitGrid}>
        <div className={styles.gridCard}>
          <p className={styles.gridCardTitle}>기관별 오늘 수집 건수</p>
          <div className={styles.chartRows}>
            {todayChart.map((row) => (
              <div className={styles.chartRow} key={row.name}>
                <p className={styles.instName}>{row.name}</p>
                <div className={styles.barTrack}>
                  <div className={styles.barFill} style={{ width: `${row.width}px` }} />
                </div>
                <p className={styles.instCount}>{row.count}</p>
              </div>
            ))}
          </div>
        </div>

        <div className={styles.gridCard}>
          <p className={styles.gridCardTitle}>기관별 누적 수집 건수</p>
          <div className={styles.chartRows}>
            {cumulativeChart.map((row) => (
              <div className={styles.chartRow} key={row.name}>
                <p className={styles.instName}>{row.name}</p>
                <div className={styles.barTrack}>
                  <div className={styles.barFill} style={{ width: `${row.width}px` }} />
                </div>
                <p className={styles.instCount}>{row.count}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className={styles.gridCard}>
        <div className={styles.cardHeaderRow}>
          <p className={styles.gridCardTitle}>통합 반영 미반영 현황</p>
          <button
            type="button"
            className="btnSecondary"
            onClick={handleRunBatch}
            disabled={runningBatch}
          >
            {runningBatch ? "반영 중..." : "배치하기"}
          </button>
        </div>
        <div className={styles.logsList}>
          {backlog.map((b) => (
            <div className={styles.logItem} key={b.source}>
              <p className={styles.logTime}>
                {SOURCE_LABELS[b.source] ?? b.source} — raw {b.raw.toLocaleString()}건 / 반영{" "}
                {b.done.toLocaleString()}건
              </p>
              <span
                className={`${styles.statusBadge} ${
                  b.pending > 0 ? styles.statusBadgeError : styles.statusBadgeSuccess
                }`}
              >
                미반영 {b.pending.toLocaleString()}건
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className={styles.gridCard}>
        <p className={styles.gridCardTitle}>최근 배치 실행 로그</p>
        <div className={styles.logsList}>
          {batchLogs.map((log) => (
            <div className={styles.logItem} key={log.ran_at}>
              <p className={styles.logTime}>{formatLogTime(log.ran_at)}</p>
              <span
                className={`${styles.statusBadge} ${
                  log.status === "success" ? styles.statusBadgeSuccess : styles.statusBadgeError
                }`}
              >
                {log.status === "success" ? "성공" : "실패"} · 신규 {log.inserted_count}건
              </span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

export default AdminHome;
