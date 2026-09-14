import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../../styles/diagnosis.module.css";
import DiagnosisHeader from "../DiagnosisHeader";
import {
  getDiagnosisAnswers,
  setDiagnosisReturnTo,
  type DiagnosisAnswers,
  type Origin,
  type StoreType,
} from "../diagnosisAnswers";

const ORIGIN_LABELS: Record<Origin, string> = {
  problem: "문제 해결형",
  opportunity: "기회 추구형",
};

const STORE_TYPE_LABELS: Record<StoreType, string> = {
  offline: "① 고객 방문형 오프라인 매장·공간",
  booking: "② 예약 방문형 서비스 공간",
  delivery: "③ 배달·제조 중심, 고객 방문 없음",
  online: "④ 온라인 판매·중개 플랫폼",
  digital: "⑤ 앱·소프트웨어·디지털 서비스",
};

interface ConfirmCard {
  label: string;
  value: string;
  path: string;
}

function buildCards(answers: DiagnosisAnswers): ConfirmCard[] {
  const region = [answers.sido, answers.sigungu, answers.dong].filter(Boolean).join(" ");
  return [
    { label: "Q1 · 사업 아이템", value: answers.seedInterest || "-", path: "/diagnosis/1" },
    { label: "Q2 · 출발점", value: answers.origin ? ORIGIN_LABELS[answers.origin] : "-", path: "/diagnosis/select" },
    { label: "Q3 · 문제 정의", value: answers.problemToSolve || "-", path: "/diagnosis/3" },
    { label: "Q4 · 해결 방식", value: answers.solutionApproach || "-", path: "/diagnosis/4" },
    {
      label: "Q5 · 매장 운영 형태",
      value: answers.storeType ? STORE_TYPE_LABELS[answers.storeType] : "-",
      path: "/diagnosis/5",
    },
    { label: "Q6 · 지역·규모", value: region || "-", path: "/diagnosis/6" },
  ];
}

/**
 * 11. PSST 확정 (Q1~Q6만). Q6(지역·규모) 다음, 12(업종코드 매칭) 이전에 끼는 리캡 화면.
 * 프로토타입엔 카드별 인라인 편집 UI(드롭다운/즉시수정)가 있지만, 여기선 카드를 누르면
 * 해당 Q 화면으로 돌아가 수정 후 다시 이 화면으로 오는 방식으로 단순화했다 -
 * consumeDiagnosisReturnTo()(각 Step의 제출 핸들러에서 소비)가 그 "돌아올 곳"을 기억한다.
 */
function DiagnosisPsstConfirm() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [cards, setCards] = useState<ConfirmCard[]>([]);

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.sido || !answers.sigungu || !answers.dong) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }
    setCards(buildCards(answers));
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/6");
  const handleNext = () => navigate("/diagnosis/industry-code");

  const editCard = (path: string) => {
    setDiagnosisReturnTo("/diagnosis/psst-confirm");
    navigate(path);
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="100%" stepLabel="PSST 확정" />
      <div className={styles.scrollArea}>
        <h1 className={styles.questionTitle}>이렇게 정리했어요, 확인해주세요</h1>
        <p className={styles.questionSub}>채워진 항목을 눌러서 언제든 수정할 수 있어요</p>
        <div className={styles.cardList}>
          {cards.map((card) => (
            <button key={card.label} type="button" className={styles.confirmCard} onClick={() => editCard(card.path)}>
              <span className={styles.confirmCardLabel}>{card.label}</span>
              <span className={styles.confirmCardValue}>{card.value}</span>
            </button>
          ))}
        </div>
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={handleBack}>
          이전
        </button>
        <button type="button" className={styles.nextButton} onClick={handleNext}>
          확정 →
        </button>
      </div>
    </div>
  );
}

export default DiagnosisPsstConfirm;
