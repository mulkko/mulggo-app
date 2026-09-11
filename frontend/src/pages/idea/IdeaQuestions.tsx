import { useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/ideaQuestions.module.css";

/**
 * 사업구체화 질문 화면 (`/idea/questions`).
 *
 * 프로토타입 라벨 "06~10-4" (내부 키 is.q + qMeta). 원래는 질문 9개가 이어지는
 * 화면이지만, 이번 라운드에서는 kind가 전부 "text"이고 참고문구도 없는 가장 단순한
 * 4개(q0/q2/q3/q8)만 구현한다. 07/09-1/10/10-1~10-3(선택지형·지역선택형·참고문구형
 * UI 필요)은 다음 라운드.
 *
 * Onboarding.tsx와 동일한 패턴 — 라우트 하나 + 로컬 stepIndex state로 콘텐츠만
 * 전환한다(URL은 안 바뀜). QUESTIONS 배열 순서는 이번 라운드에 한해 이 4개만 잇는
 * 임시 체인이라, pct/stepLabel이 25%→60%→67%→92%로 건너뛰는 게 정상 동작이다
 * (최종 9단계 기준 값을 그대로 쓴 것 — 07/09-1/10/10-1~10-3이 채워지면 자연스럽게 이어짐).
 *
 * 백엔드 연동 없음. 값(색상/radius/shadow)은 webTokens.css 토큰만 사용한다.
 */

type Question = {
  key: string;
  pct: string;
  stepLabel: string;
  badge: string;
  title: string;
  sub: string;
  placeholder: string;
};

const QUESTIONS: Question[] = [
  {
    key: "q0",
    pct: "25%",
    stepLabel: "AI 제안 · 1/6",
    badge: "Q1 · 사업 아이템 구상",
    title: "구상하고 계신 사업 아이템이나 아이디어를 편하게 적어주세요",
    sub: "이미 구체적인 아이템이어도, 아직 막연한 관심사·문제의식이어도 괜찮아요",
    placeholder: "예: 반려동물 이동장 대여 서비스, 병원비 가격 비교 앱, 커피에 관심 많음...",
  },
  {
    key: "q2",
    pct: "60%",
    stepLabel: "AI 제안 · 3/6",
    badge: "Q3 · 문제 정의",
    title: "고객이 겪는 문제는 구체적으로 무엇인가요?",
    sub: "이 아이템이 해결하려는 핵심 문제를 적어주세요",
    placeholder: "예: 정기검진 비용 부담, 병원마다 다른 진료비",
  },
  {
    key: "q3",
    pct: "67%",
    stepLabel: "AI 제안 · 4/6",
    badge: "Q4 · 해결 방식",
    title: "이 문제를 어떤 서비스·제품으로 해결하실 건가요?",
    sub: "앱, 플랫폼, 오프라인 매장 등 구체적인 형태로 적어주세요",
    placeholder: "앱으로 가격 비교·예약 기능",
  },
  {
    key: "q8",
    pct: "92%",
    stepLabel: "선택 질문 · 4/4",
    badge: "Q10 · 보유역량",
    title: "이 문제를 해결할 수 있는 본인만의 강점·경험이 있으신가요?",
    sub: "자격증, 경력, 네트워크 등 구체적으로 작성해주세요",
    placeholder: "예: 바리스타 자격증, 요식업 경력",
  },
];

function IdeaQuestions() {
  const navigate = useNavigate();
  const [stepIndex, setStepIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const current = QUESTIONS[stepIndex];

  const handleAnswerChange = (value: string) => {
    setAnswers((prev) => ({ ...prev, [current.key]: value }));
  };

  const handlePrev = () => {
    if (stepIndex > 0) {
      setStepIndex((prev) => prev - 1);
    } else {
      // 프로토타입 원본 값 그대로 — 05-1(IdeaChoice)을 거치게 할지는 팀 결정 필요, 이번엔 건드리지 않음
      navigate("/home");
    }
  };

  const handleNext = () => {
    if (stepIndex < QUESTIONS.length - 1) {
      setStepIndex((prev) => prev + 1);
      return;
    }
    // TODO: 마지막 질문(q8) 이후 다음 화면(07/PSST 정리/업종코드 매칭) 아직 없음
  };

  return (
    <div className={`pageContainer ${styles.page}`}>
      <header className={styles.header}>
        <button
          type="button"
          className={styles.backButton}
          onClick={handlePrev}
          aria-label="뒤로가기"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" aria-hidden="true">
            <path d="M16 5l-8 7 8 7" />
          </svg>
        </button>
        <div className={styles.progressTrack}>
          <div className={styles.progressFill} style={{ width: current.pct }} />
        </div>
        <span className={styles.stepBadge}>{current.stepLabel}</span>
      </header>

      <main className={styles.body}>
        <span className={styles.topicBadge}>{current.badge}</span>
        <h1 className={styles.title}>{current.title}</h1>
        <p className={styles.sub}>{current.sub}</p>
        <textarea
          className={styles.textarea}
          value={answers[current.key] ?? ""}
          onChange={(e) => handleAnswerChange(e.target.value)}
          placeholder={current.placeholder}
        />
      </main>

      <footer className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={handlePrev}>
          이전
        </button>
        <button type="button" className={styles.nextButton} onClick={handleNext}>
          다음 →
        </button>
      </footer>
    </div>
  );
}

export default IdeaQuestions;
