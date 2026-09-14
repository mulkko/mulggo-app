import { useEffect, useState } from "react";
import styles from "../../styles/diagnosis.module.css";
import { MIN_ANSWER_LENGTH } from "./diagnosisAnswers";

// [2026-09-14, 임시 - 시연 영상 촬영용, 사용자 확인] 데모 계정으로 미리 채워둔 답변을
// 실제 타이핑처럼 한 글자씩 보여주는 기능. /dev/diagnosis-precise-demo-test(테스트
// 전용 진입 페이지)에서만 이 sessionStorage 플래그를 켠다 - 일반 사용자·실제 서비스
// 흐름은 이 키가 항상 비어있어서 100% 예전과 동일하게 동작한다. 확인 끝나면 이
// 상수 + 아래 useEffect 블록만 지우면 통째로 원복된다.
export const DEMO_TYPING_KEY = "mulkko_diagnosis_demo_typing";

interface DiagnosisTextQuestionProps {
  topicBadge: string;
  title: string;
  sub?: string;
  anchor?: string;
  placeholder?: string;
  initialValue?: string;
  buttonLabel?: string;
  required?: boolean;
  onBack: () => void;
  backLabel?: string;
  onSubmit: (value: string) => void;
  error?: string;
}

/**
 * 진단 화면(구체화 진단1~3, 선택 질문 1~4)이 공유하는 "자유서술 질문 1개 + 이전/다음 버튼" 폼.
 * required(기본 true)면 최소 글자수(10자, idea_card_generator.MIN_SLOT_LENGTH와 동일 기준)
 * 미만일 때 다음 버튼을 비활성화한다. 선택 질문은 required=false로 호출해 빈 값도 진행 허용.
 */
function DiagnosisTextQuestion({
  topicBadge,
  title,
  sub,
  anchor,
  placeholder = "편하게 적어주세요",
  initialValue = "",
  buttonLabel = "다음",
  required = true,
  onBack,
  backLabel = "이전",
  onSubmit,
  error,
}: DiagnosisTextQuestionProps) {
  // 데모 타이핑 모드면 시작값을 비워둔다 - 아래 useEffect가 initialValue를 한
  // 글자씩 채워넣는 걸 보여줘야 하는데, 처음부터 다 차있으면 애니메이션이 의미 없음.
  const demoTyping =
    typeof window !== "undefined" && sessionStorage.getItem(DEMO_TYPING_KEY) === "1" && !!initialValue;
  const [value, setValue] = useState(demoTyping ? "" : initialValue);
  const tooShort = required && value.trim().length < MIN_ANSWER_LENGTH;

  useEffect(() => {
    if (!demoTyping) return;
    let i = 0;
    const timer = setInterval(() => {
      i += 1;
      setValue(initialValue.slice(0, i));
      if (i >= initialValue.length) clearInterval(timer);
    }, 35);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <div className={styles.scrollArea}>
        <span className={styles.topicBadge}>{topicBadge}</span>
        <h1 className={styles.questionTitle}>{title}</h1>
        {sub && <p className={styles.questionSub}>{sub}</p>}
        {anchor && (
          <div className={styles.qAnchor}>
            <svg
              className={styles.qAnchorIcon}
              viewBox="0 0 24 24"
              fill="none"
              stroke="#15328C"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8" />
            </svg>
            <span className={styles.qAnchorText}>{anchor}</span>
          </div>
        )}
        <textarea
          className={styles.textarea}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
        />
        {value.length > 0 && tooShort && (
          <p className={styles.lengthWarning}>{MIN_ANSWER_LENGTH}글자 이상 입력해주세요.</p>
        )}
        {error && <p className={styles.errorText}>{error}</p>}
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={onBack}>
          {backLabel}
        </button>
        <button
          type="button"
          className={styles.nextButton}
          disabled={tooShort}
          onClick={() => onSubmit(value.trim())}
        >
          {buttonLabel}
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
    </>
  );
}

export default DiagnosisTextQuestion;
