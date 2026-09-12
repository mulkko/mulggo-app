import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import marketStyles from "../../styles/diagnosisMarketReport.module.css";
import techStyles from "../../styles/diagnosisTechReport.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import { authHeaders } from "../../auth/session";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const POLL_INTERVAL_MS = 2000;

interface BarItem {
  label: string;
  value: number;
  suffix?: string;
}

/** 카페형 "반경 500m 업종 구성" 막대그래프 - emkim99님 DiagnosisMarketReport.tsx의
 * .sectionCard/.barRow 스타일 그대로 재사용(사용자 확인, 로직은 그대로 디자인만 이관). */
function MarketBarChart({ title, items }: { title: string; items: BarItem[] }) {
  if (items.length === 0) return null;
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <section className={marketStyles.sectionCard}>
      <h2 className={marketStyles.sectionTitle}>{title}</h2>
      {items.map((item) => (
        <div key={item.label} className={marketStyles.barRow}>
          <span className={marketStyles.barLabel}>{item.label}</span>
          <span className={marketStyles.barTrack}>
            <span
              className={`${marketStyles.barFill} ${item.value === max ? marketStyles.barFillMax : ""}`}
              style={{ width: `${(item.value / max) * 100}%` }}
            />
          </span>
          <span className={marketStyles.barCount}>
            {item.value}
            {item.suffix ?? ""}
          </span>
        </div>
      ))}
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

/** 기술창업형 "유사 벤처기업 인증유형 구성" 막대그래프 - emkim99님 DiagnosisTechReport.tsx의
 * .sectionCard/.barRow(+색상 순환) 스타일 그대로 재사용. */
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

// [2026-09-12, 사용자 확인] 반경 500m 업종 구성을 도넛(파이)으로 보여주는 대안 시안 -
// 프론트 디자인이 emkim99님 걸로 최종 확정되기 전, 세션 중 논의된 실험적 추가안이라
// "프론트 완성 후 추가"로 보류. 막대그래프 아래에 [임시] 타이틀을 달아 그대로 남겨둔다
// (사용자 확인) - 나중에 정식 반영 여부를 다시 결정하면 됨.
interface DonutSlice {
  label: string;
  value: number;
  color: string;
  exploded: boolean;
}

const DONUT_TOP4_COLORS = [
  "var(--color-teal-green)",
  "var(--color-light-teal)",
  "var(--color-deep-navy)",
  "var(--color-tab-active-icon)",
];
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
    ...top4.map((item, i) => ({ label: item.label, value: item.value, color: DONUT_TOP4_COLORS[i], exploded: true })),
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

/** 반경 500m 동일업종 밀집도 격자 - emkim99님 DiagnosisTechReport.tsx의 getDensityColor
 * 색상 공식 + .densityGrid/.densityCell 스타일 그대로 재사용(카페형 전용 - 기술창업형은
 * 아직 밀집도 데이터를 안 만들어서 그대로 미노출). */
function getDensityColor(count: number, maxCount: number): string {
  const ratio = maxCount > 0 ? count / maxCount : 0;
  return `rgba(21, 50, 140, ${(0.1 + ratio * 0.7).toFixed(2)})`;
}

function DensityGrid({ title, gridSize, cells }: { title: string; gridSize: number; cells: DensityCell[] }) {
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
              style={{ background: getDensityColor(count, max), color: count / max > 0.5 ? "var(--color-white)" : "var(--color-ink-charcoal)" }}
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

/** 연도별 특허출원 건수 추이 - emkim99님 DiagnosisTechReport.tsx의 PatentChart를 그대로
 * 포팅(신뢰구간 실선/예측 잠정치 점선 구분, 예측연도 별도 표시). */
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

interface DiagnosisReportResponse {
  success: boolean;
  data?: {
    ready: boolean;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    marketAnalysis?: any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    techAnalysis?: any;
    targetAnchor?: string | null;
    differentiatorAnchor?: string | null;
  };
  error?: { message: string };
}

/**
 * "질응답 내용 정리" → "업종코드 보여주기"(DiagnosisIndustryResult) 다음에 뜨는
 * "분석 리포트" 화면 (사용자 확인) - 매장형태에 따라 카페형(상권분석)/기술창업형
 * (기술창업분석) 리포트를 그래프·도표로 보여준다.
 *
 * [2026-09-12] 로직(세션 폴링·빠른매칭 분기·Q7·Q8 앵커)은 이 화면 그대로 두고,
 * 화면 디자인(통계 카드/막대그래프/밀집도/특허추이)만 emkim99님이 만든
 * DiagnosisMarketReport.tsx/DiagnosisTechReport.tsx(디자인 참고용으로 파일만 남김,
 * 라이브 흐름에서는 안 씀)의 CSS 그대로 가져다 씀(사용자 확인). 도넛차트(대안 시안)는
 * "프론트 완성 후 추가"로 보류된 실험적 요소라 막대그래프 아래에 [임시] 타이틀로 남겨둠.
 *
 * [2026-09-12] 6번(지역) 제출 이후(POST /start는 요약 화면 버튼으로 트리거) 업종코드
 * 매칭만 끝내고 바로 업종코드 결과 화면으로 넘어가고, 상권/기술창업 분석은 백그라운드
 * 에서 계속 돈다. 이 화면 자체도 GET /api/diagnosis/{sessionId}/report를 2초 간격으로
 * 폴링하지만(안 끝났으면 "분석 중이에요" 스피너), [2026-09-12, 사용자 확인] 실제로
 * 기다리는 화면은 한 단계 앞(DiagnosisIndustryResult)으로 옮겨져서 - 여기 도착할
 * 때는 이미 완료돼있는 게 정상 경로다. 이 폴링은 직접 URL 접근 등 예외 상황을 위한
 * 안전망으로 그대로 남겨둠. 완료되면 받은 데이터를 sessionStorage에도 저장해
 * Q7·Q8 화면의 앵커 문구로 이어 쓴다.
 *
 * "다음"은 진단방식선택(DiagnosisChoice)에서 고른 mode로 갈린다:
 *   - fast(빠른 진단): 선택 질문(Q7~Q10) 없이 바로 공고매칭리스트(/matching)로.
 *   - precise(정밀 진단): 7번(타깃)으로 이어서 Q7~Q10을 더 진행.
 */
function DiagnosisReport() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [reportReady, setReportReady] = useState(false);
  const [reportError, setReportError] = useState("");
  const [track, setTrack] = useState<"cafe" | "tech" | undefined>(undefined);
  const [mode, setMode] = useState<"fast" | "precise">("precise");
  const [ksicQuery, setKsicQuery] = useState("");
  const [sido, setSido] = useState("");
  const [industryName, setIndustryName] = useState("");
  const [industryState, setIndustryState] = useState("");
  const [industryConfidence, setIndustryConfidence] = useState("");

  // 카페형(상권분석)
  const [sameIndustryCount, setSameIndustryCount] = useState<number | null>(null);
  const [footfallScore, setFootfallScore] = useState<number | null>(null);
  const [footfallBasis, setFootfallBasis] = useState<string | null>(null);
  const [showFootfallTip, setShowFootfallTip] = useState(false);
  const [residentPopulation, setResidentPopulation] = useState<number | null>(null);
  const [industryMixItems, setIndustryMixItems] = useState<BarItem[]>([]);
  const [totalNearbyCount, setTotalNearbyCount] = useState(0);
  const [densityGrid, setDensityGrid] = useState<{ gridSize: number; cells: DensityCell[] } | null>(null);

  // 기술창업형
  const [similarCount, setSimilarCount] = useState<number | null>(null);
  const [recentInvestmentCount, setRecentInvestmentCount] = useState<number | null>(null);
  const [typeDistItems, setTypeDistItems] = useState<BarItem[]>([]);
  const [patentTrend, setPatentTrend] = useState<PatentTrendData | null>(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const applyAnalysis = (forTrack: "cafe" | "tech" | undefined, marketAnalysis: any, techAnalysis: any) => {
    if (forTrack === "cafe") {
      const m = marketAnalysis ?? {};
      setSameIndustryCount(m.density?.same_industry_count ?? null);
      setFootfallScore(m.footfall?.score ?? null);
      setFootfallBasis(m.footfall?.basis ?? null);
      setResidentPopulation(m.resident_population?.resident_population ?? null);
      setIndustryMixItems(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (m.industry_mix ?? []).map((row: any) => ({ label: row["업종명"], value: row["업체수"], suffix: "곳" })),
      );
      setTotalNearbyCount(m.total_nearby_count ?? 0);
      if (m.density?.grid) {
        setDensityGrid({ gridSize: m.density.grid.grid_size, cells: m.density.grid.cells });
      }
    } else if (forTrack === "tech") {
      const t = techAnalysis ?? {};
      const patent = t.patent_forecast;
      setSimilarCount(t.similar_count ?? null);
      setRecentInvestmentCount(t.recent_investment_count ?? null);
      setTypeDistItems(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (t.type_distribution ?? []).map((row: any) => ({ label: row["인증유형"], value: row["비율(%)"] })),
      );
      if (patent?.actual) {
        setPatentTrend({
          actual: patent.actual,
          forecast: patent.forecast ?? null,
          reliableYears: patent.reliable_years ?? [],
          keyword: patent.keyword ?? "",
        });
      }
    }
  };

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.sessionId) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }
    setTrack(answers.track);
    setMode(answers.mode ?? "precise");
    setKsicQuery((answers.resolvedKsicCodes ?? []).join(","));
    setSido(answers.sido ?? "");
    setIndustryName(answers.industryMatchName ?? "");
    setIndustryState(answers.industryMatchState ?? "");
    setIndustryConfidence(answers.industryMatchConfidence ?? "");
    setReady(true);

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/diagnosis/${answers.sessionId}/report`, {
          headers: authHeaders(),
        });
        if (cancelled) return;
        if (res.status === 401) {
          setReportError("로그인이 필요해요. 로그인 후 다시 시도해주세요.");
          return;
        }
        const body: DiagnosisReportResponse = await res.json();
        if (!body.success || !body.data) {
          setReportError(body.error?.message || "분석 리포트를 불러오지 못했어요.");
          return;
        }
        if (!body.data.ready) {
          timer = setTimeout(poll, POLL_INTERVAL_MS);
          return;
        }
        applyAnalysis(answers.track, body.data.marketAnalysis, body.data.techAnalysis);
        saveDiagnosisAnswers({
          marketAnalysis: body.data.marketAnalysis,
          techAnalysis: body.data.techAnalysis,
          targetAnchor: body.data.targetAnchor ?? undefined,
          differentiatorAnchor: body.data.differentiatorAnchor ?? undefined,
        });
        setReportReady(true);
      } catch {
        if (!cancelled) timer = setTimeout(poll, POLL_INTERVAL_MS); // 네트워크 일시 오류 - 계속 재시도
      }
    };
    poll();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/industry-result");
  const handleNext = () => {
    if (mode === "fast") {
      navigate(`/matching?ksic=${encodeURIComponent(ksicQuery)}&region=${encodeURIComponent(sido)}`);
    } else {
      navigate("/diagnosis/7");
    }
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="100%" stepLabel="AI 제안 · 분석 리포트" />
      <div className={styles.scrollArea}>
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
          {industryName ? (
            <>
              <span className={styles.resultTitle}>
                🏷 {industryName}
                {industryState && industryState !== "추천" ? ` (${industryState})` : ""}
              </span>
              <span className={styles.resultDesc}>
                신뢰도 {industryConfidence || "-"} · KSIC {ksicQuery || "-"}
              </span>
            </>
          ) : (
            <span className={styles.resultDesc}>업종을 특정하지 못했어요.</span>
          )}
        </div>

        {reportReady && track === "cafe" && (
          <>
            <div className={marketStyles.statGrid}>
              <div className={marketStyles.statCard}>
                <span className={marketStyles.statLabel}>반경 500m 동일 업종</span>
                {sameIndustryCount !== null ? (
                  <span className={marketStyles.statValue}>{sameIndustryCount}곳</span>
                ) : (
                  <span className={marketStyles.statValueEmpty}>-</span>
                )}
              </div>
              <div className={marketStyles.statCard}>
                <button
                  type="button"
                  className={marketStyles.infoButton}
                  onClick={() => setShowFootfallTip((prev) => !prev)}
                  aria-label="생활인구지수 설명"
                  aria-pressed={showFootfallTip}
                >
                  ?
                </button>
                {showFootfallTip && (
                  <div className={marketStyles.infoTooltip}>
                    {footfallBasis ?? "비교할 생활/유동인구 데이터가 없어요."}
                  </div>
                )}
                <span className={marketStyles.statLabel}>생활인구지수</span>
                {footfallScore !== null ? (
                  <span className={`${marketStyles.statValue} ${marketStyles.statValueAccent}`}>{footfallScore}</span>
                ) : (
                  <span className={marketStyles.statValueEmpty}>-</span>
                )}
              </div>
              <div className={marketStyles.statCard}>
                <span className={marketStyles.statLabel}>상주인구수</span>
                <span className={marketStyles.statValue}>
                  {residentPopulation !== null ? `${residentPopulation.toLocaleString()}명` : "-"}
                </span>
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
              totalCount={totalNearbyCount}
            />
            {densityGrid && (
              <DensityGrid title="반경 500m 동일업종 밀집도" gridSize={densityGrid.gridSize} cells={densityGrid.cells} />
            )}
          </>
        )}

        {reportReady && track === "tech" && (
          <>
            <div className={techStyles.statGrid}>
              <div className={techStyles.statCard}>
                <span className={techStyles.statLabel}>유사 벤처인증기업 수</span>
                <span className={techStyles.statValue}>{similarCount !== null ? `${similarCount}개` : "-"}</span>
              </div>
              <div className={techStyles.statCard}>
                <span className={techStyles.statLabel}>벤처투자형 인증 (1년)</span>
                <span className={techStyles.statValue}>{recentInvestmentCount !== null ? `${recentInvestmentCount}건` : "-"}</span>
              </div>
              <div className={`${techStyles.statCard} ${techStyles.statCardHighlight}`}>
                <span className={techStyles.statLabel}>매칭 지원사업 수</span>
                <span className={techStyles.statValueEmpty}>다음 화면에서 확인해요</span>
              </div>
            </div>

            <TechBarChart title="유사 기업 인증유형 구성" items={typeDistItems} />
            {patentTrend && <PatentChart title="관련분야 특허출원 추이 (KIPRIS)" data={patentTrend} />}
            <p className={techStyles.sourceText}>출처: 중기부 벤처기업명단·특허청 KIPRIS 기준 · 개별 성공 확률 아님</p>
          </>
        )}

        {reportError && <p className={styles.errorText}>{reportError}</p>}
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={handleBack}>
          이전
        </button>
        <button type="button" className={styles.nextButton} disabled={!reportReady} onClick={handleNext}>
          {mode === "fast" ? "지원사업 보러가기 →" : "다음 →"}
        </button>
      </div>
      {!reportReady && !reportError && (
        <div className={styles.loadingOverlay}>
          <div className={styles.loadingBox} role="status" aria-live="polite">
            <div className={styles.spinner} />
            <p className={styles.loadingText}>
              {track === "cafe" ? "상권 리포트를 분석하고 있어요..." : "기술창업 리포트를 분석하고 있어요..."}
            </p>
            <p className={styles.loadingHint}>업종코드 매칭은 끝났어요 - 데이터만 마저 준비할게요</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default DiagnosisReport;
