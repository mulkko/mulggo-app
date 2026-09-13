import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import SelectSheet from "../../components/SelectSheet/SelectSheet";
import { getDiagnosisAnswers, saveDiagnosisAnswers } from "./diagnosisAnswers";
import BottomNav from "../../components/BottomNav/BottomNav";

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
 *
 * [2026-09-12] 업종코드 매칭(POST /api/diagnosis/start) 트리거를 여기서 "질응답 내용
 * 정리"(DiagnosisAnswerSummary) 화면의 버튼으로 옮김(사용자 확인) - 여기는 이제
 * sido/sigungu/dong만 저장하고 바로 다음 화면으로 넘어간다. 이유: Q1~Q6 답변을 먼저
 * 요약으로 보여준 다음에 "분석 시작"을 누르게 하는 게 자연스럽다는 판단 - 분석
 * 시작 이후 흐름(업종코드 매칭 → 결과 화면 → 백그라운드 상권/기술창업 분석 폴링)은
 * DiagnosisAnswerSummary.tsx 상단 주석 참고, 그대로 유지.
 */
function DiagnosisStep5() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [sido, setSido] = useState("");
  const [sigungu, setSigungu] = useState("");
  const [dong, setDong] = useState("");
  // [2026-09-14, 사용자 확인] 기술창업형(오프라인 매장이 아닌 경우)은 상권분석과
  // 달리 행정동 단위 데이터를 안 쓴다(backend/api/diagnosis.py의 _resolve_tech_report는
  // ksic_codes만 받고 지역 자체를 안 받음) - 그래서 이 경로에서는 시/도·시/군/구까지만
  // 받고 행정동 선택은 일단 주석처리한다(사용자 확인, "일단 주석처리해줘" - 나중에
  // 필요해지면 되살릴 수 있게 완전히 지우지 않음).
  const [hasStore, setHasStore] = useState(true);

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
    setHasStore(answers.storeType === "offline" || answers.storeType === "booking");
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

  const canSubmit = hasStore
    ? sido.trim() !== "" && sigungu.trim() !== "" && dong.trim() !== ""
    : sido.trim() !== "" && sigungu.trim() !== "";

  const handleNext = () => {
    if (!canSubmit) return;
    saveDiagnosisAnswers({ sido, sigungu, dong: hasStore ? dong : "" });
    navigate("/diagnosis/summary");
  };

  if (!ready) return null;

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="92%" stepLabel="6/6" />
      <div className={styles.scrollArea}>
        <span className={styles.topicBadge}>Q6 · 지역·규모</span>
        <h1 className={styles.questionTitle}>어디서, 어느 정도 규모로 시작하실 계획인가요?</h1>
        <p className={styles.questionSub}>
          {hasStore ? "시/도 → 시/군/구 → 행정동 순서로 선택해주세요." : "시/도 → 시/군/구 순서로 선택해주세요."}
        </p>
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
          {/* [2026-09-14, 사용자 확인] 기술창업형(오프라인 매장 아님)은 행정동 단위
              데이터를 안 써서 일단 주석처리 - hasStore(오프라인 매장)일 때만
              보여준다. 나중에 기술창업형도 행정동이 필요해지면 이 조건만 지우면 됨. */}
          {hasStore && (
            <SelectSheet
              label="행정동"
              name="dong"
              value={dong}
              options={dongOptions}
              onChange={setDong}
              placeholder="행정동 선택"
              disabled={!sigungu}
            />
          )}
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
          다음
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

      <BottomNav active="idea" />
    </div>
  );
}

export default DiagnosisStep5;
