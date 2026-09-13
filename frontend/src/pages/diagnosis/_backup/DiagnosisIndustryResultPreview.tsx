import { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../../styles/diagnosis.module.css";
import industryStyles from "../../../styles/diagnosisIndustryCode.module.css";

const MOCK_CODES = ["56221", "10891"];
const MOCK_INDUSTRY_NAME = "커피 전문점";
const MOCK_CONFIDENCE = "high";

/**
 * [디자인 검토용, 라이브 미적용] "업종코드를 찾았어요" 화면을 프로토타입(260911_Mulkko
 * Prototype) 실측값대로 다시 만든 미리보기 - 2026-09-13 조사로 확인한 사실:
 *
 * 지금 라이브 화면(DiagnosisIndustryResult.tsx)과 emkim99님 원본(DiagnosisIndustryCode.tsx)
 * 둘 다 이 화면 전용 디자인 대신 Q2/Q5가 쓰는 공용 라디오카드(.radioCard, padding 17px·
 * radius 14px·inset 테두리)와 Q7~9가 쓰는 공용 안내박스(.qAnchor, 옅은 네이비 틴트 배경)를
 * 재사용하고 있었다 - 이건 emkim99님 원본 구현 때부터 이미 그랬던 것(사용자 확인, 백엔드
 * 통합 과정에서 망가진 게 아님).
 *
 * 프로토타입 실측값은 달랐다: 카드는 padding 20px·radius 16px에 테두리 없이 은은하게
 * 퍼지는 그림자(box-shadow, --shadow-industry-card로 새로 등록)만 있고, 안내박스는
 * 연한 파란 배경(--color-industry-anchor-bg, #F3F8FF)을 쓴다. 이 미리보기가 그 실측값을
 * 그대로 반영한 버전 - 라디오 동그라미(.radioDot/.radioDotOn)는 diagnosis.module.css 것을
 * 그대로 재사용(이건 프로토타입과 이미 일치 확인됨). 검토 후 괜찮으면
 * DiagnosisIndustryResult.tsx에 반영하기로 결정.
 */
function DiagnosisIndustryResultPreview() {
  const navigate = useNavigate();
  const [selectedCode, setSelectedCode] = useState(MOCK_CODES[0]);

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* [2026-09-13, 사용자 확인] 이 미리보기 페이지에선 상단 진행바/단계 라벨이
          필요 없어서 주석 처리 - 나중에 필요해지면 DiagnosisHeader.tsx 참고해서
          되살릴 것. 뒤로가기 버튼만 남김. */}
      <header className={styles.header}>
        <button type="button" className={styles.backButton} onClick={() => navigate("/home")} aria-label="뒤로가기">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M16 5l-8 7 8 7" />
          </svg>
        </button>
        {/* <div className={styles.progressTrack}>
          <div className={styles.progressFill} style={{ width: "100%" }} />
        </div>
        <span className={styles.stepBadge}>AI 제안 · 업종코드 매칭 [PREVIEW]</span> */}
      </header>
      <div className={styles.scrollArea}>
        <h1 className={industryStyles.title}>업종코드를 찾았어요</h1>

        <div className={industryStyles.anchorBox}>
          <span className={industryStyles.anchorText}>
            방금 답변하신 문제인식·해결방식 등 PSST 내용을 물꼬가 종합해서, 가장 가까운 업종코드를 아래처럼 찾아드렸어요.
          </span>
        </div>
        <p className={industryStyles.disclaimer}>이건 참고용 추천이며, 최종 등록 시 세무 전문가 확인을 권장합니다.</p>

        <div className={styles.cardList}>
          {MOCK_CODES.map((code) => (
            <button
              key={code}
              type="button"
              className={industryStyles.matchCard}
              onClick={() => setSelectedCode(code)}
            >
              <span className={industryStyles.matchCardHead}>
                <span className={industryStyles.matchCardTitle}>{MOCK_INDUSTRY_NAME}</span>
                <span className={styles.radioDot}>
                  {selectedCode === code && <span className={styles.radioDotOn} />}
                </span>
              </span>
              <span className={industryStyles.matchCodeText}>
                업종코드 {code}
                {code === MOCK_CODES[0] ? ` · 신뢰도 ${MOCK_CONFIDENCE}` : ""}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={() => navigate("/home")}>
          이전
        </button>
        <button type="button" className={styles.nextButton} onClick={() => navigate("/home")}>
          분석 리포트 보러가기 →
        </button>
      </div>
    </div>
  );
}

export default DiagnosisIndustryResultPreview;
