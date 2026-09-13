import { useNavigate } from "react-router-dom";
import logo from "../../assets/logo.svg";
import styles from "../../styles/diagnosisReportSummary.module.css";

export interface IdeaCard {
  axis: string;
  title: string;
  description: string;
}

interface DiagnosisReportSummaryProps {
  variant: "market" | "tech";
  target: string;
  differentiator: string;
  revenueModel: string;
  coreSkill: string;
  cards: IdeaCard[];
  /** [2026-09-12] 라이브 흐름(DiagnosisStep9)은 emkim99님의 별도 market/tech-report
   * 화면 대신 제 통합 분석리포트(/diagnosis/report)로 되돌아가야 해서, variant 기반
   * 기본 경로를 덮어쓸 수 있게 옵션으로 뺐다. 안 넘기면(프리뷰 등) 기존 기본값 그대로. */
  backPath?: string;
  /** 실제 매칭된 업종코드/지역으로 필터된 매칭 리스트로 보내기 위한 경로 override. */
  matchPath?: string;
}

const AXIS_TONE: Record<string, "target" | "revenue" | "skill"> = {
  "타깃 관점": "target",
  "수익모델 관점": "revenue",
  "보유역량 활용": "skill",
};

const IDEA_CARD_CLASS: Record<"target" | "revenue" | "skill" | "default", string> = {
  target: styles.ideaCardTarget,
  revenue: styles.ideaCardRevenue,
  skill: styles.ideaCardSkill,
  default: styles.ideaCardDefault,
};

const IDEA_BADGE_CLASS: Record<"target" | "revenue" | "skill" | "default", string> = {
  target: styles.ideaBadgeTarget,
  revenue: styles.ideaBadgeRevenue,
  skill: styles.ideaBadgeSkill,
  default: styles.ideaBadgeDefault,
};

/**
 * 13-1(상권분석)/14-2(기술창업분석) 리포트 파트2 — 사업구체화 진단(DiagnosisStep9)
 * 제출 완료 화면. 두 프로토타입 화면(is.reportASum/is.reportBSum)은 구조가 100% 동일하고
 * 헤더 뒤로가기·"이전" 버튼 목적지만 다르므로, variant prop 하나로 통합했다.
 * 지금은 실제 흐름상 상권분석 리포트만 연결돼 있어 DiagnosisStep9에서는 항상
 * variant="market"으로 쓰고, "tech"는 기술창업 리포트가 나중에 연결될 때를 위해 미리
 * 만들어둔 것.
 */
function DiagnosisReportSummary({
  variant,
  target,
  differentiator,
  revenueModel,
  coreSkill,
  cards,
  backPath,
  matchPath,
}: DiagnosisReportSummaryProps) {
  const navigate = useNavigate();
  const reportPath = backPath ?? (variant === "market" ? "/diagnosis/market-report" : "/diagnosis/tech-report");

  const handleBack = () => navigate(reportPath);
  const handleMatch = () => navigate(matchPath ?? "/matching");

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M16 5l-8 7 8 7" />
          </svg>
        </button>
        <span className={styles.brandName}>MULKKO REPORT</span>
        <img src={logo} alt="물꼬 로고" className={styles.logoMark} />
      </header>

      <div className={styles.subHeader}>이렇게 정리했어요</div>

      <div className={styles.scrollArea}>
        <div className={styles.summaryCard}>
          <div className={styles.summaryRow}>
            <span className={`${styles.summaryIcon} ${styles.summaryIconTarget}`}>◎</span>
            <span className={styles.summaryText}>
              <span className={styles.summaryLabel}>타깃</span>
              <span className={styles.summaryValue}>{target}</span>
            </span>
          </div>
          <div className={styles.summaryRow}>
            <span className={`${styles.summaryIcon} ${styles.summaryIconDifferentiator}`}>✦</span>
            <span className={styles.summaryText}>
              <span className={styles.summaryLabel}>차별점</span>
              <span className={styles.summaryValue}>{differentiator}</span>
            </span>
          </div>
          <div className={styles.summaryRow}>
            <span className={`${styles.summaryIcon} ${styles.summaryIconRevenue}`}>$</span>
            <span className={styles.summaryText}>
              <span className={styles.summaryLabel}>수익모델</span>
              <span className={styles.summaryValue}>{revenueModel}</span>
            </span>
          </div>
          <div className={styles.summaryRow}>
            <span className={`${styles.summaryIcon} ${styles.summaryIconSkill}`}>☉</span>
            <span className={styles.summaryText}>
              <span className={styles.summaryLabel}>보유역량</span>
              <span className={styles.summaryValue}>{coreSkill}</span>
            </span>
          </div>
        </div>

        <div className={styles.heading}>
          <h1 className={styles.headingTitle}>지금 방향도 좋아요.</h1>
          <p className={styles.headingDesc}>참고해볼 만한 아이디어를 몇 가지 추천드려요.</p>
          <p className={styles.headingAiNote}>✨ AI가 답변을 바탕으로 만든 참고 아이디어예요</p>
        </div>

        {cards.map((card, i) => {
          const tone = AXIS_TONE[card.axis] ?? "default";
          return (
            <div key={i} className={`${styles.ideaCard} ${IDEA_CARD_CLASS[tone]}`}>
              <span className={`${styles.ideaBadge} ${IDEA_BADGE_CLASS[tone]}`}>{card.axis}</span>
              <h2 className={styles.ideaTitle}>{card.title}</h2>
              <p className={styles.ideaDesc}>{card.description}</p>
            </div>
          );
        })}

        <p className={styles.caption}>참고용 아이디어예요 · 원래 계획은 그대로 유지해요</p>
      </div>

      <div className={styles.footer}>
        <button type="button" className={styles.prevButton} onClick={handleBack}>
          이전
        </button>
        <button type="button" className={styles.matchButton} onClick={handleMatch}>
          지원사업 매칭 보기 →
        </button>
      </div>
    </div>
  );
}

export default DiagnosisReportSummary;
