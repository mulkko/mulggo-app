import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import industryStyles from "../../styles/diagnosisIndustryCode.module.css";
import DiagnosisHeader from "./DiagnosisHeader";

const MOCK_CODES = ["56221", "10891"];
const MOCK_INDUSTRY_NAME = "커피 전문점";
const MOCK_CONFIDENCE = "high";

/**
 * [개인 디자인 확인용, 원본 DiagnosisIndustryResult.tsx의 격리 사본] 세션/백엔드
 * 폴링(POST /select-industry, GET /report) 없이 업종코드 카드 목업으로 바로 확인
 * (2026-09-13, 사용자 확인 - 나머지 _test 사본과 동일 패턴). "분석 리포트 보러가기"
 * 버튼은 여기선 그냥 /home으로 - 실제 폴링 동작은 라이브 화면에서만 확인.
 */
function DiagnosisIndustryResult_test() {
  const navigate = useNavigate();

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={() => navigate("/home")} pct="100%" stepLabel="AI 제안 · 업종코드 매칭 [TEST]" />
      <div className={styles.scrollArea}>
        <h1 className={industryStyles.title}>업종코드를 찾았어요</h1>
        <div className={styles.qAnchor}>
          <span className={styles.qAnchorText}>
            방금 답변하신 문제인식·해결방식 등 PSST 내용을 물꼬가 종합해서, 가장 가까운 업종코드를 아래처럼 찾아드렸어요.
          </span>
        </div>
        <p className={industryStyles.disclaimer}>이건 참고용 추천이며, 최종 등록 시 세무 전문가 확인을 권장합니다.</p>

        <div className={styles.cardList}>
          {MOCK_CODES.map((code, i) => (
            <div key={code} className={styles.resultCard}>
              <span className={styles.resultAxis}>{i === 0 ? "1순위" : `대안 ${i}`}</span>
              <span className={styles.resultTitle}>🏷 {MOCK_INDUSTRY_NAME}</span>
              <span className={styles.resultDesc}>
                업종코드 {code}
                {i === 0 ? ` · 신뢰도 ${MOCK_CONFIDENCE}` : ""}
              </span>
            </div>
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

export default DiagnosisIndustryResult_test;
