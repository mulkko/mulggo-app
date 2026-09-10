import { useState } from "react";
import styles from "../../styles/diagnosis.module.css";
import { MIN_ANSWER_LENGTH } from "./diagnosisAnswers";

interface DiagnosisTextQuestionProps {
  title: string;
  sub?: string;
  initialValue?: string;
  buttonLabel?: string;
  onSubmit: (value: string) => void;
}

/**
 * 진단 화면(구체화 진단1~3)이 공유하는 "자유서술 질문 1개 + 다음 버튼" 폼.
 * 최소 글자수(10자, idea_card_generator.MIN_SLOT_LENGTH와 동일 기준) 미만이면 버튼 비활성.
 */
function DiagnosisTextQuestion({
  title,
  sub,
  initialValue = "",
  buttonLabel = "다음",
  onSubmit,
}: DiagnosisTextQuestionProps) {
  const [value, setValue] = useState(initialValue);
  const tooShort = value.trim().length < MIN_ANSWER_LENGTH;

  return (
    <>
      <div className={styles.scrollArea}>
        <h1 className={styles.questionTitle}>{title}</h1>
        {sub && <p className={styles.questionSub}>{sub}</p>}
        <textarea
          className={styles.textarea}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="편하게 적어주세요"
        />
        {value.length > 0 && tooShort && (
          <p className={styles.lengthWarning}>{MIN_ANSWER_LENGTH}글자 이상 입력해주세요.</p>
        )}
      </div>
      <div className={styles.footer}>
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
