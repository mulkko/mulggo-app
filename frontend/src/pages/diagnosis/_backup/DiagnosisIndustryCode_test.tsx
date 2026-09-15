import { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../../styles/diagnosisIndustryCode.module.css";
import diagnosisStyles from "../../../styles/diagnosis.module.css";

/**
 * [개인 테스트용, 원본 DiagnosisIndustryCode.tsx의 격리 사본] sessionStorage 의존과
 * 실제 백엔드 호출(POST /api/industry-code) 둘 다 없이 목업 데이터로 바로 렌더링만
 * 확인하는 페이지. 정식 흐름과 완전히 분리돼 있어서 주소창에 바로 쳐서 들어가도
 * 리다이렉트 안 됨(2026-09-12, 사용자 확인 - DiagnosisAnswerSummary_test.tsx와 동일 패턴).
 */
const MOCK_PRIMARY = { code: "56221", name: "커피전문점" };
const MOCK_ALTERNATIVES = [
  { code: "56191", name: "생과일주스 전문점" },
  { code: "56220", name: "제과점업" },
];
const MOCK_STATE = "추천";
const MOCK_QUESTION = "";

function DiagnosisIndustryCode_test() {
  const navigate = useNavigate();
  const [selectedCode, setSelectedCode] = useState(MOCK_PRIMARY.code);

  const codeOptions = [MOCK_PRIMARY, ...MOCK_ALTERNATIVES];

  const handleBack = () => navigate("/home");
  const handleNext = () => {};

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <button type="button" className={styles.backButton} onClick={handleBack} aria-label="뒤로가기">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M16 5l-8 7 8 7" />
          </svg>
        </button>
        <span className={styles.resultLabel}>매칭 결과 [TEST]</span>
      </header>

      <div className={styles.scrollArea}>
        <h1 className={styles.title}>업종코드를 찾았어요</h1>
        <div className={diagnosisStyles.qAnchor}>
          <span className={diagnosisStyles.qAnchorText}>
            방금 답변하신 문제인식·해결방식 등 PSST 내용을 물꼬가 종합해서, 가장 가까운 업종코드를 아래처럼 찾아드렸어요.
          </span>
        </div>
        <p className={styles.disclaimer}></p>

        {MOCK_STATE !== "추천" && MOCK_QUESTION && <div className={styles.stateBanner}>{MOCK_QUESTION}</div>}

        <div className={diagnosisStyles.cardList}>
          {codeOptions.map((opt) => (
            <button
              key={opt.code}
              type="button"
              className={diagnosisStyles.radioCard}
              onClick={() => setSelectedCode(opt.code)}
            >
              <span className={diagnosisStyles.radioCardHead}>
                <span className={diagnosisStyles.radioCardTitle}>{opt.name}</span>
                <span className={styles.codeMeta}>업종코드 {opt.code}</span>
              </span>
              <span className={diagnosisStyles.radioDot}>
                {selectedCode === opt.code && <span className={diagnosisStyles.radioDotOn} />}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className={diagnosisStyles.bottom}>
        <button type="button" className={diagnosisStyles.prevButton} onClick={handleBack}>
          홈으로
        </button>
        <button type="button" className={diagnosisStyles.nextButton} onClick={handleNext}>
          분석 리포트 보러가기 →
        </button>
      </div>
    </div>
  );
}

export default DiagnosisIndustryCode_test;
