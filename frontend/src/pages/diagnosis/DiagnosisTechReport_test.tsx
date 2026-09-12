import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosisTechReport.module.css";
import diagnosisStyles from "../../styles/diagnosis.module.css";

/**
 * [개인 테스트용, 원본 DiagnosisTechReport.tsx의 격리 사본] 실제 백엔드 호출
 * (/analysis/tech-startup, /analysis/patent-startup) 없이 목업 데이터로 바로 렌더링만
 * 확인하는 페이지. 정식 흐름과 완전히 분리돼 있어서 백엔드 상태와 무관하게 항상 같은
 * 화면이 보임(2026-09-12, 사용자 확인 - DiagnosisAnswerSummary_test.tsx와 동일 패턴).
 */
const KSIC_LABEL = "20112 · 바이오매스계 기초 화학물질 제조업";

const MOCK_TYPE_DISTRIBUTION = [
  { 인증유형: "벤처기업", 건수: 128, "비율(%)": 52 },
  { 인증유형: "이노비즈", 건수: 76, "비율(%)": 31 },
  { 인증유형: "메인비즈", 건수: 42, "비율(%)": 17 },
];

const MOCK_DENSITY_GRID = {
  grid_cols: 6,
  grid_rows: 3,
  total_sigungu_count: 25,
  shown_sigungu_count: 12,
  total_company_count: 340,
  shown_company_count: 210,
  cells: [
    { x: 0, y: 0, count: 12, sigungu: "강남구" },
    { x: 1, y: 0, count: 28, sigungu: "서초구" },
    { x: 2, y: 0, count: 5, sigungu: "송파구" },
    { x: 0, y: 1, count: 40, sigungu: "마포구" },
    { x: 1, y: 1, count: 18, sigungu: "영등포구" },
    { x: 3, y: 1, count: 9, sigungu: "성동구" },
  ],
};

const MOCK_PATENT_ACTUAL: Record<string, number> = { "2021": 12, "2022": 18, "2023": 25, "2024": 21 };
const MOCK_PATENT_FORECAST: Record<string, number> = { "2025": 30 };

const BAR_COLORS = [
  "var(--color-light-teal)",
  "var(--color-tab-active-icon)",
  "var(--color-stone-gray)",
  "var(--color-dot-inactive)",
];

function getBarColor(index: number): string {
  return BAR_COLORS[index] ?? BAR_COLORS[BAR_COLORS.length - 1];
}

function getDensityColor(count: number, maxCount: number): string {
  const ratio = maxCount > 0 ? count / maxCount : 0;
  return `rgba(21, 50, 140, ${(0.1 + ratio * 0.7).toFixed(2)})`;
}

function DiagnosisTechReport_test() {
  const navigate = useNavigate();
  const handleBack = () => navigate("/home");
  const handleNext = () => {};

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M16 5l-8 7 8 7" />
            </svg>
          </button>
          <span className={styles.headerTitle}>기술창업분석 리포트 [TEST]</span>
        </div>
      </header>

      <div className={styles.scrollArea}>
        <div className={styles.codeLabel}>{KSIC_LABEL}</div>
        <h1 className={styles.regionTitle}>업종 및 특허분석 지표</h1>

        <div className={styles.statGrid}>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>유사 벤처인증기업 수</span>
            <span className={styles.statValue}>246개</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>벤처투자형 인증 (1년)</span>
            <span className={styles.statValue}>34건</span>
          </div>
          <div className={`${styles.statCard} ${styles.statCardHighlight}`}>
            <span className={styles.statLabel}>매칭 지원사업 수</span>
            <span className={styles.statValueEmpty}>준비 중이에요</span>
          </div>
        </div>

        <section className={styles.sectionCard}>
          <h2 className={styles.sectionTitle}>유사 기업 인증유형 구성</h2>
          {MOCK_TYPE_DISTRIBUTION.map((item, index) => (
            <div key={item.인증유형} className={styles.barRow}>
              <span className={styles.barLabel}>{item.인증유형}</span>
              <span className={styles.barTrack}>
                <span
                  className={styles.barFill}
                  style={{ width: `${item["비율(%)"]}%`, background: getBarColor(index) }}
                />
              </span>
              <span className={styles.barCount}>{item["비율(%)"]}%</span>
            </div>
          ))}
        </section>

        <section className={styles.sectionCard}>
          <h2 className={styles.sectionTitle}>관련분야 특허출원 추이 (KIPRIS)</h2>
          <PatentChart actual={MOCK_PATENT_ACTUAL} forecast={MOCK_PATENT_FORECAST} keyword="바이오매스 원료" />
        </section>

        <section className={styles.sectionCard}>
          <h2 className={styles.sectionTitle}>동종산업 밀집도</h2>
          <DensityGridView grid={MOCK_DENSITY_GRID} />
        </section>

        <p className={styles.sourceText}>출처: 중기부 벤처기업명단·특허청 KIPRIS 기준 · 개별 성공 확률 아님</p>
      </div>

      <div className={diagnosisStyles.bottom}>
        <button type="button" className={diagnosisStyles.prevButton} onClick={handleBack}>
          홈으로
        </button>
        <button type="button" className={diagnosisStyles.nextButton} onClick={handleNext}>
          다음 →
        </button>
      </div>
    </div>
  );
}

function PatentChart({
  actual,
  forecast,
  keyword,
}: {
  actual: Record<string, number>;
  forecast: Record<string, number>;
  keyword: string;
}) {
  const years = Object.keys(actual).map(Number).sort((a, b) => a - b);
  const forecastEntries = Object.entries(forecast);
  const forecastYear = forecastEntries.length > 0 ? Number(forecastEntries[0][0]) : null;
  const forecastValue = forecastEntries.length > 0 ? forecastEntries[0][1] : null;
  const actualPoints = years.map((year) => ({ year, value: actual[String(year)] }));

  const allValues = actualPoints.map((p) => p.value).concat(forecastValue !== null ? [forecastValue] : []);
  const maxValue = Math.max(...allValues, 1);
  const minValue = Math.min(...allValues, 0);

  const step = 36;
  const paddingX = 22;
  const chartHeight = 110;
  const topPad = 22;
  const bottomPad = 6;

  const xForYear = (year: number) => paddingX + years.indexOf(year) * step;
  const yForValue = (value: number) => {
    if (maxValue === minValue) return chartHeight - bottomPad - (chartHeight - topPad - bottomPad) / 2;
    const ratio = (value - minValue) / (maxValue - minValue);
    return chartHeight - bottomPad - ratio * (chartHeight - topPad - bottomPad);
  };

  const lastActual = actualPoints[actualPoints.length - 1];
  const polyline = actualPoints.map((p) => `${xForYear(p.year)},${yForValue(p.value)}`).join(" ");
  const chartWidth = paddingX * 2 + Math.max(years.length - 1, 0) * step;

  return (
    <div className={styles.patentChartWrap}>
      <div className={styles.patentChartScroll}>
        <svg
          viewBox={`0 0 ${chartWidth} ${chartHeight}`}
          preserveAspectRatio="none"
          className={styles.patentSvg}
          style={{ width: `${Math.max(chartWidth, 280)}px` }}
        >
          <polyline points={polyline} fill="none" stroke="var(--color-light-teal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          {forecastYear !== null && forecastValue !== null && (
            <polyline
              points={`${xForYear(lastActual.year)},${yForValue(lastActual.value)} ${paddingX + years.length * step},${yForValue(forecastValue)}`}
              fill="none"
              stroke="var(--color-deep-navy)"
              strokeWidth="2"
              strokeDasharray="2 3"
              strokeLinecap="round"
            />
          )}
          {actualPoints.map((p) => (
            <circle key={p.year} cx={xForYear(p.year)} cy={yForValue(p.value)} r="4" fill="var(--color-light-teal)" />
          ))}
          {forecastYear !== null && forecastValue !== null && (
            <circle cx={paddingX + years.length * step} cy={yForValue(forecastValue)} r="4" fill="var(--color-white)" stroke="var(--color-deep-navy)" strokeWidth="2" />
          )}
          {actualPoints.map((p) => (
            <text key={`v-${p.year}`} x={xForYear(p.year)} y={yForValue(p.value) - 8} textAnchor="middle" fontSize="9" fontWeight="700" fill="var(--color-ink-charcoal)">
              {p.value}
            </text>
          ))}
          {forecastYear !== null && forecastValue !== null && (
            <text x={paddingX + years.length * step} y={yForValue(forecastValue) - 8} textAnchor="middle" fontSize="9" fontWeight="700" fill="var(--color-deep-navy)">
              예측:{forecastValue}
            </text>
          )}
          {years.map((year) => (
            <text key={`x-${year}`} x={xForYear(year)} y={chartHeight} textAnchor="end" fontSize="9" fill="var(--color-stone-gray)" transform={`rotate(-40 ${xForYear(year)} ${chartHeight})`}>
              {year}
            </text>
          ))}
          {forecastYear !== null && (
            <text x={paddingX + years.length * step} y={chartHeight} textAnchor="end" fontSize="9" fill="var(--color-deep-navy)" transform={`rotate(-40 ${paddingX + years.length * step} ${chartHeight})`}>
              {forecastYear}
            </text>
          )}
        </svg>
      </div>
      <p className={styles.emptyText}>검색 키워드(AI 자동생성): {keyword}</p>
    </div>
  );
}

function DensityGridView({ grid }: { grid: typeof MOCK_DENSITY_GRID }) {
  const cellMap = new Map<string, (typeof MOCK_DENSITY_GRID.cells)[number]>();
  grid.cells.forEach((cell) => cellMap.set(`${cell.x},${cell.y}`, cell));
  const maxCount = Math.max(0, ...grid.cells.map((c) => c.count));

  const items: Array<(typeof MOCK_DENSITY_GRID.cells)[number] | null> = [];
  for (let y = 0; y < grid.grid_rows; y += 1) {
    for (let x = 0; x < grid.grid_cols; x += 1) {
      items.push(cellMap.get(`${x},${y}`) ?? null);
    }
  }

  return (
    <div className={styles.densityWrap}>
      <div className={styles.densityGrid} style={{ gridTemplateColumns: `repeat(${grid.grid_cols}, 1fr)`, gridTemplateRows: `repeat(${grid.grid_rows}, 1fr)` }}>
        {items.map((cell, index) => {
          const color = cell ? getDensityColor(cell.count, maxCount) : "rgba(21, 50, 140, 0.05)";
          const ratio = cell && maxCount > 0 ? cell.count / maxCount : 0;
          return (
            <div key={index} className={styles.densityCell} style={{ background: color, color: ratio > 0.5 ? "var(--color-white)" : "var(--color-ink-charcoal)" }}>
              {cell && (
                <>
                  <span className={styles.densityCount}>{cell.count}</span>
                  <span className={styles.densitySigungu}>{cell.sigungu}</span>
                </>
              )}
            </div>
          );
        })}
      </div>
      <p className={styles.emptyText}>
        * 진한 색일수록 동종업종 벤처기업 밀집 · 상위 {grid.shown_sigungu_count}개 지역 기준 (전체 {grid.total_sigungu_count}개 중)
      </p>
    </div>
  );
}

export default DiagnosisTechReport_test;
