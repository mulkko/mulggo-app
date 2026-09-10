import { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/onboarding.module.css";

/**
 * 온보딩 화면 (`/onboarding`).
 *
 * 회원가입 완료 직후 진입한다. step(0~3) 로컬 state 하나로
 * 본문(마스코트 + 카피)과 하단 페이지 인디케이터 / CTA 전환을 모두 처리한다.
 * 백엔드 / URL 파라미터 연동 없음.
 *
 * - step 0: 가입 완료 인사
 * - step 1: 사업 구체화 소개
 * - step 2: 맞춤 분석 소개
 * - step 3: 시작 방식 선택 (카드 2개) — 하단 영역(인디케이터 + CTA) 없음
 *
 * 스펙 출처: 프로토타입 "is.onboard". 하단 네비게이션(BottomNav) 없음.
 * 값(색상/radius/shadow)은 webTokens.css 토큰만 사용한다.
 */

type Step = 0 | 1 | 2 | 3;

type StepContent = {
  badge?: string;
  title: string; // <br> 포함 — 줄바꿈 위치가 디자인 스펙
  desc?: string;
};

/** step 0~2 본문 카피 — 프로토타입 값 그대로. 이름은 더미데이터 일관성 위해 "김창업". */
const STEP_CONTENT: Record<0 | 1 | 2, StepContent> = {
  0: {
    title: "김창업 님,<br>가입이 완료되었습니다",
  },
  1: {
    badge: "STEP 1 · 사업 구체화",
    title: "막연한 생각도<br>질문에 답하면 사업이 돼요",
    desc: "물꼬 AI가 아이템·문제·해결방식을 차례로 물어보고 PSST 형식으로 정리해 드려요.",
  },
  2: {
    badge: "STEP 2 · 맞춤 분석",
    title: "업종코드를 찾아<br>상권·기술창업 분석까지",
    desc: "정리된 내용으로 업종코드를 판정해 상권형 또는 기술창업형 리포트로 이어드려요.",
  },
};

const TOTAL_STEPS = 4;

/** 마스코트 원 — 모든 step 공통. 안쪽은 임시 placeholder 도형. */
function Mascot() {
  return (
    <div className={styles.mascot} aria-hidden="true">
      <div className={styles.mascotInner} />
    </div>
  );
}

function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(0);

  const handleBack = () => {
    // step 0에서만 노출 — 회원가입 화면으로 복귀 (이미 있는 라우트)
    navigate("/signup");
  };

  const handleSkip = () => {
    navigate("/home");
  };

  const handleNext = () => {
    setStep((prev) => (prev < 3 ? ((prev + 1) as Step) : prev));
  };

  const handleIdeaCard = () => {
    navigate("/idea/choice");
  };

  const handleMatchingCard = () => {
    navigate("/matching");
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* 상단바: 뒤로가기(step 0만) + 건너뛰기(step 0~2) */}
      <header className={styles.topbar}>
        {step === 0 ? (
          <button
            type="button"
            className={styles.backButton}
            onClick={handleBack}
            aria-label="뒤로가기"
          >
            ←
          </button>
        ) : (
          <span />
        )}
        {step !== 3 && (
          <button type="button" className={styles.skipButton} onClick={handleSkip}>
            건너뛰기
          </button>
        )}
      </header>

      {/* 중앙 콘텐츠 */}
      <main className={styles.content}>
        {step === 3 ? (
          <>
            <Mascot />
            <div className={styles.startHeading}>
              <h1 className={styles.startTitle}>
                이제 물꼬를 시작해볼
                <br />
                준비가 되셔나요?
              </h1>
              <p className={styles.startSubtitle}>무엇부터 해보고 싶은지 알려주세요.</p>
            </div>
            <div className={styles.cardList}>
              <button type="button" className={styles.choiceCard} onClick={handleIdeaCard}>
                <span className={styles.choiceCardTitle}>사업 아이디어를 구상하고 싶어요</span>
                <span className={styles.choiceCardDesc}>
                  짧은 질문 혹은 정밀 질문에 답하며 사업을 구체화해요
                </span>
              </button>
              <button type="button" className={styles.choiceCard} onClick={handleMatchingCard}>
                <span className={styles.choiceCardTitle}>바로 지원사업 매칭을 받아보고 싶어요</span>
                <span className={styles.choiceCardDesc}>
                  이미 사업 정보가 있다면 바로 지원사업을 확인해요
                </span>
              </button>
            </div>
          </>
        ) : (
          <>
            <Mascot />
            {STEP_CONTENT[step].badge && (
              <span className={styles.badge}>{STEP_CONTENT[step].badge}</span>
            )}
            <h1
              className={styles.title}
              dangerouslySetInnerHTML={{ __html: STEP_CONTENT[step].title }}
            />
            {STEP_CONTENT[step].desc && (
              <p className={styles.desc}>{STEP_CONTENT[step].desc}</p>
            )}
          </>
        )}
      </main>

      {/* 하단 영역: step 0~2만 */}
      {step !== 3 && (
        <footer className={styles.bottom}>
          <div className={styles.dots} role="presentation">
            {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
              <span
                key={i}
                className={`${styles.dot} ${i === step ? styles.dotActive : ""}`}
              />
            ))}
          </div>
          <button type="button" className={styles.cta} onClick={handleNext}>
            다음
          </button>
        </footer>
      )}
    </div>
  );
}

export default Onboarding;
