import { useEffect, useState } from "react";
import styles from "../../styles/adminHome.module.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

type ChartRow = { name: string; count: string; width: number };

// TODO: K-스타트업(창업진흥원), 중소벤처24는 API 연동 전까지 주석 처리.
// 연동되면 각 기관의 실제 건수로 채우고 주석 풀 것.
const TODAY_CHART_BASE: ChartRow[] = [
  // { name: "K-스타트업(창업진흥원)", count: "9건", width: 90 },
  // { name: "중소벤처24", count: "7건", width: 65 },
];

const CUMULATIVE_CHART_BASE: ChartRow[] = [
  // { name: "K-스타트업(창업진흥원)", count: "9건", width: 90 },
  // { name: "중소벤처24", count: "6건", width: 55 },
];

type BatchLog = {
  source: string;
  fetched_count: number;
  inserted_count: number;
  status: "success" | "error";
  ran_at: string;
};

function formatLogTime(isoString: string): string {
  const d = new Date(isoString);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function AdminHome() {
  const [bizinfoCount, setBizinfoCount] = useState<number | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [crawling, setCrawling] = useState(false);
  const [batchLogs, setBatchLogs] = useState<BatchLog[]>([]);

  const fetchCount = () => {
    fetch(`${API_BASE_URL}/admin/bizinfo-count`)
      .then((res) => res.json())
      .then((data: { count: number }) => setBizinfoCount(data.count))
      .catch(() => setLoadError(true));
  };

  const fetchBatchLogs = () => {
    fetch(`${API_BASE_URL}/admin/batch-logs`)
      .then((res) => res.json())
      .then((data: { success: boolean; data: { logs: BatchLog[] } }) => setBatchLogs(data.data.logs))
      .catch(() => {});
  };

  useEffect(() => {
    fetchCount();
    fetchBatchLogs();
  }, []);

  const handleManualCrawl = async () => {
    setCrawling(true);
    try {
      const res = await fetch(`${API_BASE_URL}/admin/bizinfo-crawl`, { method: "POST" });
      const data: {
        success: boolean;
        data?: { fetched: number; inserted: number };
        error?: { message: string };
      } = await res.json();
      if (!data.success) {
        alert(`공고 API 호출에 실패했습니다: ${data.error?.message ?? "알 수 없는 오류"}`);
      } else {
        alert(`수집 완료: 전체 ${data.data!.fetched}건 확인, 신규 ${data.data!.inserted}건 추가`);
      }
      fetchCount();
      fetchBatchLogs();
    } catch {
      alert("공고 API 호출에 실패했습니다.");
    } finally {
      setCrawling(false);
    }
  };

  const countLabel = loadError ? "불러오기 실패" : bizinfoCount === null ? "확인 중..." : `${bizinfoCount.toLocaleString()}건`;

  // 기업마당만 실제 값, 바 너비는 비교 대상이 없어서 트랙 꽉 채움(150px)
  const bizinfoRow = { name: "기업마당", count: countLabel, width: 130 };
  const todayChart = [bizinfoRow, ...TODAY_CHART_BASE];
  const cumulativeChart = [bizinfoRow, ...CUMULATIVE_CHART_BASE];

  return (
    <>
      <div className={styles.header}>
        <h1 className={styles.pageTitle}>공고 수집 현황</h1>
        <button type="button" className="btnSecondary" onClick={handleManualCrawl} disabled={crawling}>
          {crawling ? "호출 중..." : "수동호출"}
        </button>
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
    </>
  );
}

export default AdminHome;
