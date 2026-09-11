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
  const [value, setValue] = useState(initialValue);
  const tooShort = required && value.trim().length < MIN_ANSWER_LENGTH;

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
        </button>
      </div>
    </>
  );
}

export default DiagnosisTextQuestion;
