import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import marketStyles from "../../styles/diagnosisMarketReport.module.css";
import techStyles from "../../styles/diagnosisTechReport.module.css";
import { authHeaders } from "../../auth/session";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";
import BottomNav from "../../components/BottomNav/BottomNav";
import logo from "../../assets/logo.svg";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const POLL_INTERVAL_MS = 2000;
const MAX_NETWORK_RETRIES = 10;

interface BarItem {
  label: string;
  value: number;
  suffix?: string;
}

// [2026-09-13, 사용자 확인] 프로토타입 원본 대조 결과, 막대그래프 상위 4개 색상은
// 카페형("반경 500m 업종 구성")·기술창업형("유사 기업 인증유형 구성") 둘 다 원래
// 이 팔레트 하나를 공유하도록 디자인돼 있었다 - 도넛차트(같은 데이터, 같은 순위를
// 보여줌)도 이 팔레트를 그대로 재사용한다(사용자 확인, 2026-09-13) - 도넛 쪽에
// 조각 위에 흰 글씨를 얹는 렌더링이 실제로는 없어서(범례 텍스트는 항상 잉크차콜/
// 스톤그레이 고정색), 별도 대비색 팔레트가 필요하지 않다는 게 확인됨.
// [2026-09-13] 3·4번째 색이 --color-stone-gray/--color-dot-inactive였는데 둘 다
// "비활성" 용도로 만들어진 무채색이라 실제로는 색이 없는 것처럼 보였다(사용자 확인 -
// "TOP4는 전부 색이 들어갔으면 좋겠는데") - teal(1번)·gold(2번)와 어울리면서도
// 서로 뚜렷이 구분되는 기존 UI 팔레트 색(딥네이비/퍼플 액센트, 새 색상 아님)으로 교체.
const RANK_BAR_COLORS = [
  "var(--color-light-teal)",
  "var(--color-tab-active-icon)",
  "var(--color-deep-navy)",
  "var(--color-purple-accent)",
];

function getRankBarColor(index: number): string | undefined {
  return RANK_BAR_COLORS[index];
}

/** 카페형 "반경 500m 업종 구성" 막대그래프 - emkim99님 DiagnosisMarketReport.tsx의
 * .sectionCard/.barRow 스타일 그대로 재사용(사용자 확인, 로직은 그대로 디자인만 이관).
 * [2026-09-13] 상위 4개만 색을 넣고 5~10위는 기존 회색 유지(사용자 확인) - 라벨
 * 위치·색은 diagnosisMarketReport.module.css의 640px 미디어쿼리가 처리(640px 미만:
 * 막대 위에 겹쳐 표시, 상위 4개는 흰 글씨). */
function MarketBarChart({ title, items }: { title: string; items: BarItem[] }) {
  if (items.length === 0) return null;
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <section className={`${marketStyles.sectionCard} ${marketStyles.sectionCardNested}`}>
      <span className={marketStyles.sectionTitle}>{title}</span>
      {items.map((item, index) => {
        const barColor = getRankBarColor(index);
        return (
          <div key={item.label} className={marketStyles.barRow}>
            <span className={marketStyles.barLabel}>{item.label}</span>
            <span className={marketStyles.barTrack}>
              <span
                className={marketStyles.barFill}
                style={{
                  width: `${(item.value / max) * 100}%`,
                  ...(barColor ? { background: barColor } : {}),
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
              style={{ width: `${item.value}%`, background: getRankBarColor(index) }}
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

function DonutChart({
  title,
  items,
  detailTitle,
}: {
  title: string;
  items: BarItem[];
  /** [2026-09-13, 사용자 확인] 폴딩을 열면 도넛 카드 안에 같은 items로 막대그래프를
   * 서브 콘텐츠로 보여준다 - 그 막대그래프의 타이틀. */
  detailTitle: string;
}) {
  const [expanded, setExpanded] = useState(false);
  if (items.length === 0) return null;
  // [2026-09-13, 사용자 확인] totalCount를 반경 내 "전체" 업체 수(top10 밖의 것까지
  // 포함)로 넘기면, top10만 그리는 이 도넛에서 top10 밖 몫이 안 보이는 채로 통째로
  // "기타"에 흡수돼 top4 조각이 원 전체에서 지나치게 작아 보였다 - top10 자체를
  // 100%로 보이게, 넘어온 items(top10)의 합만으로 totalCount를 다시 계산한다.
  const totalCount = items.reduce((sum, item) => sum + item.value, 0);
  if (totalCount <= 0) return null;
  const top4 = items.slice(0, 4);
  const top4Sum = top4.reduce((sum, item) => sum + item.value, 0);
  const otherValue = Math.max(totalCount - top4Sum, 0);

  const slices: DonutSlice[] = [
    ...top4.map((item, i) => ({ label: item.label, value: item.value, color: getRankBarColor(i) ?? "var(--color-stone-gray)", exploded: true })),
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
      <div className={styles.chartCardHead}>
        <h2 className={styles.chartTitle}>{title}</h2>
        <button
          type="button"
          className={styles.chartFoldButton}
          onClick={() => setExpanded((prev) => !prev)}
          aria-expanded={expanded}
        >
          {expanded ? "간단히 보기 ▲" : "자세히 보기 ▼"}
        </button>
      </div>
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
      {expanded && <MarketBarChart title={detailTitle} items={items} />}
    </div>
  );
}

interface DensityCell {
  x: number;
  y: number;
  count: number;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function mixRgb(c1: [number, number, number], c2: [number, number, number], t: number): string {
  return `rgb(${Math.round(lerp(c1[0], c2[0], t))}, ${Math.round(lerp(c1[1], c2[1], t))}, ${Math.round(lerp(c1[2], c2[2], t))})`;
}

// [2026-09-13, 사용자 확인] 프로토타입(13번 상권분석 화면)의 실제 범례를 대조해보니
// 단일 러스트색+투명도만으로는(예전 getDensityColor) "느낌"이 달랐다 - 진짜는 3단
// 그라데이션(진한 러스트 → 55% 지점 주황 → 연한 크림)이었다:
//   linear-gradient(rgb(122,42,10), rgb(240,168,104) 55%, rgb(251,241,228))
// 밀집도가 높을수록(ratio=1) 위쪽 진한 러스트, 0일수록 아래쪽 연크림에 가깝게
// 매핑한다(그라데이션 바가 위=진함/아래=옅음이라 위치% = 1-ratio 관계).
const MARKET_DENSITY_HIGH: [number, number, number] = [122, 42, 10];
const MARKET_DENSITY_MID: [number, number, number] = [240, 168, 104];
const MARKET_DENSITY_LOW: [number, number, number] = [251, 241, 228];
const MARKET_DENSITY_MID_RATIO = 1 - 0.55; // 그라데이션 55% 지점 = ratio 0.45

function getMarketDensityColor(ratio: number): string {
  if (ratio >= MARKET_DENSITY_MID_RATIO) {
    const t = (ratio - MARKET_DENSITY_MID_RATIO) / (1 - MARKET_DENSITY_MID_RATIO);
    return mixRgb(MARKET_DENSITY_MID, MARKET_DENSITY_HIGH, t);
  }
  const t = ratio / MARKET_DENSITY_MID_RATIO;
  return mixRgb(MARKET_DENSITY_LOW, MARKET_DENSITY_MID, t);
}

/** 반경 500m 동일업종 밀집도 격자 색상 - [2026-09-13] 프로토타입(260911_Mulkko
 * Prototype) 원본 대조로 확인한 결과, 상권분석(카페형)은 위 3단 러스트 그라데이션,
 * 기술창업형은 네이비 계열(#15328C = --color-deep-navy) 단색+투명도로 서로 다르게
 * 디자인돼 있었다. 값(카운트) 계산은 그대로, 색상 매핑만 트랙별로 다르다. */
function getDensityColor(count: number, maxCount: number, track: "cafe" | "tech"): string {
  const ratio = maxCount > 0 ? count / maxCount : 0;
  if (track === "cafe") return getMarketDensityColor(ratio);
  return `rgba(21, 50, 140, ${(0.1 + ratio * 0.7).toFixed(2)})`;
}

// [2026-09-13, 사용자 확인] 밀집도 범례 눈금 - 프로토타입은 8,6,4,2,0(카페형)/9,7,5,3,1
// (기술창업형) 같은 5단계 숫자였는데, maxCount 기준으로 균등 5분할하면 정확히 같은
// 패턴이 나온다(예: max=8 → 8,6,4,2,0) - 실제 데이터의 max를 그대로 반영한다.
function buildDensityTicks(max: number): number[] {
  return [1, 0.75, 0.5, 0.25, 0].map((t) => Math.round(max * t));
}

/** 카페형 "반경 500m 동일업종 밀집도" - [2026-09-13, 사용자 확인] 프로토타입(13번
 * 상권분석 화면) 문구 전체 대조 후 소제목·범례 눈금·"내 위치" 마커·안내문구를
 * 추가했다. "상위 N개 지역 기준(전체 M개 중)" 문구는 프로토타입엔 있었지만 카페형
 * 백엔드(density.py)가 애초에 "지역 랭킹"이 아니라 500m를 5x5 좌표 격자로 나눈
 * 것이라(center_cell만 있고 total/shown region 개념이 없음) 여기엔 넣지 않는다
 * (사용자 확인 - "각자 맞는거를 추가해줘"). */
function DensityGrid({
  title,
  subtitle,
  gridSize,
  cells,
  centerCell,
  track,
}: {
  title: string;
  subtitle?: string;
  gridSize: number;
  cells: DensityCell[];
  centerCell?: [number, number] | null;
  track: "cafe" | "tech";
}) {
  // [2026-09-14, 사용자 확인] 예전엔 cells가 비어있으면(반경 내 동일업종 0곳) 이
  // 섹션 자체가 통째로 사라졌다 - 카드도 제목도 없이 조용히 안 보여서 "왜 밀집도가
  // 안 나오냐"는 문의로 이어짐(실측, 셀렉박스 기본값인 1순위 후보가 0곳인 경우가
  // 실제로 있었음). 특허차트 실패 케이스와 같은 원칙 - 데이터가 없어도 카드는
  // 남기고 안내 문구로 보여준다.
  if (cells.length === 0) {
    return (
      <section className={marketStyles.sectionCard}>
        <h2 className={marketStyles.sectionTitle}>{title}</h2>
        {subtitle && <span className={marketStyles.densitySubtitle}>{subtitle}</span>}
        <p className={marketStyles.densityNote}>반경 500m 안에 동일업종이 없어요.</p>
      </section>
    );
  }
  const max = Math.max(...cells.map((c) => c.count), 1);
  const byPos = new Map(cells.map((c) => [`${c.x},${c.y}`, c.count]));
  const grid = Array.from({ length: gridSize * gridSize }, (_, i) => {
    const x = i % gridSize;
    const y = Math.floor(i / gridSize);
    return byPos.get(`${x},${y}`) ?? 0;
  });
  const ticks = buildDensityTicks(max);
  return (
    <section className={marketStyles.sectionCard}>
      <h2 className={marketStyles.sectionTitle}>{title}</h2>
      {subtitle && <span className={marketStyles.densitySubtitle}>{subtitle}</span>}
      <div className={techStyles.densityWrap}>
        <div className={marketStyles.densityRow}>
          <div
            className={techStyles.densityGrid}
            style={{ gridTemplateColumns: `repeat(${gridSize}, 1fr)`, gridTemplateRows: `repeat(${gridSize}, 1fr)` }}
          >
            {grid.map((count, i) => {
              const x = i % gridSize;
              const y = Math.floor(i / gridSize);
              const isMyLocation = !!centerCell && centerCell[0] === x && centerCell[1] === y;
              return (
                <div
                  key={i}
                  className={techStyles.densityCell}
                  style={{ background: getDensityColor(count, max, track), color: count / max > 0.5 ? "var(--color-white)" : "var(--color-ink-charcoal)" }}
                >
                  {count > 0 && <span className={techStyles.densityCount}>{count}</span>}
                  {isMyLocation && <span className={marketStyles.densityCellMarker} />}
                </div>
              );
            })}
          </div>
          {/* [2026-09-13, 사용자 확인] 프로토타입(13번 상권분석 화면)에 있던 밀집도
              범례 - 그래프 위쪽(진한 러스트)일수록 밀집도가 높다는 걸 색과 숫자
              눈금으로 보여준다. 기술창업형(track="tech")은 이 컴포넌트를 안 써서
              (아래 TechDensityGrid가 별도 범례를 그림) 카페형 전용이나 다름없다. */}
          {track === "cafe" && (
            <div className={marketStyles.densityLegend}>
              <div className={marketStyles.densityLegendBar} />
              <div className={marketStyles.densityLegendTicks}>
                {ticks.map((t, i) => (
                  <span key={i}>{t}</span>
                ))}
              </div>
              <span className={marketStyles.densityLegendCaption}>사업체 수</span>
            </div>
          )}
        </div>
        <div className={marketStyles.densityCaptionRow}>
          <span>* 진한 색일수록 동일업종 밀집</span>
          {centerCell && (
            <>
              <span className={marketStyles.densityCellMarkerLegend} />
              <span>= 내 위치</span>
            </>
          )}
        </div>
        <p className={marketStyles.densityNote}>* 실제 지도가 아닌 상대적 밀집도를 표현한 도식입니다.</p>
      </div>
    </section>
  );
}

// [2026-09-13] 기술창업형 "동종산업 밀집도" - DiagnosisTechReport.tsx(emkim99님 디자인
// 참고 화면)의 DensityGridView를 그대로 포팅. 카페형(위 DensityGrid)과 데이터 모양이
// 달라서(카페형: 정사각 gridSize 하나 + x/y/count, 기술창업형: grid_cols×grid_rows
// 직사각형 + 시군구별 count/지역명) 별도 컴포넌트로 분리 - 억지로 하나로 합치면
// 카페형 정사각형 가정이 깨지거나 지역명 표시가 빠진다. 색상은 기존 getDensityColor
// (track="tech")를 그대로 재사용 - 이미 네이비 계열로 트랙 분기돼 있음.
interface TechDensityCell {
  x: number;
  y: number;
  count: number;
  sigungu: string;
}

interface TechDensityGridData {
  grid_cols: number;
  grid_rows: number;
  cells: TechDensityCell[];
  total_sigungu_count: number;
  shown_sigungu_count: number;
}

/** [2026-09-13, 사용자 확인] 프로토타입(13번 상권분석 화면 문구 대조 - 기술창업형도
 * 같은 구조) 원본 대비 범례(네이비 그라데이션+눈금)·캡션·안내문구를 추가했다.
 * [2026-09-14, 사용자 확인] "내 위치" 마커도 카페형처럼 추가함 - 기술창업형은
 * "상위 N개 지역 랭킹"이라 중심좌표(center_cell) 개념은 없지만, 진단 시 입력한
 * 지역(myLocation, "시도 시군구")이 랭킹 안에 있으면(cell.sigungu와 문자열 일치)
 * 그 칸에 표시한다. 카페형(항상 격자 중심에 있음)과 달리 상위 N 밖이면 표시 자체가
 * 안 뜰 수 있다(정상 - 순위 밖이라는 뜻). sigungu 원본 표기가 소스마다 다를 수
 * 있어(예: "서울" vs "서울특별시") 드물게 실제로는 있는데 못 찾을 수도 있음. */
function TechDensityGrid({ grid, myLocation }: { grid: TechDensityGridData; myLocation?: string }) {
  const cellMap = new Map<string, TechDensityCell>();
  grid.cells.forEach((cell) => cellMap.set(`${cell.x},${cell.y}`, cell));
  const maxCount = Math.max(0, ...grid.cells.map((c) => c.count));
  const ticks = buildDensityTicks(maxCount);

  const items: Array<TechDensityCell | null> = [];
  for (let y = 0; y < grid.grid_rows; y += 1) {
    for (let x = 0; x < grid.grid_cols; x += 1) {
      items.push(cellMap.get(`${x},${y}`) ?? null);
    }
  }
  const hasMyLocationCell = !!myLocation && items.some((cell) => cell?.sigungu === myLocation);

  return (
    <div className={techStyles.densityWrap}>
      <div className={techStyles.densityRow}>
        <div
          className={techStyles.densityGrid}
          style={{ gridTemplateColumns: `repeat(${grid.grid_cols}, 1fr)`, gridTemplateRows: `repeat(${grid.grid_rows}, 1fr)` }}
        >
          {items.map((cell, index) => {
            const color = getDensityColor(cell?.count ?? 0, maxCount, "tech");
            const ratio = cell && maxCount > 0 ? cell.count / maxCount : 0;
            const isMyLocation = !!myLocation && cell?.sigungu === myLocation;
            return (
              <div key={index} className={techStyles.densityCell} style={{ background: color, color: ratio > 0.5 ? "var(--color-white)" : "var(--color-ink-charcoal)" }}>
                {cell && (
                  <>
                    <span className={techStyles.densityCount}>{cell.count}</span>
                    <span className={techStyles.densitySigungu}>{cell.sigungu}</span>
                  </>
                )}
                {isMyLocation && <span className={techStyles.densityCellMarker} />}
              </div>
            );
          })}
        </div>
        <div className={techStyles.densityLegend}>
          <div className={techStyles.densityLegendBar} />
          <div className={techStyles.densityLegendTicks}>
            {ticks.map((t, i) => (
              <span key={i}>{t}</span>
            ))}
          </div>
          <span className={techStyles.densityLegendCaption}>기업 수</span>
        </div>
      </div>
      <div className={techStyles.densityCaptionRow}>
        <span>* 진한 색일수록 동종업종 벤처기업 밀집</span>
        {hasMyLocationCell && (
          <>
            <span className={techStyles.densityCellMarkerLegend} />
            <span>= 내 위치</span>
          </>
        )}
      </div>
      <p className={techStyles.emptyText}>
        * 실제 지도가 아닌 상대적 밀집도를 표현한 도식입니다.
        <br />* 상위 {grid.shown_sigungu_count}개 지역 기준 (전체 {grid.total_sigungu_count}개 중)
      </p>
    </div>
  );
}

interface PatentTrendData {
  actual: Record<string, number | null>;
  forecast: Record<string, number> | null;
  reliableYears: number[];
  keyword: string;
}

/** 연도별 특허출원 건수 추이 - [2026-09-14, 사용자 확인] 프로토타입("관련분야
 * 특허출원 추이 (KIPRIS)" 화면) 원본 마크업을 기반으로, 예측연도 표현 방식만 다시
 * 조정함: 예측연도(신뢰구간 마지막 해+1)의 실측치는 공개지연으로 과소집계된
 * 값이라 선·점 높이는 실측이 아니라 보정된 예측치를 기준으로 그린다(추세선이
 * 실제로 없는 급락처럼 보이지 않게) - 이 구간만 점선+빈 원으로 "확정 아님"을
 * 표시하고, "예측:N"을 메인 라벨로, "현재:n"(실측)은 점 아래에 작게 보조로 둔다.
 * 예측연도 이후(공개지연으로 예측 자체가 불가능한 연도)는 선·점 없이 x축 라벨과
 * "예측불가" 텍스트만 남긴다. */
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

  // [2026-09-14, 사용자 확인] 예측연도(forecastYear) 그 이후 연도는 예측 자체가
  // 불가능하다고 판별된 거라 선/점을 아예 안 그리고(unplottableYears), x축 라벨+
  // "예측불가" 텍스트만 남긴다.
  const unplottableYears = forecastYear !== null ? years.filter((y) => y > forecastYear) : [];
  const reliablePlottable = actualPoints.filter((p) => reliableSet.has(p.year));
  // [2026-09-14, 사용자 확인] 예측연도의 실측치(현재)는 공개지연으로 과소집계된
  // 값이라, 선·점의 높이는 실측치가 아니라 보정된 예측치를 기준으로 그린다(그래야
  // 추세선이 "실제로는 없는 급락"처럼 안 보임) - 점선으로 구분해서 이 구간이
  // 확정치가 아니라 추정이라는 걸 표시한다. 실측치(현재)는 점 옆에 작게 보조로만.
  const forecastActual = forecastYear !== null ? actualPoints.find((p) => p.year === forecastYear) : undefined;

  const allValues = reliablePlottable
    .map((p) => p.value)
    .concat(forecastValue !== null ? [forecastValue] : []);
  const maxValue = Math.max(...allValues, 1);
  const minValue = Math.min(...allValues, 0);

  const step = 36;
  const paddingX = 22;
  const plotHeight = 110; // 점·선·값 라벨이 그려지는 영역 - 기존 chartHeight 그대로 유지
  const topPad = 22;
  // [2026-09-13, 사용자 확인] 값이 0인 지점의 숫자 라벨(yForValue(0) 근처)이 -40도로
  // 기울어진 연도 라벨(labelY 기준선)과 겨우 6px 차이라 서로 겹쳐 보이는 문제가
  // 있었다(실측) - 16으로 늘려서 0값 지점과 연도 라벨 사이 실제 간격을 확보한다.
  const bottomPad = 16;
  // [2026-09-13, 사용자 확인] 연도 라벨(-40도 회전)이 plotHeight 경계선(라벨 기준선)
  // 바로 아래에 딱 붙어있어서, 회전된 글자의 아랫부분이 SVG 자체 높이 밖으로 잘려
  // 보이는 문제가 있었다("년도가 잘려보임", 실측) - CSS가 svg 높이를 고정값(120px)으로
  // 강제해서 viewBox와 안 맞으면 세로로 눌려 찍히기까지 해서, 라벨 기준선(labelY)은
  // 그대로 두고 그 아래로 회전된 글자가 통째로 들어갈 여유(LABEL_EXTRA)만큼 SVG 전체
  // 높이를 늘렸다 - 값 영역(topPad/bottomPad/점·선 위치)은 그대로.
  const LABEL_EXTRA = 30;
  const labelY = plotHeight;
  const chartHeight = plotHeight + LABEL_EXTRA;

  const xForYear = (year: number) => paddingX + years.indexOf(year) * step;
  const yForValue = (value: number) => {
    if (maxValue === minValue) return plotHeight - bottomPad - (plotHeight - topPad - bottomPad) / 2;
    const ratio = (value - minValue) / (maxValue - minValue);
    return plotHeight - bottomPad - ratio * (plotHeight - topPad - bottomPad);
  };

  const solidPolyline = reliablePlottable.map((p) => `${xForYear(p.year)},${yForValue(p.value)}`).join(" ");
  const lastReliable = reliablePlottable[reliablePlottable.length - 1];
  const forecastX = forecastYear !== null ? xForYear(forecastYear) : null;
  const dashedPolyline =
    lastReliable && forecastX !== null && forecastValue !== null
      ? `${xForYear(lastReliable.year)},${yForValue(lastReliable.value)} ${forecastX},${yForValue(forecastValue)}`
      : "";
  const unpredictableX = unplottableYears.length > 0 ? xForYear(unplottableYears[0]) : null;
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
            style={{ width: `${Math.max(chartWidth, 280)}px`, height: `${chartHeight}px` }}
          >
            {solidPolyline && (
              <polyline points={solidPolyline} fill="none" stroke="var(--color-light-teal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            )}
            {/* [2026-09-14, 사용자 확인] 예측연도 구간은 점선 - 실측이 아니라 추정이라는 표시. */}
            {dashedPolyline && (
              <polyline points={dashedPolyline} fill="none" stroke="var(--color-light-teal)" strokeWidth="2" strokeDasharray="4 3" strokeLinecap="round" />
            )}

            {reliablePlottable.map((p) => (
              <circle key={p.year} cx={xForYear(p.year)} cy={yForValue(p.value)} r="4" fill="var(--color-light-teal)" />
            ))}
            {/* [2026-09-14, 사용자 확인] 예측연도 점은 실측치가 아니라 예측치 높이에 -
                속이 빈 원으로 "확정 아님"을 표시. "예측:N"이 메인(다른 연도 값과 같은
                크기·색), "현재:n"(실측, 과소집계)은 점 아래에 작게 보조로만. */}
            {forecastX !== null && forecastValue !== null && (
              <circle cx={forecastX} cy={yForValue(forecastValue)} r="4" fill="var(--color-white)" stroke="var(--color-light-teal)" strokeWidth="2" />
            )}

            {reliablePlottable.map((p) => (
              <text key={`v-${p.year}`} x={xForYear(p.year)} y={yForValue(p.value) - 8} textAnchor="middle" fontSize="9" fontWeight="700" fill="var(--color-ink-charcoal)">
                {p.value}
              </text>
            ))}
            {forecastX !== null && forecastValue !== null && (
              <text x={forecastX} y={yForValue(forecastValue) - 8} textAnchor="middle" fontSize="9" fontWeight="700" fill="var(--color-ink-charcoal)">
                예측:{forecastValue}
              </text>
            )}
            {forecastX !== null && forecastActual && (
              <text x={forecastX} y={yForValue(forecastValue ?? forecastActual.value) + 15} textAnchor="middle" fontSize="7.5" fill="var(--color-stone-gray)">
                현재:{forecastActual.value}
              </text>
            )}

            {unpredictableX !== null && (
              <text x={unpredictableX} y={plotHeight / 2} textAnchor="middle" fontSize="8.5" fontWeight="700" fill="var(--color-stone-gray)">
                예측불가
              </text>
            )}

            {years.map((year) => (
              <text
                key={`x-${year}`}
                x={xForYear(year)}
                y={labelY}
                textAnchor="end"
                fontSize="9"
                fill="var(--color-stone-gray)"
                transform={`rotate(-40 ${xForYear(year)} ${labelY})`}
              >
                {year}
                {!reliableSet.has(year) && year <= (forecastYear ?? year) ? "*" : ""}
              </text>
            ))}
          </svg>
        </div>
        {hasUnreliableYears && (
          <>
            <p className={techStyles.patentNote}>* 잠정치(특허 공개 지연 반영) · 2025년은 현재 집계와 연간 예측치를 함께 표기</p>
            <p className={techStyles.patentNote}>* 2026년은 특허 공개 지연으로 현재 집계 수치만 제공, 예측 불가</p>
          </>
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
    // [2026-09-13] 업종코드 후보(최대 3개) 전부의 분석 결과 - 코드 -> {marketAnalysis,
    // techAnalysis} 맵. 상단 셀렉박스가 이걸로 후보를 전환해가며 보여준다.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    analysisByCode?: Record<string, any>;
    targetAnchor?: string | null;
    differentiatorAnchor?: string | null;
    // [2026-09-13] 마이페이지에서 지난 세션을 URL로 바로 열 때(sessionStorage 없음)
    // 이 응답만으로 화면을 채우기 위한 필드 - ready:true일 때만 내려온다.
    track?: "cafe" | "tech";
    resolvedKsicCodes?: string[];
    mode?: "fast" | "precise";
    sido?: string;
    dong?: string;
    industryMatchName?: string | null;
    industryMatchState?: string | null;
    industryMatchConfidence?: string | null;
    industryMatchCodeNames?: Record<string, string>;
  };
  error?: { message: string };
}

/** [2026-09-13, 사용자 확인] 업종코드 후보(최소 1개~최대 3개) 선택 UI - 프로토타입
 * (260911_Mulkko Prototype, reportCodeOptions/ddToggle.code 상태 대조로 확인) 원본
 * 그대로 이식했다: 겉모습은 셀렉트박스(칩 트리거+드롭다운)지만 기능은 후보 중
 * 하나만 고르는 라디오(단일 선택)다. 스타일은 프로토타입 원본 색(#F2FAF9/#0F6E62/
 * #3FB6A8 계열)을 그대로 쓰지 않고, 가장 가까운 기존 스타일가이드 토큰(--color-teal-mist/
 * --color-teal-green/--shadow-inset-teal)으로 매핑했다(사용자 확인 - "스타일가이드가
 * 최우선"). 후보가 1개뿐이어도 프로토타입처럼 항상 렌더링한다(구조 통일). */
function IndustryCodeSelect({
  codes,
  industryName,
  codeNames,
  selectedCode,
  onSelect,
  analysisByCode,
}: {
  codes: string[];
  industryName: string;
  // [2026-09-14] 후보 3개가 전부 같은 industryName(1순위 이름)을 찍던 버그 수정 -
  // 코드별 이름이 있으면 그걸 쓰고, 없으면(구버전 세션 등) industryName으로 폴백.
  codeNames: Record<string, string>;
  selectedCode: string;
  onSelect: (code: string) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  analysisByCode: Record<string, any>;
}) {
  const [open, setOpen] = useState(false);

  if (codes.length === 0) {
    return <p className={styles.industrySelectEmpty}>업종을 특정하지 못했어요.</p>;
  }

  const activeCode = selectedCode || codes[0];
  const name = codeNames[activeCode] || industryName || "업종 미확인";

  return (
    <div className={styles.industrySelectWrap}>
      <button
        type="button"
        className={styles.industrySelectTrigger}
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
      >
        <span className={styles.industrySelectLabel}>
          {name} 업종코드 {activeCode}
        </span>
        <svg
          viewBox="0 0 24 24"
          width="14"
          height="14"
          fill="none"
          stroke="var(--color-teal-green)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          style={{ flexShrink: 0, transform: open ? "rotate(180deg)" : undefined }}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && (
        <div className={styles.industrySelectPanel} role="listbox">
          {codes.map((code) => {
            const isSelected = code === activeCode;
            return (
              <div
                key={code}
                role="option"
                aria-selected={isSelected}
                className={`${styles.industrySelectOption} ${isSelected ? styles.industrySelectOptionActive : ""}`}
                onClick={() => {
                  onSelect(code);
                  setOpen(false);
                }}
              >
                {codeNames[code] || industryName || "업종 미확인"} 업종코드 {code}
                {analysisByCode[code]?.failed ? " (분석 실패)" : ""}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
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
 * [2026-09-13] 6번(지역) 제출 직후(POST /start)부터 업종코드 후보(최대 3개) 전부에
 * 대해 상권/기술창업 분석이 백그라운드로 바로 시작된다(예전엔 사용자가 업종을 하나
 * 확정해야만 POST /{id}/select-industry로 시작했는데, 강제 선택 자체를 없앰 - 사용자
 * 확인). 이 화면 자체도 GET /api/diagnosis/{sessionId}/report를 2초 간격으로
 * 폴링하지만(안 끝났으면 "분석 중이에요" 스피너), 실제로 기다리는 화면은 한 단계 앞
 * (DiagnosisIndustryResult)이라 여기 도착할 때는 이미 완료돼있는 게 정상 경로다. 이
 * 폴링은 직접 URL 접근 등 예외 상황을 위한 안전망으로 그대로 남겨둠. 완료되면 받은
 * 데이터를 sessionStorage에도 저장해 Q7·Q8 화면의 앵커 문구로 이어 쓴다(1순위 후보
 * 기준 고정, 사용자 확인).
 *
 * [2026-09-13] 후보가 2개 이상이면 상단에 셀렉박스를 보여줘서 analysisByCode(코드별
 * 결과 맵)에서 원하는 후보로 전환해가며 볼 수 있게 한다(사용자 확인) - Q7·Q8 앵커
 * 문구·"다음" 이동 경로는 셀렉박스 선택과 무관하게 항상 1순위 후보 기준 그대로.
 *
 * "다음"은 진단방식선택(DiagnosisChoice)에서 고른 mode로 갈린다:
 *   - fast(빠른 진단): 선택 질문(Q7~Q10) 없이 바로 공고매칭리스트(/matching)로.
 *   - precise(정밀 진단): 7번(타깃)으로 이어서 Q7~Q10을 더 진행.
 */
function DiagnosisReport() {
  const navigate = useNavigate();
  // [2026-09-13] 마이페이지 "분석 리포트" 카드에서 옴 - /diagnosis/report/:sessionId로
  // 들어오면 sessionStorage(실시간 흐름 전용) 대신 이 세션ID로 API에서 바로 불러온다.
  const { sessionId: sessionIdParam } = useParams<{ sessionId?: string }>();
  const viewSessionId = sessionIdParam ? Number(sessionIdParam) : undefined;
  const [ready, setReady] = useState(false);
  const [reportReady, setReportReady] = useState(false);
  const [reportError, setReportError] = useState("");
  const [track, setTrack] = useState<"cafe" | "tech" | undefined>(undefined);
  const [mode, setMode] = useState<"fast" | "precise">("precise");
  const [ksicQuery, setKsicQuery] = useState("");
  const [sido, setSido] = useState("");
  const [industryName, setIndustryName] = useState("");
  const [industryCodeNames, setIndustryCodeNames] = useState<Record<string, string>>({});
  // [2026-09-13] 프로토타입(13번 상권분석 화면)의 밀집도 소제목("{동} 반경 500m
  // {업종명}({코드}) 밀집도")에 필요해서 추가 - 이전엔 이 화면이 sido만 들고 있었다.
  const [dong, setDong] = useState("");
  // [2026-09-13] 업종코드 후보(최대 3개) 전부의 분석 결과 - 상단 셀렉박스가 이 맵에서
  // selectedCode에 해당하는 항목을 골라 보여준다(후보 1개면 셀렉박스 자체를 숨김).
  const [resolvedCodes, setResolvedCodes] = useState<string[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [analysisByCode, setAnalysisByCode] = useState<Record<string, any>>({});
  const [selectedCode, setSelectedCode] = useState("");
  // [2026-09-13, 사용자 확인] "매칭 지원사업 수" - 이 시점엔 이미 업종코드가 확정돼있어서
  // "다음 화면에서 확인해요" 대신 실제 건수를 보여줄 수 있다. GET /api/matching이 이미
  // 진짜 매칭 건수(COUNT(*) 기반 total, limit과 무관하게 정확함)를 내려주고 있어서
  // limit=1로 최소한만 받아온다 - 목록 자체는 필요 없고 숫자만 쓴다.
  const [matchedCount, setMatchedCount] = useState<number | null>(null);
  // [2026-09-14, 사용자 확인] matchedCount==null만으로는 "아직 로딩 중"과 "조회 실패"를
  // 구분 못 해서 로딩 중에도 계속 안내 문구만 보였다 - 로딩 중엔 문구 대신 작은
  // 스피너만 돌게 별도 상태로 분리.
  const [matchedCountLoading, setMatchedCountLoading] = useState(false);

  // 카페형(상권분석)
  const [sameIndustryCount, setSameIndustryCount] = useState<number | null>(null);
  const [footfallScore, setFootfallScore] = useState<number | null>(null);
  const [footfallBasis, setFootfallBasis] = useState<string | null>(null);
  const [showFootfallTip, setShowFootfallTip] = useState(false);
  const [residentPopulation, setResidentPopulation] = useState<number | null>(null);
  const [industryMixItems, setIndustryMixItems] = useState<BarItem[]>([]);
  const [densityGrid, setDensityGrid] = useState<{
    gridSize: number;
    cells: DensityCell[];
    centerCell: [number, number] | null;
  } | null>(null);

  // 기술창업형
  const [similarCount, setSimilarCount] = useState<number | null>(null);
  const [recentInvestmentCount, setRecentInvestmentCount] = useState<number | null>(null);
  const [typeDistItems, setTypeDistItems] = useState<BarItem[]>([]);
  const [patentTrend, setPatentTrend] = useState<PatentTrendData | null>(null);
  const [techDensityGrid, setTechDensityGrid] = useState<TechDensityGridData | null>(null);

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
      if (m.density?.grid) {
        setDensityGrid({
          gridSize: m.density.grid.grid_size,
          cells: m.density.grid.cells,
          centerCell: m.density.grid.center_cell ?? null,
        });
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
      if (t.density_grid) {
        setTechDensityGrid(t.density_grid);
      }
    }
  };

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    const sessionId = viewSessionId ?? answers.sessionId;
    if (!sessionId) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }

    // 실시간 흐름(sessionStorage 있음)은 기존처럼 즉시 채워서 분석 끝나기 전에도
    // 업종매칭 요약 카드가 바로 보이게 한다. 지난 세션을 URL로 바로 연 경우
    // (viewSessionId)는 sessionStorage가 없으니 poll() 첫 응답에서 채운다.
    if (!viewSessionId) {
      setTrack(answers.track);
      setMode(answers.mode ?? "precise");
      const codes = answers.resolvedKsicCodes ?? [];
      setKsicQuery(codes.join(","));
      setResolvedCodes(codes);
      setAnalysisByCode(answers.analysisByCode ?? {});
      setSelectedCode(codes[0] ?? "");
      setSido(answers.sido ?? "");
      setDong(answers.dong ?? "");
      setIndustryName(answers.industryMatchName ?? "");
      setIndustryCodeNames(answers.industryMatchCodeNames ?? {});
    }
    setReady(true);

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    // [2026-09-12] 네트워크 오류가 계속되면(백엔드에 아예 안 닿는 경우 등) 예전엔 에러
    // 표시 없이 계속 조용히 재시도해서 "무한 로딩"처럼 보이는 문제가 있었다(사용자
    // 확인) - 10번(20초) 넘게 연속 실패하면 재시도를 멈추고 에러를 보여준다.
    let networkRetries = 0;
    // [2026-09-13] "ready: false"만 계속 오는 경우엔 이 한도가 없었다(위와 별개) -
    // DiagnosisIndustryResult.tsx와 동일한 이유로 상한을 둔다.
    let notReadyRetries = 0;
    const MAX_NOT_READY_RETRIES = 60;

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/diagnosis/${sessionId}/report`, {
          headers: authHeaders(),
          cache: "no-store", // [2026-09-13] 폴링 GET이 캐시된 옛 응답을 계속 재사용하는 걸 방지
        });
        if (cancelled) return;
        networkRetries = 0;
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
          notReadyRetries += 1;
          if (notReadyRetries >= MAX_NOT_READY_RETRIES) {
            setReportError("분석이 예상보다 오래 걸리고 있어요. 잠시 후 다시 시도해주세요.");
            return;
          }
          timer = setTimeout(poll, POLL_INTERVAL_MS);
          return;
        }
        const resolvedTrack = viewSessionId ? body.data.track : answers.track;
        const byCode = body.data.analysisByCode ?? {};
        setAnalysisByCode(byCode);
        if (viewSessionId) {
          const codes = body.data.resolvedKsicCodes ?? [];
          setTrack(body.data.track);
          setMode(body.data.mode ?? "precise");
          setKsicQuery(codes.join(","));
          setResolvedCodes(codes);
          setSelectedCode((prev) => prev || codes[0] || "");
          setSido(body.data.sido ?? "");
          setDong(body.data.dong ?? "");
          setIndustryName(body.data.industryMatchName ?? "");
          setIndustryCodeNames(body.data.industryMatchCodeNames ?? {});
        } else {
          setSelectedCode((prev) => prev || (answers.resolvedKsicCodes ?? [])[0] || "");
        }
        applyAnalysis(resolvedTrack, body.data.marketAnalysis, body.data.techAnalysis);
        if (!viewSessionId) {
          // sessionStorage 갱신은 지금 진행 중인 흐름(Q7·Q8 앵커로 이어씀)에만 의미 있다 -
          // 지난 세션 조회는 현재 진행 중인 답변을 덮어쓰면 안 되므로 건드리지 않는다.
          saveDiagnosisAnswers({
            marketAnalysis: body.data.marketAnalysis,
            techAnalysis: body.data.techAnalysis,
            analysisByCode: byCode,
            targetAnchor: body.data.targetAnchor ?? undefined,
            differentiatorAnchor: body.data.differentiatorAnchor ?? undefined,
          });
        }
        setReportReady(true);
      } catch {
        if (cancelled) return;
        networkRetries += 1;
        if (networkRetries >= MAX_NETWORK_RETRIES) {
          setReportError("서버에 연결할 수 없어요. 네트워크 상태를 확인하고 다시 시도해주세요.");
          return;
        }
        timer = setTimeout(poll, POLL_INTERVAL_MS); // 네트워크 일시 오류 - 한도 내에서 계속 재시도
      }
    };
    poll();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigate, viewSessionId]);

  // [2026-09-13] 셀렉박스에서 후보를 바꾸면 그 코드의 analysisByCode 항목으로 다시
  // 그린다 - 최초 로드 시 poll()이 이미 primary 데이터로 한 번 그려두므로, 여기서는
  // selectedCode가 실제로 바뀌었을 때(사용자가 셀렉박스를 조작했을 때)만 의미있게 동작한다.
  useEffect(() => {
    if (!reportReady || !selectedCode) return;
    const entry = analysisByCode[selectedCode];
    if (!entry) return;
    applyAnalysis(track, entry.marketAnalysis, entry.techAnalysis);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCode, analysisByCode, reportReady, track]);

  // [2026-09-13, 사용자 확인] "매칭 지원사업 수" 실제 건수 - 지금 선택된 후보 코드
  // 기준으로만 센다(셀렉박스로 후보를 바꾸면 다시 조회) - 목록 화면(/matching)의
  // "다음" 버튼은 후보 전체(ksicQuery)로 넘어가지만, 이 카드는 지금 보고 있는
  // 후보 하나에 대한 숫자를 보여주는 게 맞다고 판단.
  //
  // [2026-09-13, 사용자 확인] total(정확히 매칭된 것)만 세면 안 되고, "업종무관"·
  // "특정불가"(ksic_codes_matched가 항상 빈 배열이라 어떤 업종을 필터링해도 배열
  // 겹침에 안 걸리는 공고들 - 실제로는 "어떤 업종에도 해당" 또는 "분류만 실패했을
  // 뿐 제한 없음"이라는 뜻, backend/api/matching.py list_announcements() 독스트링
  // 참고)도 매칭 건수에 포함해야 한다 - GET /api/matching이 ksic 필터가 있을 때 이
  // 두 그룹을 total/unclassified_total로 분리해서 내려주므로 둘을 더한다(/matching
  // 화면 자체도 두 섹션을 같이 보여주지, 진짜매칭 섹션만 보여주는 게 아님).
  useEffect(() => {
    if (!reportReady || !selectedCode || !sido) return;
    let cancelled = false;
    setMatchedCount(null);
    setMatchedCountLoading(true);
    fetch(
      `${API_BASE_URL}/api/matching?ksic=${encodeURIComponent(selectedCode)}&region=${encodeURIComponent(sido)}&limit=1&unclassified_limit=1`,
      { headers: authHeaders() },
    )
      .then((res) => res.json())
      .then((body: { success: boolean; total?: number; unclassified_total?: number }) => {
        if (cancelled) return;
        if (!body.success || typeof body.total !== "number") {
          setMatchedCount(null);
          return;
        }
        setMatchedCount(body.total + (body.unclassified_total ?? 0));
      })
      .catch(() => {
        if (!cancelled) setMatchedCount(null);
      })
      .finally(() => {
        if (!cancelled) setMatchedCountLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reportReady, selectedCode, sido]);

  // 지난 세션을 보는 중이면 "이어서 진단하기" 개념 자체가 없다 - 뒤로가기는 마이페이지로,
  // "다음"은 항상 매칭 화면으로 보낸다(fast 모드와 동일 취급).
  const handleBack = () => (viewSessionId ? navigate("/mypage") : navigate("/diagnosis/industry-result"));
  const handleNext = () => {
    if (viewSessionId || mode === "fast") {
      navigate(`/matching?ksic=${encodeURIComponent(ksicQuery)}&region=${encodeURIComponent(sido)}`);
    } else {
      navigate("/diagnosis/7");
    }
  };

  if (!ready) return null;

  // [2026-09-13, 사용자 확인] 상단 헤더 - 처음엔 _backup/DiagnosisMarketReport.tsx·
  // DiagnosisTechReport.tsx가 쓰던 "뒤로가기+제목 한 줄" 헤더로 교체했는데, 사용자가
  // "프로토타입이랑 다르다"고 지적해서 프로토타입(260911_Mulkko Prototype) 원문을 다시
  // 대조해보니 그 backup 파일들은 구버전 디자인이었다 - 실제 최신 프로토타입은 2단
  // 구조: (1) 52px 흰 배경에 뒤로가기+"MULKKO REPORT" 워드마크(다른 화면 헤더에도 이미
  // 있는 로고 패턴, matchingList.module.css의 .logo/.logoText/.logoMark와 완전히 동일한
  // 스펙이라 그대로 재사용), (2) 그 아래 38px 라이트틸 배경 바에 흰 글씨로 화면
  // 이름("상권분석 리포트"/"기술창업분석 리포트") - 카페형/기술창업형 둘 다 같은 색
  // (#3FB6A8 = --color-light-teal) 헤더를 쓰고 문구만 다르다(프로토타입 원본 대조 확인).
  const activeStyles = track === "tech" ? techStyles : marketStyles;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.reportHeader}>
        <div className={styles.reportHeaderTop}>
          <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M16 5l-8 7 8 7" />
            </svg>
          </button>
          <span className={styles.logo}>
            <span className={styles.logoText}>MULKKO REPORT</span>
            <img src={logo} alt="물꼬 로고" className={styles.logoMark} />
          </span>
        </div>
        <div className={styles.reportHeaderBar}>
          <span className={styles.reportHeaderBarText}>
            {track === "cafe" ? "상권분석 리포트" : "기술창업분석 리포트"}
          </span>
        </div>
      </header>
      <div className={styles.scrollArea}>
        <IndustryCodeSelect
          codes={resolvedCodes}
          industryName={industryName}
          codeNames={industryCodeNames}
          selectedCode={selectedCode}
          onSelect={setSelectedCode}
          analysisByCode={analysisByCode}
        />
        <h1 className={activeStyles.regionTitle}>
          {track === "cafe" ? `${dong} 주변 상권 동향` : "업종 및 특허분석 지표"}
        </h1>

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
                {matchedCountLoading ? (
                  <span className={styles.statSpinner} role="status" aria-label="불러오는 중" />
                ) : matchedCount !== null ? (
                  <span className={marketStyles.statValue}>{matchedCount}건</span>
                ) : (
                  <span className={marketStyles.statValueEmpty}>다음 화면에서 확인해요</span>
                )}
              </div>
            </div>

            <DonutChart
              title="반경 500m 업종 구성"
              items={industryMixItems}
              detailTitle="업체 수 상위 10개"
            />
            {densityGrid && (
              <DensityGrid
                title="반경 500m 동일업종 밀집도"
                subtitle={dong ? `${dong} 반경 500m ${industryName || "업종"}(${selectedCode || ksicQuery}) 밀집도` : undefined}
                gridSize={densityGrid.gridSize}
                cells={densityGrid.cells}
                centerCell={densityGrid.centerCell}
                track="cafe"
              />
            )}
            <p className={marketStyles.sourceText}>출처: 소상공인시장진흥공단 상권데이터·기업마당(bizinfo) 기준 · 예측 아님</p>
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
                {matchedCountLoading ? (
                  <span className={styles.statSpinner} role="status" aria-label="불러오는 중" />
                ) : matchedCount !== null ? (
                  <span className={techStyles.statValue}>{matchedCount}건</span>
                ) : (
                  <span className={techStyles.statValueEmpty}>다음 화면에서 확인해요</span>
                )}
              </div>
            </div>

            <TechBarChart title="유사 기업 인증유형 구성" items={typeDistItems} />
            {patentTrend ? (
              <PatentChart title="관련분야 특허출원 추이 (KIPRIS)" data={patentTrend} />
            ) : (
              // [2026-09-13] 특허 예측은 외부 API(KIPRIS/OpenAI) 호출이라 실패해도 진단
              // 자체는 막지 않게 설계돼 있는데(diagnosis.py 주석 참고), 그래서 실패하면
              // 이 섹션이 원래 없었던 것처럼 조용히 사라져 "왜 안 나오지" 원인 파악이
              // 어려웠다(사용자 확인, 실측) - 실패도 눈에 보이게 안내 문구로 표시.
              <section className={techStyles.sectionCard}>
                <h2 className={techStyles.sectionTitle}>관련분야 특허출원 추이 (KIPRIS)</h2>
                <p className={techStyles.emptyText}>특허 데이터를 불러오지 못했어요. 잠시 후 다시 진단해보시면 나올 수 있어요.</p>
              </section>
            )}
            {/* [2026-09-14, 사용자 확인] 예전엔 techDensityGrid가 없으면(데이터 계산 실패
                등) 카드 제목까지 통째로 사라졌다 - 카페형 밀집도와 같은 이유로 "왜 안
                나오냐"는 혼동을 만들 수 있어서, 데이터가 없어도 카드는 남기고 안내
                문구로 보여준다(특허차트 실패 케이스와 동일 원칙). */}
            <section className={techStyles.sectionCard}>
              <h2 className={techStyles.sectionTitle}>동종산업 밀집도</h2>
              {techDensityGrid ? (
                <TechDensityGrid grid={techDensityGrid} myLocation={sido && dong ? `${sido} ${dong}` : undefined} />
              ) : (
                <p className={techStyles.emptyText}>표시할 밀집도 데이터가 없어요.</p>
              )}
            </section>
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
          {viewSessionId || mode === "fast" ? "지원사업 보러가기" : "다음"}
          <svg
            className={styles.nextButtonIcon}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M8 5l8 7-8 7" />
          </svg>
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

      <BottomNav active="idea" />
    </div>
  );
}

export default DiagnosisReport;
