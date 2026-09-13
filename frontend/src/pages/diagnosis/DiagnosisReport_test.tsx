import { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import marketStyles from "../../styles/diagnosisMarketReport.module.css";
import techStyles from "../../styles/diagnosisTechReport.module.css";
import DiagnosisHeader from "./DiagnosisHeader";

/**
 * [개인 테스트용, 원본 DiagnosisReport.tsx의 격리 사본] sessionStorage/세션 폴링 의존
 * 없이 목업 데이터로 차트 렌더링만 바로 확인하는 페이지 - 백엔드 호출 자체가 없다.
 * 카페형/기술창업형 목업을 버튼으로 바로 전환해서 둘 다 한 페이지에서 볼 수 있다.
 *
 * [2026-09-12] 디자인을 emkim99님의 DiagnosisMarketReport.tsx/DiagnosisTechReport.tsx
 * 것으로 갈아입힘(사용자 확인) - 아래 차트 컴포넌트는 DiagnosisReport.tsx 것을 그대로
 * 복사(공유 모듈로 뽑는 건 이번 범위 밖, 테스트 전용 파일이라 git에도 안 올라감).
 */

interface BarItem {
  label: string;
  value: number;
  suffix?: string;
}

// [2026-09-13] 도넛차트와 상위 4개 색상 통일(DiagnosisReport.tsx와 동일 이유 - 골드
// (--color-tab-active-icon)는 흰 글씨 명암비 미달이라 --color-purple-accent로 교체).
const TOP4_COLORS = [
  "var(--color-teal-green)",
  "var(--color-light-teal)",
  "var(--color-deep-navy)",
  "var(--color-purple-accent)",
];

function getTop4Color(index: number): string | undefined {
  return TOP4_COLORS[index];
}

function MarketBarChart({ title, items }: { title: string; items: BarItem[] }) {
  if (items.length === 0) return null;
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <section className={marketStyles.sectionCard}>
      <h2 className={marketStyles.sectionTitle}>{title}</h2>
      {items.map((item, index) => {
        const top4Color = getTop4Color(index);
        return (
          <div key={item.label} className={marketStyles.barRow}>
            <span className={`${marketStyles.barLabel} ${top4Color ? marketStyles.barLabelOnFill : ""}`}>
              {item.label}
            </span>
            <span className={marketStyles.barTrack}>
              <span
                className={marketStyles.barFill}
                style={{
                  width: `${(item.value / max) * 100}%`,
                  ...(top4Color ? { background: top4Color } : {}),
                }}
              />
            </span>
            <span className={marketStyles.barCount}>
              {item.value}
              {item.suffix ?? ""}
            </span>
          </div>
        );
      })}
    </section>
  );
}

const TECH_BAR_COLORS = [
  "var(--color-light-teal)",
  "var(--color-tab-active-icon)",
  "var(--color-stone-gray)",
  "var(--color-dot-inactive)",
];

function getTechBarColor(index: number): string {
  return TECH_BAR_COLORS[index] ?? TECH_BAR_COLORS[TECH_BAR_COLORS.length - 1];
}

function TechBarChart({ title, items }: { title: string; items: BarItem[] }) {
  if (items.length === 0) return null;
  return (
    <section className={techStyles.sectionCard}>
      <h2 className={techStyles.sectionTitle}>{title}</h2>
      {items.map((item, index) => (
        <div key={item.label} className={techStyles.barRow}>
          <span className={techStyles.barLabel}>{item.label}</span>
          <span className={techStyles.barTrack}>
            <span
              className={techStyles.barFill}
              style={{ width: `${item.value}%`, background: getTechBarColor(index) }}
            />
          </span>
          <span className={techStyles.barCount}>{item.value.toFixed(1)}%</span>
        </div>
      ))}
    </section>
  );
}

interface DonutSlice {
  label: string;
  value: number;
  color: string;
  exploded: boolean;
}

const DONUT_OTHER_COLOR = "rgba(139, 141, 147, 0.35)";
const DONUT_OUTER_R = 42;
const DONUT_INNER_R = 24;
const DONUT_EXPLODE_OFFSET = 5;

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function describeAnnularSector(rOuter: number, rInner: number, startAngle: number, endAngle: number): string {
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  const outerStart = polarToCartesian(0, 0, rOuter, startAngle);
  const outerEnd = polarToCartesian(0, 0, rOuter, endAngle);
  const innerEnd = polarToCartesian(0, 0, rInner, endAngle);
  const innerStart = polarToCartesian(0, 0, rInner, startAngle);
  return [
    `M ${outerStart.x} ${outerStart.y}`,
    `A ${rOuter} ${rOuter} 0 ${largeArc} 1 ${outerEnd.x} ${outerEnd.y}`,
    `L ${innerEnd.x} ${innerEnd.y}`,
    `A ${rInner} ${rInner} 0 ${largeArc} 0 ${innerStart.x} ${innerStart.y}`,
    "Z",
  ].join(" ");
}

function DonutChart({ title, items, totalCount }: { title: string; items: BarItem[]; totalCount: number }) {
  if (items.length === 0 || totalCount <= 0) return null;
  const top4 = items.slice(0, 4);
  const top4Sum = top4.reduce((sum, item) => sum + item.value, 0);
  const otherValue = Math.max(totalCount - top4Sum, 0);

  const slices: DonutSlice[] = [
    ...top4.map((item, i) => ({ label: item.label, value: item.value, color: TOP4_COLORS[i], exploded: true })),
    ...(otherValue > 0 ? [{ label: "기타", value: otherValue, color: DONUT_OTHER_COLOR, exploded: false }] : []),
  ];

  let cumulative = 0;
  const arcs = slices.map((slice) => {
    const startAngle = (cumulative / totalCount) * 360;
    cumulative += slice.value;
    const endAngle = (cumulative / totalCount) * 360;
    const midAngle = (startAngle + endAngle) / 2;
    const offset = slice.exploded ? polarToCartesian(0, 0, DONUT_EXPLODE_OFFSET, midAngle) : { x: 0, y: 0 };
    return { ...slice, path: describeAnnularSector(DONUT_OUTER_R, DONUT_INNER_R, startAngle, endAngle), offset };
  });

  return (
    <div className={styles.chartCard}>
      <span className={styles.chartTitle}>{title}</span>
      <div className={styles.donutRow}>
        <svg className={styles.donutSvg} viewBox="-50 -50 100 100">
          {arcs.map((arc) => (
            <path
              key={arc.label}
              d={arc.path}
              fill={arc.color}
              transform={`translate(${arc.offset.x} ${arc.offset.y})`}
            />
          ))}
        </svg>
        <div className={styles.donutLegend}>
          {slices.map((slice) => (
            <div key={slice.label} className={styles.donutLegendRow}>
              <span className={styles.donutLegendDot} style={{ background: slice.color }} />
              <span className={styles.donutLegendLabel}>{slice.label}</span>
              <span className={styles.donutLegendValue}>
                {slice.value}곳 ({((slice.value / totalCount) * 100).toFixed(1)}%)
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface DensityCell {
  x: number;
  y: number;
  count: number;
}

// [2026-09-13] 프로토타입 원본 대조 확인 - 상권분석은 러스트(#7A2A0A =
// --color-market-density), 기술창업형은 네이비(#15328C) 계열로 서로 다름(사용자 확인).
function getDensityColor(count: number, maxCount: number, track: "cafe" | "tech"): string {
  const ratio = maxCount > 0 ? count / maxCount : 0;
  const rgb = track === "cafe" ? "122, 42, 10" : "21, 50, 140";
  return `rgba(${rgb}, ${(0.1 + ratio * 0.7).toFixed(2)})`;
}

function DensityGrid({
  title,
  gridSize,
  cells,
  track,
}: {
  title: string;
  gridSize: number;
  cells: DensityCell[];
  track: "cafe" | "tech";
}) {
  if (cells.length === 0) return null;
  const max = Math.max(...cells.map((c) => c.count), 1);
  const byPos = new Map(cells.map((c) => [`${c.x},${c.y}`, c.count]));
  const grid = Array.from({ length: gridSize * gridSize }, (_, i) => {
    const x = i % gridSize;
    const y = Math.floor(i / gridSize);
    return byPos.get(`${x},${y}`) ?? 0;
  });
  return (
    <section className={marketStyles.sectionCard}>
      <h2 className={marketStyles.sectionTitle}>{title}</h2>
      <div className={techStyles.densityWrap}>
        <div
          className={techStyles.densityGrid}
          style={{ gridTemplateColumns: `repeat(${gridSize}, 1fr)`, gridTemplateRows: `repeat(${gridSize}, 1fr)` }}
        >
          {grid.map((count, i) => (
            <div
              key={i}
              className={techStyles.densityCell}
              style={{ background: getDensityColor(count, max, track), color: count / max > 0.5 ? "var(--color-white)" : "var(--color-ink-charcoal)" }}
            >
              {count > 0 && <span className={techStyles.densityCount}>{count}</span>}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

interface PatentTrendData {
  actual: Record<string, number | null>;
  forecast: Record<string, number> | null;
  reliableYears: number[];
  keyword: string;
}

function PatentChart({ title, data }: { title: string; data: PatentTrendData }) {
  const years = Object.keys(data.actual)
    .map(Number)
    .sort((a, b) => a - b);
  const reliableSet = new Set(data.reliableYears);
  const forecastEntries = Object.entries(data.forecast ?? {});
  const forecastYear = forecastEntries.length > 0 ? Number(forecastEntries[0][0]) : null;
  const forecastValue = forecastEntries.length > 0 ? forecastEntries[0][1] : null;

  const actualPoints = years
    .map((year) => ({ year, value: data.actual[String(year)] }))
    .filter((p): p is { year: number; value: number } => p.value !== null);

  if (actualPoints.length === 0) {
    return (
      <section className={techStyles.sectionCard}>
        <h2 className={techStyles.sectionTitle}>{title}</h2>
        <p className={techStyles.emptyText}>표시할 특허 출원 데이터가 없어요.</p>
      </section>
    );
  }

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
  const reliablePoints = actualPoints.filter((p) => reliableSet.has(p.year));
  const unreliablePoints = actualPoints.filter((p) => !reliableSet.has(p.year));

  const reliablePolyline = reliablePoints.map((p) => `${xForYear(p.year)},${yForValue(p.value)}`).join(" ");
  const unreliableChain = reliablePoints.length > 0 ? [reliablePoints[reliablePoints.length - 1], ...unreliablePoints] : unreliablePoints;
  const unreliablePolyline = unreliableChain.map((p) => `${xForYear(p.year)},${yForValue(p.value)}`).join(" ");

  const chartWidth = paddingX * 2 + Math.max(years.length - 1, 0) * step;
  const hasUnreliableYears = years.some((y) => !reliableSet.has(y));

  return (
    <section className={techStyles.sectionCard}>
      <h2 className={techStyles.sectionTitle}>{title}</h2>
      <div className={techStyles.patentChartWrap}>
        <div className={techStyles.patentChartScroll}>
          <svg
            viewBox={`0 0 ${chartWidth} ${chartHeight}`}
            preserveAspectRatio="none"
            className={techStyles.patentSvg}
            style={{ width: `${Math.max(chartWidth, 280)}px` }}
          >
            {reliablePolyline && (
              <polyline points={reliablePolyline} fill="none" stroke="var(--color-light-teal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            )}
            {unreliablePolyline && unreliableChain.length > 1 && (
              <polyline points={unreliablePolyline} fill="none" stroke="var(--color-light-teal)" strokeWidth="2" strokeDasharray="4 3" strokeLinecap="round" strokeLinejoin="round" opacity="0.55" />
            )}
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

            {reliablePoints.map((p) => (
              <circle key={p.year} cx={xForYear(p.year)} cy={yForValue(p.value)} r="4" fill="var(--color-light-teal)" />
            ))}
            {unreliablePoints.map((p) => (
              <circle key={p.year} cx={xForYear(p.year)} cy={yForValue(p.value)} r="4" fill="var(--color-white)" stroke="var(--color-light-teal)" strokeWidth="2" />
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
              <text
                key={`x-${year}`}
                x={xForYear(year)}
                y={chartHeight}
                textAnchor="end"
                fontSize="9"
                fill="var(--color-stone-gray)"
                transform={`rotate(-40 ${xForYear(year)} ${chartHeight})`}
              >
                {year}
                {!reliableSet.has(year) ? "*" : ""}
              </text>
            ))}
            {forecastYear !== null && (
              <text
                x={paddingX + years.length * step}
                y={chartHeight}
                textAnchor="end"
                fontSize="9"
                fill="var(--color-deep-navy)"
                transform={`rotate(-40 ${paddingX + years.length * step} ${chartHeight})`}
              >
                {forecastYear}
              </text>
            )}
          </svg>
        </div>
        {hasUnreliableYears && (
          <p className={techStyles.patentNote}>* 잠정치·공개지연으로 예측 학습에서 제외된 연도예요</p>
        )}
        <p className={techStyles.emptyText}>검색 키워드(AI 자동생성): {data.keyword}</p>
      </div>
    </section>
  );
}

// 목업 데이터 - 이번 세션 중 실제 API로 검증했던 값 그대로 재사용(서울 종로구
// 청운효자동 카페형 / "AI 코드 리뷰" 기술창업형 예시).
const MOCK_MARKET = {
  footfall: { data_type: "생활인구", score: 63.7, basis: "최근 3개월 평균 대비 생활인구 지수" },
  resident_population: { resident_population: 10799 },
  total_nearby_count: 1241,
  density: {
    same_industry_count: 99,
    grid: {
      grid_size: 5,
      cells: [
        { x: 1, y: 1, count: 3 }, { x: 2, y: 2, count: 8 }, { x: 3, y: 1, count: 2 },
        { x: 0, y: 3, count: 1 }, { x: 4, y: 4, count: 5 }, { x: 2, y: 0, count: 4 },
      ],
    },
  },
  industry_mix: [
    { "업종명": "카페", "업체수": 99 }, { "업종명": "펜션", "업체수": 76 }, { "업종명": "백반/한정식", "업체수": 72 },
    { "업종명": "경양식", "업체수": 61 }, { "업종명": "치킨", "업체수": 40 }, { "업종명": "분식", "업체수": 35 },
    { "업종명": "베이커리", "업체수": 30 }, { "업종명": "편의점", "업체수": 25 }, { "업종명": "미용실", "업체수": 20 },
    { "업종명": "세탁소", "업체수": 15 },
  ],
};

const MOCK_TECH = {
  similar_count: 4132,
  type_distribution: [
    { "인증유형": "혁신성장", "건수": 2035, "비율(%)": 49.2 },
    { "인증유형": "벤처투자", "건수": 1467, "비율(%)": 35.5 },
    { "인증유형": "연구개발", "건수": 611, "비율(%)": 14.8 },
    { "인증유형": "예비벤처", "건수": 19, "비율(%)": 0.5 },
  ],
  recent_investment_count: 320,
  patent_forecast: {
    keyword: "코드 리뷰",
    actual: {
      "2015": 10, "2016": 12, "2017": 15, "2018": 18, "2019": 22, "2020": 28,
      "2021": 35, "2022": 40, "2023": 45, "2024": 48,
    },
    reliable_years: [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022],
    forecast: { "2025": 52 },
  },
};

function DiagnosisReport_test() {
  const navigate = useNavigate();
  const [track, setTrack] = useState<"cafe" | "tech">("cafe");

  const industryMixItems: BarItem[] = MOCK_MARKET.industry_mix.map((r) => ({
    label: r["업종명"], value: r["업체수"], suffix: "곳",
  }));
  const typeDistItems: BarItem[] = MOCK_TECH.type_distribution.map((r) => ({
    label: r["인증유형"], value: r["비율(%)"],
  }));
  const patentTrend: PatentTrendData = {
    actual: MOCK_TECH.patent_forecast.actual,
    forecast: MOCK_TECH.patent_forecast.forecast,
    reliableYears: MOCK_TECH.patent_forecast.reliable_years,
    keyword: MOCK_TECH.patent_forecast.keyword,
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={() => navigate("/diagnosis/summary-test")} pct="100%" stepLabel="AI 제안 · 분석 리포트 [TEST]" />
      <div className={styles.scrollArea}>
        <div style={{ display: "flex", gap: 8, marginBottom: 4 }}>
          <button type="button" className={styles.prevButton} onClick={() => setTrack("cafe")}>
            카페형 보기
          </button>
          <button type="button" className={styles.prevButton} onClick={() => setTrack("tech")}>
            기술창업형 보기
          </button>
        </div>
        <h1 className={styles.questionTitle}>
          {track === "cafe" ? "상권 분석 리포트예요" : "기술창업 분석 리포트예요"}
        </h1>
        <p className={styles.questionSub}>
          {track === "cafe"
            ? "선택하신 지역·업종 기준 상권 데이터예요."
            : "선택하신 업종 기준 유사 벤처기업·특허 데이터예요."}
        </p>
        <div className={styles.resultCard}>
          <span className={styles.resultAxis}>업종코드 매칭 결과</span>
          <span className={styles.resultTitle}>🏷 {track === "cafe" ? "커피 전문점" : "소프트웨어 개발·공급업"}</span>
          <span className={styles.resultDesc}>
            신뢰도 high · KSIC {track === "cafe" ? "56221" : "58222"}
          </span>
        </div>

        {track === "cafe" && (
          <>
            <div className={marketStyles.statGrid}>
              <div className={marketStyles.statCard}>
                <span className={marketStyles.statLabel}>반경 500m 동일 업종</span>
                <span className={marketStyles.statValue}>{MOCK_MARKET.density.same_industry_count}곳</span>
              </div>
              <div className={marketStyles.statCard}>
                <span className={marketStyles.statLabel}>생활인구지수</span>
                <span className={`${marketStyles.statValue} ${marketStyles.statValueAccent}`}>{MOCK_MARKET.footfall.score}</span>
              </div>
              <div className={marketStyles.statCard}>
                <span className={marketStyles.statLabel}>상주인구수</span>
                <span className={marketStyles.statValue}>{MOCK_MARKET.resident_population.resident_population.toLocaleString()}명</span>
              </div>
              <div className={`${marketStyles.statCard} ${marketStyles.statCardHighlight}`}>
                <span className={marketStyles.statLabel}>매칭 지원사업 수</span>
                <span className={marketStyles.statValueEmpty}>다음 화면에서 확인해요</span>
              </div>
            </div>

            <MarketBarChart title="반경 500m 업종 구성 (업체 수 상위 10개)" items={industryMixItems} />
            <DonutChart
              title="[임시] 반경 500m 업종 구성 - 도넛(대안 시안)"
              items={industryMixItems}
              totalCount={MOCK_MARKET.total_nearby_count}
            />
            <DensityGrid
              title="반경 500m 동일업종 밀집도"
              gridSize={MOCK_MARKET.density.grid.grid_size}
              cells={MOCK_MARKET.density.grid.cells}
              track="cafe"
            />
          </>
        )}

        {track === "tech" && (
          <>
            <div className={techStyles.statGrid}>
              <div className={techStyles.statCard}>
                <span className={techStyles.statLabel}>유사 벤처인증기업 수</span>
                <span className={techStyles.statValue}>{MOCK_TECH.similar_count.toLocaleString()}개</span>
              </div>
              <div className={techStyles.statCard}>
                <span className={techStyles.statLabel}>벤처투자형 인증 (1년)</span>
                <span className={techStyles.statValue}>{MOCK_TECH.recent_investment_count}건</span>
              </div>
              <div className={`${techStyles.statCard} ${techStyles.statCardHighlight}`}>
                <span className={techStyles.statLabel}>매칭 지원사업 수</span>
                <span className={techStyles.statValueEmpty}>다음 화면에서 확인해요</span>
              </div>
            </div>

            <TechBarChart title="유사 기업 인증유형 구성" items={typeDistItems} />
            <PatentChart title="관련분야 특허출원 추이 (KIPRIS)" data={patentTrend} />
            <p className={techStyles.sourceText}>출처: 중기부 벤처기업명단·특허청 KIPRIS 기준 · 개별 성공 확률 아님</p>
          </>
        )}
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={() => navigate("/diagnosis/summary-test")}>
          이전
        </button>
        <button type="button" className={styles.nextButton} onClick={() => navigate("/home")}>
          다음 →
        </button>
      </div>
    </div>
  );
}

export default DiagnosisReport_test;
