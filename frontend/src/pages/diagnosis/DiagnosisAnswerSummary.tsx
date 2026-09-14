import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import styles from "../../styles/diagnosis.module.css";
import DiagnosisHeader from "./DiagnosisHeader";
import SelectSheet from "../../components/SelectSheet/SelectSheet";
import { authHeaders } from "../../auth/session";
import { getDiagnosisAnswers, saveDiagnosisAnswers, type Origin, type StoreType } from "./diagnosisAnswers";
import BottomNav from "../../components/BottomNav/BottomNav";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const ORIGIN_LABEL: Record<Origin, string> = {
  problem: "① 불편했던 경험에서 (문제 해결형)",
  opportunity: "② 이런 게 있으면 좋겠다 (기회 추구형)",
};
const ORIGIN_OPTIONS = (Object.entries(ORIGIN_LABEL) as [Origin, string][]).map(([value, label]) => ({ value, label }));

const STORE_TYPE_LABEL: Record<StoreType, string> = {
  offline: "① 고객 방문형 오프라인 매장·공간",
  booking: "② 예약 방문형 서비스 공간",
  delivery: "③ 배달·제조 중심, 고객 방문 없음",
  online: "④ 온라인 판매·중개 플랫폼",
  digital: "⑤ 앱·소프트웨어·디지털 서비스",
};
const STORE_TYPE_OPTIONS = (Object.entries(STORE_TYPE_LABEL) as [StoreType, string][]).map(([value, label]) => ({ value, label }));

interface IndustryMatch {
  state: string;
  name: string;
  confidence: string;
  question: string;
  codeNames?: Record<string, string>;
}

interface DiagnosisStartResponse {
  success: boolean;
  data?: {
    session_id: number;
    resolvedKsicCodes?: string[];
    industryMatch?: IndustryMatch | null;
    track?: "cafe" | "tech";
  };
  error?: { message: string };
}

// [2026-09-14] Q6(지역) 인라인 수정용 - DiagnosisStep5.tsx와 동일한 데이터/로직
// (administrative_dong 기반 캐스케이딩 시/도 → 시/군/구 → 행정동).
interface RegionRow {
  sido: string;
  sigungu: string | null;
  dong_name: string | null;
  level: "시도" | "시군구" | "행정동";
}
const toSelectSheetOptions = (values: string[]) => values.map((v) => ({ label: v, value: v }));

type EditKey = "seedInterest" | "origin" | "problemToSolve" | "solutionApproach" | "storeType" | "region";

/**
 * 6번(지역) 제출 직후 뜨는 "질응답 내용 정리" 화면 (사용자 확인) - 필수 질문 6개
 * 답변을 한눈에 보여준 뒤 "업종코드 보여주기"(DiagnosisIndustryResult) →
 * 분석 리포트(DiagnosisReport) 순으로 이어진다.
 *
 * [2026-09-12] 업종코드 매칭(POST /api/diagnosis/start) 트리거를 Q6(DiagnosisStep5)
 * 에서 여기로 옮김(사용자 확인) - Q1~Q6 답변을 먼저 요약으로 보여준 다음 "업종코드
 * 확인하기" 버튼을 눌러야 세션 생성 + 업종코드 매칭이 시작된다(11~13초).
 *
 * [2026-09-12] 상권/기술창업 분석은 여기서 시작하지 않는다 - 매칭 후보가 여러 개면
 * "업종코드 보여주기" 화면(DiagnosisIndustryResult)에서 사용자가 하나를 확정해야
 * (POST /{id}/select-industry) 그때 비로소 분석이 시작된다(backend/api/diagnosis.py
 * 상단 주석 참고). 그래서 이 화면의 로딩 오버레이는 "업종코드를 분석하고 있어요"
 * (매칭까지)만 의미하고, 상권/기술창업 분석 대기는 다음 화면 몫이다.
 *
 * [2026-09-12] 카드 디자인은 emkim99님이 만든 DiagnosisPsstConfirm.tsx(같은 목적의
 * 별도 화면, 디자인 참고용으로만 남김)의 .cardList/.confirmCard를 그대로 가져다 씀
 * (사용자 확인 - 로직은 이 화면 그대로, 디자인만 emkim99님 걸로).
 *
 * [2026-09-14, 사용자 확인] 카드를 누르면 그 자리에서 값을 고치는 인라인 수정 기능
 * 추가 - "아이콘 눌러서 수정하면 영역이 너무 좁다"는 피드백으로, 별도 화면 대신
 * 카드 안에서 형태에 맞는 입력을 바로 받는다: Q1·Q3·Q4(자유서술)는 textarea, Q2·
 * Q5·Q6(디자인은 셀렉트지만 실제로는 라디오 단일선택)은 SelectSheet(Step5의 지역
 * 3단 선택과 동일 컴포넌트) 재사용. 선택형(Q2·Q5)은 고르는 즉시 저장되고, 자유서술
 * (Q1·Q3·Q4)과 지역(Q6)은 "저장" 버튼을 눌러야 반영된다(지역은 3단이 다 채워져야
 * 저장 가능).
 */
function DiagnosisAnswerSummary() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [answers, setAnswers] = useState(getDiagnosisAnswers());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const [editingKey, setEditingKey] = useState<EditKey | null>(null);
  const [textDraft, setTextDraft] = useState("");
  const [draftSido, setDraftSido] = useState("");
  const [draftSigungu, setDraftSigungu] = useState("");
  const [draftDong, setDraftDong] = useState("");
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [regionsError, setRegionsError] = useState(false);

  useEffect(() => {
    if (!submitting) return;
    setElapsedSeconds(0);
    const timer = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [submitting]);

  useEffect(() => {
    const a = getDiagnosisAnswers();
    // [2026-09-14, 사용자 확인] dong은 기술창업형(오프라인 매장 아님)이면 비어있는 게
    // 정상이라(DiagnosisStep5.tsx 참고) 더 이상 필수 가드에 안 넣는다.
    if (!a.sido || !a.sigungu) {
      navigate("/diagnosis/6", { replace: true });
      return;
    }
    setAnswers(a);
    setReady(true);
  }, [navigate]);

  // Q6(지역) 카드를 한 번이라도 열어볼 수 있으니 목록은 미리 받아둔다(DiagnosisStep5.tsx와 동일).
  useEffect(() => {
    fetch(`${API_BASE_URL}/analysis/regions`)
      .then((res) => res.json())
      .then((body: { success: boolean; data?: RegionRow[] }) => {
        if (body.success && body.data) setRegions(body.data);
        else setRegionsError(true);
      })
      .catch(() => setRegionsError(true));
  }, []);

  const handleBack = () => navigate("/diagnosis/6");

  const closeEdit = () => setEditingKey(null);

  const openTextEdit = (key: "seedInterest" | "problemToSolve" | "solutionApproach", current: string) => {
    setTextDraft(current);
    setEditingKey(key);
  };

  const openRegionEdit = () => {
    setDraftSido(answers.sido ?? "");
    setDraftSigungu(answers.sigungu ?? "");
    setDraftDong(answers.dong ?? "");
    setEditingKey("region");
  };

  const toggleCard = (key: EditKey) => {
    if (editingKey === key) {
      closeEdit();
      return;
    }
    if (key === "region") {
      openRegionEdit();
    } else if (key === "seedInterest") {
      openTextEdit("seedInterest", answers.seedInterest ?? "");
    } else if (key === "problemToSolve") {
      openTextEdit("problemToSolve", answers.problemToSolve ?? "");
    } else if (key === "solutionApproach") {
      openTextEdit("solutionApproach", answers.solutionApproach ?? "");
    } else {
      // origin/storeType은 선택 즉시 저장되니 열기만 하면 됨(초기값은 answers 그대로 사용).
      setEditingKey(key);
    }
  };

  const saveTextEdit = (field: "seedInterest" | "problemToSolve" | "solutionApproach") => {
    setAnswers(saveDiagnosisAnswers({ [field]: textDraft }));
    closeEdit();
  };

  const saveOrigin = (value: string) => {
    setAnswers(saveDiagnosisAnswers({ origin: value as Origin }));
    closeEdit();
  };

  const saveStoreType = (value: string) => {
    setAnswers(saveDiagnosisAnswers({ storeType: value as StoreType }));
    closeEdit();
  };

  const handleSidoChange = (value: string) => {
    setDraftSido(value);
    setDraftSigungu("");
    setDraftDong("");
  };
  const handleSigunguChange = (value: string) => {
    setDraftSigungu(value);
    setDraftDong("");
  };
  // [2026-09-14, 사용자 확인] 기술창업형(오프라인 매장 아님)은 행정동을 안 받는다
  // (DiagnosisStep5.tsx 참고) - 시/도·시/군/구만 채워지면 저장 가능.
  const hasStore = answers.storeType === "offline" || answers.storeType === "booking";
  const canSaveRegion = hasStore
    ? draftSido.trim() !== "" && draftSigungu.trim() !== "" && draftDong.trim() !== ""
    : draftSido.trim() !== "" && draftSigungu.trim() !== "";
  const saveRegion = () => {
    if (!canSaveRegion) return;
    setAnswers(saveDiagnosisAnswers({ sido: draftSido, sigungu: draftSigungu, dong: hasStore ? draftDong : "" }));
    closeEdit();
  };

  const sidoOptions = toSelectSheetOptions(
    regions.filter((r) => r.level === "시도").map((r) => r.dong_name ?? r.sido),
  );
  const sigunguOptions = toSelectSheetOptions(
    regions.filter((r) => r.level === "시군구" && r.sido === draftSido).map((r) => r.dong_name ?? ""),
  );
  const dongOptions = toSelectSheetOptions(
    regions
      .filter((r) => r.level === "행정동" && r.sido === draftSido && r.sigungu === draftSigungu)
      .map((r) => r.dong_name ?? ""),
  );

  const handleNext = async () => {
    if (submitting) return;
    const hasStore = answers.storeType === "offline" || answers.storeType === "booking";

    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE_URL}/api/diagnosis/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          origin: answers.origin || "problem",
          seed_interest: answers.seedInterest || "",
          problem_to_solve: answers.problemToSolve || "",
          solution_approach: answers.solutionApproach || "",
          has_store: hasStore,
          sido: answers.sido,
          sigungu: answers.sigungu,
          dong: answers.dong,
          mode: answers.mode || "precise",
        }),
      });
      if (res.status === 401) {
        setError("로그인이 필요해요. 로그인 후 다시 시도해주세요.");
        return;
      }
      const data: DiagnosisStartResponse = await res.json();
      if (!data.success || !data.data) {
        setError(data.error?.message || "진단 시작에 실패했어요.");
        return;
      }
      const match = data.data.industryMatch;
      saveDiagnosisAnswers({
        sessionId: data.data.session_id,
        resolvedKsicCodes: data.data.resolvedKsicCodes ?? [],
        industryMatchName: match?.name,
        industryMatchState: match?.state,
        industryMatchConfidence: match?.confidence,
        industryMatchCodeNames: match?.codeNames ?? {},
        track: data.data.track,
      });
      navigate("/diagnosis/industry-result");
    } catch {
      setError("서버에 연결할 수 없습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!ready) return null;

  const origin = answers.origin ?? "problem";
  const region = [answers.sido, answers.sigungu, answers.dong].filter(Boolean).join(" ");

  const rows: { key: EditKey; label: string; value: string }[] = [
    { key: "seedInterest", label: "Q1 · 사업 아이템", value: answers.seedInterest ?? "" },
    { key: "origin", label: "Q2 · 출발점", value: ORIGIN_LABEL[origin] },
    { key: "problemToSolve", label: "Q3 · 문제 정의", value: answers.problemToSolve ?? "" },
    { key: "solutionApproach", label: "Q4 · 해결 방식", value: answers.solutionApproach ?? "" },
    { key: "storeType", label: "Q5 · 매장 운영 형태", value: answers.storeType ? STORE_TYPE_LABEL[answers.storeType] : "" },
    { key: "region", label: "Q6 · 지역·규모", value: region },
  ];

  return (
    <div className={`pageContainer ${styles.page}`}>
      <DiagnosisHeader onBack={handleBack} pct="100%" stepLabel="답변 정리" />
      <div className={styles.scrollArea}>
        <h1 className={styles.questionTitle}>지금까지 답변한 내용이에요</h1>
        <p className={styles.questionSub}>이 내용을 바탕으로 업종코드를 매칭하고 분석 리포트를 준비했어요.</p>
        <div className={styles.cardList}>
          {rows.map((row) => {
            const isEditing = editingKey === row.key;
            return (
              <div
                key={row.key}
                className={styles.confirmCard}
                onClick={() => toggleCard(row.key)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") toggleCard(row.key);
                }}
              >
                <span className={styles.confirmCardHead}>
                  <span className={styles.confirmCardLabel}>{row.label}</span>
                  <svg
                    className={styles.confirmCardEditIcon}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z" />
                  </svg>
                </span>

                {!isEditing && <span className={styles.confirmCardValue}>{row.value || "-"}</span>}

                {isEditing && (row.key === "seedInterest" || row.key === "problemToSolve" || row.key === "solutionApproach") && (
                  <div className={styles.confirmCardEditArea} onClick={(e) => e.stopPropagation()}>
                    <input
                      type="text"
                      className={styles.confirmCardEditInput}
                      value={textDraft}
                      onChange={(e) => setTextDraft(e.target.value)}
                      autoFocus
                    />
                    <div className={styles.confirmCardEditActions}>
                      <button type="button" className={styles.confirmCardCancelButton} onClick={closeEdit}>
                        취소
                      </button>
                      <button type="button" className={styles.confirmCardSaveButton} onClick={() => saveTextEdit(row.key as "seedInterest" | "problemToSolve" | "solutionApproach")}>
                        저장
                      </button>
                    </div>
                  </div>
                )}

                {isEditing && row.key === "origin" && (
                  <div className={styles.confirmCardEditArea} onClick={(e) => e.stopPropagation()}>
                    <SelectSheet
                      label="출발점"
                      name="origin-edit"
                      value={answers.origin ?? "problem"}
                      options={ORIGIN_OPTIONS}
                      onChange={saveOrigin}
                    />
                  </div>
                )}

                {isEditing && row.key === "storeType" && (
                  <div className={styles.confirmCardEditArea} onClick={(e) => e.stopPropagation()}>
                    <SelectSheet
                      label="매장 운영 형태"
                      name="storeType-edit"
                      value={answers.storeType ?? ""}
                      options={STORE_TYPE_OPTIONS}
                      onChange={saveStoreType}
                    />
                  </div>
                )}

                {isEditing && row.key === "region" && (
                  <div className={styles.confirmCardEditArea} onClick={(e) => e.stopPropagation()}>
                    <div className={styles.regionGroup}>
                      <SelectSheet
                        label="시/도"
                        name="region-sido-edit"
                        value={draftSido}
                        options={sidoOptions}
                        onChange={handleSidoChange}
                        placeholder="시/도 선택"
                        disabled={sidoOptions.length === 0}
                      />
                      <SelectSheet
                        label="시/군/구"
                        name="region-sigungu-edit"
                        value={draftSigungu}
                        options={sigunguOptions}
                        onChange={handleSigunguChange}
                        placeholder="시/군/구 선택"
                        disabled={!draftSido}
                      />
                      {/* [2026-09-14, 사용자 확인] 기술창업형은 행정동을 안 받아서
                          일단 주석처리 - hasStore(오프라인 매장)일 때만 보여준다. */}
                      {hasStore && (
                        <SelectSheet
                          label="행정동"
                          name="region-dong-edit"
                          value={draftDong}
                          options={dongOptions}
                          onChange={setDraftDong}
                          placeholder="행정동 선택"
                          disabled={!draftSigungu}
                        />
                      )}
                    </div>
                    {regionsError && <p className={styles.errorText}>지역 목록을 불러오지 못했어요. 새로고침해주세요.</p>}
                    <div className={styles.confirmCardEditActions}>
                      <button type="button" className={styles.confirmCardCancelButton} onClick={closeEdit}>
                        취소
                      </button>
                      <button type="button" className={styles.confirmCardSaveButton} disabled={!canSaveRegion} onClick={saveRegion}>
                        저장
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
        {error && <p className={styles.errorText}>{error}</p>}
      </div>
      <div className={styles.bottom}>
        <button type="button" className={styles.prevButton} onClick={handleBack}>
          이전
        </button>
        <button type="button" className={styles.nextButton} disabled={submitting} onClick={handleNext}>
          {submitting ? (
            "분석 시작 중..."
          ) : (
            <>
              업종코드 확인하기
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
            </>
          )}
        </button>
      </div>
      {submitting && (
        <div className={styles.loadingOverlay}>
          <div className={styles.loadingBox} role="status" aria-live="polite">
            <div className={styles.spinner} />
            <p className={styles.loadingText}>업종코드를 분석하고 있어요... ({elapsedSeconds}초 경과)</p>
            <p className={styles.loadingHint}>업종을 확인하고 나면 상권·기술창업 분석을 이어서 준비할게요</p>
          </div>
        </div>
      )}

      <BottomNav active="idea" />
    </div>
  );
}

export default DiagnosisAnswerSummary;
