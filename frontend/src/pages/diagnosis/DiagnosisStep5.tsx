import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import SelectSheet from "../../components/SelectSheet/SelectSheet";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface RegionRow {
  sido: string;
  sigungu: string | null;
  dong_name: string | null;
  level: "시도" | "시군구" | "행정동";
}

const toSelectSheetOptions = (values: string[]) => values.map((v) => ({ label: v, value: v }));

/**
 * 사업구체화 진단 - 필수 질문 6/6 (Q6 · 지역·규모, 필수질문 구간의 마지막). 슬롯: sido/sigungu/dong.
 * 이 화면을 끝으로 "AI 제안" 6단계가 끝나고, 이후 선택 질문(Q7~Q10)으로 이어진다.
 */
function DiagnosisStep5() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [sido, setSido] = useState("");
  const [sigungu, setSigungu] = useState("");
  const [dong, setDong] = useState("");

  // [2026-09-10] 지역 3단을 자유입력 대신 administrative_dong 기반 캐스케이딩
  // 셀렉트박스로 바꿈 - GET /analysis/regions(3,924행, 작아서 한 번에 다 받음)를
  // 받아서 프론트에서 시/도 → 시/군/구 → 행정동 계층으로 걸러 쓴다.
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [regionsError, setRegionsError] = useState(false);

  useEffect(() => {
    const answers = getDiagnosisAnswers();
    if (!answers.storeType) {
      navigate("/diagnosis/5", { replace: true });
      return;
    }
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

  const handleBack = () => navigate("/diagnosis/5");

  const canSubmit = sido.trim() !== "" && sigungu.trim() !== "" && dong.trim() !== "";

  const handleNext = () => {
    if (!canSubmit) return;
    saveDiagnosisAnswers({ sido, sigungu, dong });
    // [2026-09-11] 원래 다음은 Q7(타깃)이지만, 그 사이에 13(상권분석 리포트)가
    // 임시로 끼워졌다 - 11(PSST 확정)·12(업종코드 매칭)가 생기기 전까지의 배치.
    navigate("/diagnosis/market-report");
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="92%" stepLabel="AI 제안 · 6/6" />
      <div className={styles.scrollArea}>
        <span className={styles.topicBadge}>Q6 · 지역·규모</span>
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
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={handleBack}>
          이전
        </button>
        <button type="button" className={styles.nextButton} disabled={!canSubmit} onClick={handleNext}>
          다음 →
        </button>
      </div>
    </div>
  );
}

export default DiagnosisStep5;
