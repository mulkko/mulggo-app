import { useState } from "react";
import styles from "../../styles/diagnosis.module.css";
import { MIN_ANSWER_LENGTH } from "./diagnosisAnswers";

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
 * 미달일 때 "다음/제출" 버튼을 눌러야 경고 문구가 뜨고 제출이 막힌다(2026-09-16, 사용자
 * 확인 - 예전엔 입력 중에 바로 경고가 떠서 타이핑을 방해했음). 선택 질문은 required=false로
 * 호출해 빈 값도 진행 허용.
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
  const [value, setValue] = useState(initialValue);
  const tooShort = required && value.trim().length < MIN_ANSWER_LENGTH;
  // [2026-09-16, 사용자 확인] 예전엔 입력하는 도중에도 tooShort면 바로 경고 문구가
  //떴는데(타이핑 중 방해된다는 피드백), 이제 "다음/제출" 버튼을 눌렀을 때만 검사해서
  // 부족하면 경고를 띄운다 - 버튼은 더 이상 disabled로 미리 막지 않고, 클릭 시점에
  // 판정한다. 한 번 경고가 뜬 뒤에는(submitAttempted) 글자 수가 채워지면 입력 중에도
  // 바로 사라지게 자연스럽게 재계산된다.
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const showLengthWarning = submitAttempted && tooShort;

  const handleSubmitClick = () => {
    if (tooShort) {
      setSubmitAttempted(true);
      return;
    }
    onSubmit(value.trim());
  };

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
        {showLengthWarning && (
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
          onClick={handleSubmitClick}
        >
          {buttonLabel}
          {!buttonLabel.startsWith("제출") && (
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
          )}
        </button>
      </div>
    </>
  );
}

export default DiagnosisTextQuestion;
