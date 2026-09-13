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

const LOG_SOURCE_LABELS: Record<string, string> = {
  bizinfo: "기업마당 수집(스케줄러)",
  kstartup: "K-스타트업 수집(스케줄러)",
  "bizinfo-manual": "기업마당 수집(수동호출)",
  "kstartup-manual": "K-스타트업 수집(수동호출)",
  "bizinfo-sync": "기업마당 통합 반영",
  "kstartup-sync": "K-스타트업 통합 반영",
};

function formatLogTime(isoString: string): string {
  const d = new Date(isoString);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// [2026-09-11] "마지막/다음 실행", "집계 시작" 표시가 KST(한국시간) 기준이어야
// 하는데(크롤러가 매일 KST 04:00에 도는 스케줄), 보는 사람 브라우저의 로컬
// 타임존과 무관하게 항상 KST로 보이게 한다. Date의 UTC getter를 그대로 쓰되
// +9시간 옮긴 시각을 넣어서 "UTC 기준으로 읽으면 곧 KST 벽시계 값"이 되게 하는
// 트릭 - Intl.DateTimeFormat(timeZone) 없이도 브라우저 로케일에 안 흔들림.
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

function toKstShifted(ms: number): Date {
  return new Date(ms + KST_OFFSET_MS);
}

function formatKstDateTime(isoString: string | null): string {
  if (!isoString) return "-";
  const d = toKstShifted(new Date(isoString).getTime());
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}.${pad(d.getUTCMonth() + 1)}.${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

function formatKstDate(isoString: string | null): string {
  if (!isoString) return "-";
  const d = toKstShifted(new Date(isoString).getTime());
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}.${pad(d.getUTCMonth() + 1)}.${pad(d.getUTCDate())}`;
}

// 기업마당(로컬 스케줄러)/K-스타트업(GitHub Actions) 둘 다 매일 KST 04:00 실행
// (scripts/README.md, .github/workflows/crawl-daily.yml 기준) - 다음 실행 시각을
// "오늘 04:00이 아직 안 지났으면 오늘, 지났으면 내일"로 계산한다.
const CRAWL_HOUR_KST = 4;

function nextCrawlRunLabel(): string {
  const nowKst = toKstShifted(Date.now());
  const todayFourAmMs = Date.UTC(
    nowKst.getUTCFullYear(),
    nowKst.getUTCMonth(),
    nowKst.getUTCDate(),
    CRAWL_HOUR_KST,
  );
  const nextMs = nowKst.getTime() >= todayFourAmMs ? todayFourAmMs + 24 * 60 * 60 * 1000 : todayFourAmMs;
  const next = new Date(nextMs);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${next.getUTCFullYear()}.${pad(next.getUTCMonth() + 1)}.${pad(next.getUTCDate())} 0${CRAWL_HOUR_KST}:00`;
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

const BATCH_LOG_PAGE_SIZE = 10;

// [2026-09-11] /admin/bizinfo-count, /admin/kstartup-count가 누적 건수뿐 아니라
// 오늘 신규 건수(today_count, KST 기준)/마지막·최초 수집 시각까지 같이 내려주도록
// 백엔드가 바뀌어서, 프론트도 숫자 하나(count)가 아니라 이 요약 전체를 들고 있는다.
type SourceSummary = {
  count: number;
  today_count: number;
  last_collected_at: string | null;
  first_collected_at: string | null;
};

function AdminHome() {
  const [bizinfoSummary, setBizinfoSummary] = useState<SourceSummary | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [kstartupSummary, setKstartupSummary] = useState<SourceSummary | null>(null);
  const [kstartupError, setKstartupError] = useState(false);
  const [batchLogs, setBatchLogs] = useState<BatchLog[]>([]);
  const [batchLogTotal, setBatchLogTotal] = useState(0);
  const [batchLogPage, setBatchLogPage] = useState(0);
  const [backlog, setBacklog] = useState<Backlog[]>([]);
  const [crawlSource, setCrawlSource] = useState(CRAWL_SOURCES[0].value);
  // 현재 백그라운드로 수집 중인 소스(없으면 null). 진행 중엔 셀렉트·버튼 잠금.
  const [crawlingSource, setCrawlingSource] = useState<string | null>(null);
  // "배치하기" 버튼으로 미반영분 통합 반영을 실행 중인지(진행 중엔 버튼 잠금).
  const [runningBatch, setRunningBatch] = useState(false);

  const bizinfoCount = bizinfoSummary?.count ?? null;
  const kstartupCount = kstartupSummary?.count ?? null;

  const fetchCount = () => {
    fetch(`${API_BASE_URL}/admin/bizinfo-count`)
      .then((res) => res.json())
      .then((data: SourceSummary) => setBizinfoSummary(data))
      .catch(() => setLoadError(true));
  };

  const fetchKstartupCount = () => {
    fetch(`${API_BASE_URL}/admin/kstartup-count`)
      .then((res) => res.json())
      .then((data: SourceSummary) => setKstartupSummary(data))
      .catch(() => setKstartupError(true));
  };

  const fetchBatchLogs = (page = 0) => {
    fetch(`${API_BASE_URL}/admin/batch-logs?limit=${BATCH_LOG_PAGE_SIZE}&offset=${page * BATCH_LOG_PAGE_SIZE}`)
      .then((res) => res.json())
      .then((data: { success: boolean; data: { logs: BatchLog[]; total: number } }) => {
        setBatchLogs(data.data.logs);
        setBatchLogTotal(data.data.total);
        setBatchLogPage(page);
      })
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
      const logs: BatchLog[] = await fetch(`${API_BASE_URL}/admin/batch-logs?limit=${BATCH_LOG_PAGE_SIZE}`)
        .then((res) => res.json())
        .then((data: { data: { logs: BatchLog[] } }) => data.data.logs)
        .catch(() => []);

      const newest = logs.find((log) => log.source === src);
      if (newest && newest.ran_at !== prevLatestRanAt) {
        setCrawlingSource(null);
        fetchCount();
        fetchKstartupCount();
        fetchBatchLogs(0);
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

  const cumulativeLabel = loadError ? "불러오기 실패" : bizinfoCount === null ? "확인 중..." : `${bizinfoCount.toLocaleString()}건`;
  const kstartupLabel = kstartupError
    ? "불러오기 실패"
    : kstartupCount === null
      ? "확인 중..."
      : `${kstartupCount.toLocaleString()}건`;

  // [2026-09-11] 기업마당만 반영되던 두 상단 큰 숫자("오늘 자동 수집 요약"/"오늘까지
  // 누적 현황")를 K-스타트업까지 합산하도록 수정. 하나라도 아직 안 왔으면 "확인 중",
  // 하나라도 에러면 그 이유를 보여준다(둘 다 정상일 때만 합산 숫자를 보여줌).
  const bothLoaded = bizinfoSummary !== null && kstartupSummary !== null;
  const anyError = loadError || kstartupError;
  const totalTodayCount = (bizinfoSummary?.today_count ?? 0) + (kstartupSummary?.today_count ?? 0);
  const totalCumulativeCount = (bizinfoCount ?? 0) + (kstartupCount ?? 0);
  const todaySummaryLabel = anyError
    ? "일부 소스 불러오기 실패"
    : bothLoaded
      ? `${totalTodayCount.toLocaleString()}건`
      : "확인 중...";
  const cumulativeSummaryLabel = anyError
    ? "일부 소스 불러오기 실패"
    : bothLoaded
      ? `${totalCumulativeCount.toLocaleString()}건`
      : "확인 중...";

  // 마지막 수집 시각 = 두 소스 중 더 최근 것. 집계 시작 = 두 소스 중 더 오래된 것.
  const lastCollectedAt = [bizinfoSummary?.last_collected_at, kstartupSummary?.last_collected_at]
    .filter((v): v is string => !!v)
    .sort()
    .at(-1) ?? null;
  const firstCollectedAt = [bizinfoSummary?.first_collected_at, kstartupSummary?.first_collected_at]
    .filter((v): v is string => !!v)
    .sort()
    .at(0) ?? null;

  // 기관별 실제 건수 비율대로 막대 너비 계산 (제일 큰 값이 트랙을 꽉 채움) - 오늘/누적
  // 각각 자기 값들끼리 비교해야 막대 비율이 맞아서 스케일을 따로 계산한다.
  const maxCumulativeCount = Math.max(bizinfoCount ?? 0, kstartupCount ?? 0) || 1;
  const bizinfoCumulativeWidth = bizinfoCount ? Math.round((bizinfoCount / maxCumulativeCount) * BAR_TRACK_WIDTH) : 0;
  const kstartupCumulativeWidth = kstartupCount ? Math.round((kstartupCount / maxCumulativeCount) * BAR_TRACK_WIDTH) : 0;

  const bizinfoTodayCount = bizinfoSummary?.today_count ?? null;
  const kstartupTodayCount = kstartupSummary?.today_count ?? null;
  const maxTodayCount = Math.max(bizinfoTodayCount ?? 0, kstartupTodayCount ?? 0) || 1;
  const bizinfoTodayWidth = bizinfoTodayCount ? Math.round((bizinfoTodayCount / maxTodayCount) * BAR_TRACK_WIDTH) : 0;
  const kstartupTodayWidth = kstartupTodayCount ? Math.round((kstartupTodayCount / maxTodayCount) * BAR_TRACK_WIDTH) : 0;

  const todayChart = [
    { name: "기업마당", count: bizinfoTodayCount !== null ? `${bizinfoTodayCount.toLocaleString()}건` : cumulativeLabel, width: bizinfoTodayWidth },
    { name: "K-스타트업(창업진흥원)", count: kstartupTodayCount !== null ? `${kstartupTodayCount.toLocaleString()}건` : kstartupLabel, width: kstartupTodayWidth },
    ...OTHER_CHART_BASE,
  ];
  const cumulativeChart = [
    { name: "기업마당", count: cumulativeLabel, width: bizinfoCumulativeWidth },
    { name: "K-스타트업(창업진흥원)", count: kstartupLabel, width: kstartupCumulativeWidth },
    ...OTHER_CHART_BASE,
  ];

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
          <p className={styles.countNum}>{todaySummaryLabel}</p>
          <p className={styles.countSuffixBold}>신규 추가</p>
        </div>
        <p className={styles.crawlerTimeInfo}>
          마지막 실행 {formatKstDateTime(lastCollectedAt)} · 다음 실행 {nextCrawlRunLabel()} (매일 04:00 자동 수집)
        </p>
      </div>

      <div className={styles.summaryCardPlain}>
        <div className={styles.cardHeaderRow}>
          <p className={styles.cardHeaderTitle}>오늘까지 누적 현황</p>
        </div>
        <div className={styles.countBlock}>
          <p className={styles.countNum}>{cumulativeSummaryLabel}</p>
          <p className={styles.countSuffixMedium}>누적 현황</p>
        </div>
        <p className={styles.crawlerTimeInfo}>
          집계 시작 {formatKstDate(firstCollectedAt)} · 오늘 기준 {formatKstDateTime(lastCollectedAt)} 누적
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
        <table className={styles.logTable}>
          <thead>
            <tr>
              <th>출처</th>
              <th>실행 시각</th>
              <th>상태</th>
              <th>건수</th>
            </tr>
          </thead>
          <tbody>
            {batchLogs.length === 0 ? (
              <tr>
                <td className={styles.logTableEmpty} colSpan={4}>
                  실행 로그가 없습니다.
                </td>
              </tr>
            ) : (
              batchLogs.map((log, idx) => (
                <tr key={`${log.ran_at}-${log.source}-${idx}`}>
                  <td>{LOG_SOURCE_LABELS[log.source] ?? log.source}</td>
                  <td>{formatLogTime(log.ran_at)}</td>
                  <td>
                    <span
                      className={`${styles.statusBadge} ${
                        log.status === "success" ? styles.statusBadgeSuccess : styles.statusBadgeError
                      }`}
                    >
                      {log.status === "success" ? "성공" : "실패"}
                    </span>
                  </td>
                  <td>
                    {log.source.endsWith("-sync")
                      ? `반영 ${log.inserted_count.toLocaleString()}건`
                      : `신규 ${log.inserted_count.toLocaleString()}건`}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        <BatchLogPagination page={batchLogPage} total={batchLogTotal} onPageChange={fetchBatchLogs} />
      </div>
    </>
  );
}

// 게시판형 페이지 번호 목록(현재 페이지 기준 최대 5개 노출) + 이전/다음.
function BatchLogPagination({
  page,
  total,
  onPageChange,
}: {
  page: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / BATCH_LOG_PAGE_SIZE));
  if (totalPages <= 1) return null;

  const windowStart = Math.max(0, Math.min(page - 2, totalPages - 5));
  const pageNumbers = Array.from(
    { length: Math.min(5, totalPages - windowStart) },
    (_, i) => windowStart + i,
  );

  return (
    <div className={styles.pagination}>
      <button type="button" disabled={page === 0} onClick={() => onPageChange(page - 1)}>
        이전
      </button>
      {pageNumbers.map((p) => (
        <button
          type="button"
          key={p}
          className={p === page ? styles.paginationActive : undefined}
          onClick={() => onPageChange(p)}
        >
          {p + 1}
        </button>
      ))}
      <button type="button" disabled={page >= totalPages - 1} onClick={() => onPageChange(page + 1)}>
        다음
      </button>
    </div>
  );
}

export default AdminHome;
