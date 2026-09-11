import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import { getDiagnosisAnswers, saveDiagnosisAnswers, type StoreType } from "./diagnosisAnswers";

/**
 * 사업구체화 진단 - 필수 질문 5/6 (Q5 · 매장 운영 형태). 슬롯: storeType.
 * 지역·규모(Q6)는 별도 화면(DiagnosisStep5)으로 분리돼 있다 — 매장형태 하나만 고르면
 * 바로 다음으로 넘어간다.
 */
function DiagnosisStep4() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [storeType, setStoreType] = useState<StoreType | null>(null);

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.origin || !answers.solutionApproach) {
      navigate("/diagnosis/select", { replace: true });
      return;
    }
    setStoreType(answers.storeType ?? null);
    setReady(true);
  }, [navigate]);

  const handleBack = () => navigate("/diagnosis/3");

  const handleNext = () => {
    if (storeType === null) return;
    saveDiagnosisAnswers({ storeType });
    navigate("/diagnosis/5");
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="83%" stepLabel="AI 제안 · 5/6" />
      <div className={styles.scrollArea}>
        <span className={styles.topicBadge}>Q5 · 매장 운영 형태</span>
        <h1 className={styles.questionTitle}>사업을 어떤 형태로 하시나요?</h1>
        <p className={styles.questionSub}>
          오프라인 매장 여부에 따라 분석 리포트 구성이 달라져요
        </p>
        <div className={styles.cardList} style={{ gap: 10 }}>
          {(
            [
              { value: "offline", title: "① 고객 방문형 오프라인 매장·공간", desc: "ex. 카페, 미용실, 학원" },
              { value: "booking", title: "② 예약 방문형 서비스 공간", desc: "ex. 공유스튜디오, 상담실" },
              { value: "delivery", title: "③ 배달·제조 중심, 고객 방문 없음", desc: "ex. 공장, 배달전문 주방" },
              { value: "online", title: "④ 온라인 판매·중개 플랫폼", desc: "ex. 쇼핑몰, 중고거래앱" },
              { value: "digital", title: "⑤ 앱·소프트웨어·디지털 서비스", desc: "ex. 구독 SaaS" },
            ] as { value: StoreType; title: string; desc: string }[]
          ).map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={styles.radioCard}
              style={{ padding: 15, borderRadius: "var(--radius-card)" }}
              onClick={() => setStoreType(opt.value)}
            >
              <span className={styles.radioCardHead} style={{ gap: 4 }}>
                <span className={styles.radioCardTitle} style={{ fontSize: 14 }}>{opt.title}</span>
                <span className={styles.radioCardDesc} style={{ fontSize: 11.5 }}>{opt.desc}</span>
              </span>
              <span className={styles.radioDot}>
                {storeType === opt.value && <span className={styles.radioDotOn} />}
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={handleBack}>
          이전
        </button>
        <button type="button" className={styles.nextButton} disabled={storeType === null} onClick={handleNext}>
          다음 →
        </button>
      </div>
    </div>
  );
}

export default DiagnosisStep4;
