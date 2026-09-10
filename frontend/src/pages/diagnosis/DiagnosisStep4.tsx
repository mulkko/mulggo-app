import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import SelectSheet from "../../components/SelectSheet/SelectSheet";
import { clearDiagnosisAnswers, getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface RegionRow {
  sido: string;
  sigungu: string | null;
  dong_name: string | null;
  level: "시도" | "시군구" | "행정동";
}

const toSelectSheetOptions = (values: string[]) => values.map((v) => ({ label: v, value: v }));

interface IdeaCard {
  axis: string;
  title: string;
  description: string;
}

interface SlotFillingResponse {
  success: boolean;
  cards: IdeaCard[] | null;
  weak_slots: string[] | null;
  error: string | null;
  // ksic/report_type도 응답에 있지만 업종분류 쪽을 팀에서 별도로 다시 만들고 있어서
  // (사용자 확인, 2026-09-10) 이 화면에서는 안 쓴다 - 완성되면 여기서 마저 연결.
}

/**
 * 사업구체화 진단 5/5 — "구체화 진단4" (dev_links.html 목업 이름).
 * 슬롯 4(매장운영여부, 버튼선택) + 슬롯 14(지역·규모, 시/도·시군구·동)를 한 화면에서
 * 받고, POST /api/test/slot-filling로 지금까지의 답변을 한 번에 제출한다
 * (backend/api/idea_card_test.py — DB 저장 없는 테스트 전용 엔드포인트, 정식
 * 엔드포인트로 바뀌면 이 fetch 경로만 교체하면 됨).
 */
function DiagnosisStep4() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [hasStore, setHasStore] = useState<boolean | null>(null);
  const [sido, setSido] = useState("");
  const [sigungu, setSigungu] = useState("");
  const [dong, setDong] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SlotFillingResponse | null>(null);

  // [2026-09-10] 지역 3단을 자유입력 대신 administrative_dong 기반 캐스케이딩
  // 셀렉트박스로 바꿈 - GET /analysis/regions(3,924행, 작아서 한 번에 다 받음)를
  // 받아서 프론트에서 시/도 → 시/군/구 → 행정동 계층으로 걸러 쓴다.
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [regionsError, setRegionsError] = useState(false);

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.origin || !answers.solutionApproach) {
      navigate("/diagnosis/select", { replace: true });
      return;
    }
    setHasStore(answers.hasStore ?? null);
    setSido(answers.sido ?? "");
    setSigungu(answers.sigungu ?? "");
    setDong(answers.dong ?? "");
    setReady(true);
  }, [navigate]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/analysis/regions`)
      .then((res) => res.json())
      .then((body: { success: boolean; data?: RegionRow[] }) => {
        if (body.success && body.data) setRegions(body.data);
        else setRegionsError(true);
      })
      .catch(() => setRegionsError(true));
  }, []);

  const sidoOptions = toSelectSheetOptions(
    regions.filter((r) => r.level === "시도").map((r) => r.dong_name ?? r.sido),
  );
  const sigunguOptions = toSelectSheetOptions(
    regions.filter((r) => r.level === "시군구" && r.sido === sido).map((r) => r.dong_name ?? ""),
  );
  const dongOptions = toSelectSheetOptions(
    regions
      .filter((r) => r.level === "행정동" && r.sido === sido && r.sigungu === sigungu)
      .map((r) => r.dong_name ?? ""),
  );

  const handleSidoChange = (value: string) => {
    setSido(value);
    setSigungu("");
    setDong("");
  };

  const handleSigunguChange = (value: string) => {
    setSigungu(value);
    setDong("");
  };

  const handleBack = () => navigate("/diagnosis/3");
  const handleFinish = () => navigate("/home");

  const canSubmit = hasStore !== null && sido.trim() !== "" && sigungu.trim() !== "" && dong.trim() !== "";

  const handleSubmit = async () => {
    if (hasStore === null || !canSubmit) return;
    const answers = saveDiagnosisAnswers({ hasStore, sido, sigungu, dong });

    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE_URL}/api/test/slot-filling`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          seed_interest: answers.seedInterest || "",
          problem_to_solve: answers.problemToSolve || "",
          solution_approach: answers.solutionApproach || "",
          has_store: hasStore,
          sido,
          sigungu,
          dong,
          // 타깃/차별점/수익모델/보유역량(선택 슬롯)은 이 5화면 플로우에서 안 받음 - 빈 값.
          target: "",
          differentiator: "",
          revenue_model: "",
          core_skill: "",
        }),
      });
      const data: SlotFillingResponse = await res.json();
      if (!data.success) {
        setError(data.error || "제출에 실패했어요.");
        return;
      }
      setResult(data);
      clearDiagnosisAnswers();
    } catch {
      setError("서버에 연결할 수 없습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!ready) return null;

  if (result) {
    return (
      <div className={`pageContainer ${styles.page}`}>
        <DiagnosisHeader onBack={handleFinish} stepLabel="4 / 4" />
        <div className={styles.scrollArea}>
          <h1 className={styles.questionTitle}>사업 구체화가 끝났어요!</h1>
          <p className={styles.noticeText}>
            업종코드 매칭·분석 리포트 연결은 준비 중이에요. 지금까지 답변을 바탕으로 한
            아이디어를 먼저 보여드릴게요.
          </p>

          {result.weak_slots && result.weak_slots.length > 0 && (
            <p className={styles.noticeText}>
              답변이 짧아 근거로 못 쓴 항목: {result.weak_slots.join(", ")}
            </p>
          )}

          {result.cards && result.cards.length > 0 ? (
            result.cards.map((card) => (
              <div key={card.title} className={styles.resultCard}>
                <span className={styles.resultAxis}>{card.axis}</span>
                <span className={styles.resultTitle}>{card.title}</span>
                <span className={styles.resultDesc}>{card.description}</span>
              </div>
            ))
          ) : (
            <p className={styles.noticeText}>아이디어 카드는 생성되지 않았어요.</p>
          )}
        </div>
        <div className={styles.footer}>
          <button type="button" className={styles.nextButton} onClick={handleFinish}>
            홈으로
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} stepLabel="4 / 4" />
      <div className={styles.scrollArea}>
        <h1 className={styles.questionTitle}>
          고객이 직접 방문하는 매장이나 공간을 운영하시나요?
        </h1>
        <p className={styles.questionSub}>
          예: 카페, 식당, 매장, 학원처럼 손님이 찾아오는 공간이 있다면 &quot;예&quot;
        </p>
        <div className={styles.cardList}>
          <button
            type="button"
            className={`${styles.choiceCard} ${hasStore === true ? styles.choiceCardSelected : ""}`}
            onClick={() => setHasStore(true)}
          >
            <span className={styles.choiceCardTitle}>예</span>
          </button>
          <button
            type="button"
            className={`${styles.choiceCard} ${hasStore === false ? styles.choiceCardSelected : ""}`}
            onClick={() => setHasStore(false)}
          >
            <span className={styles.choiceCardTitle}>아니오</span>
          </button>
        </div>

        <h1 className={styles.questionTitle}>어디서, 어느 정도 규모로 시작하실 계획인가요?</h1>
        <p className={styles.questionSub}>시/도 → 시/군/구 → 행정동 순서로 선택해주세요.</p>
        <div className={styles.regionGroup}>
          <SelectSheet
            label="시/도"
            name="sido"
            value={sido}
            options={sidoOptions}
            onChange={handleSidoChange}
            placeholder="시/도 선택"
            disabled={sidoOptions.length === 0}
          />
          <SelectSheet
            label="시/군/구"
            name="sigungu"
            value={sigungu}
            options={sigunguOptions}
            onChange={handleSigunguChange}
            placeholder="시/군/구 선택"
            disabled={!sido}
          />
          <SelectSheet
            label="행정동"
            name="dong"
            value={dong}
            options={dongOptions}
            onChange={setDong}
            placeholder="행정동 선택"
            disabled={!sigungu}
          />
        </div>
        {regionsError && (
          <p className={styles.errorText}>지역 목록을 불러오지 못했어요. 새로고침해주세요.</p>
        )}

        {error && <p className={styles.errorText}>{error}</p>}
      </div>
      <div className={styles.footer}>
        <button
          type="button"
          className={styles.nextButton}
          disabled={!canSubmit || submitting}
          onClick={handleSubmit}
        >
          {submitting ? "제출 중..." : "제출하기"}
        </button>
      </div>
    </div>
  );
}

export default DiagnosisStep4;
