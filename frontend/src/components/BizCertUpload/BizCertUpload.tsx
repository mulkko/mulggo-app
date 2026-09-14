import { forwardRef, useEffect, useImperativeHandle, useState } from "react";
import type { ChangeEvent } from "react";
import styles from "./bizCertUpload.module.css";
import { Chevron as SharedChevron } from "../FormField/FormField";
import OcrStagePopup from "./OcrStagePopup";

/** 법인/개인 필드 - 값 자체를 누르면 선택 팝업이 뜬다는 걸 알려주는 화살표. */
function Chevron() {
  return <SharedChevron className={styles.chevron} />;
}

// OCR 하이브리드 구조: 팀원 각자 자기 PC에서 localhost로 프론트를 띄우지만,
// OCR(무거운 모델)만은 GPU가 있는 고정 PC로 보낸다.
//   1) 브라우저에 저장해둔 주소가 있으면 그걸 우선 사용
//      (주소가 바뀌면 개발자 콘솔에서 localStorage.setItem("ocr_api_base_url", "http://새주소:8000") 로 갱신)
//   2) 없으면 GPU PC 고정 주소 사용
const OCR_SERVER_HOST = "192.168.0.160";

function resolveOcrApiBaseUrl(): string {
  const saved = localStorage.getItem("ocr_api_base_url");
  if (saved) return saved;
  return `http://${OCR_SERVER_HOST}:8000`;
}

const OCR_API_BASE_URL = resolveOcrApiBaseUrl();

// KSIC 업종 목록(GET /api/ksic/options)은 GPU 없이도 되는 일반 DB 조회라, OCR 전용인
// OCR_API_BASE_URL이 아니라 프론트가 원래 쓰는 메인 백엔드 주소를 그대로 쓴다.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".pdf"];
const MAX_FILE_SIZE_MB = 10;

// 화면에 보여줄 필드 목록. key는 백엔드(_extracted_to_fields)가 내려주는 평탄화된 key와 동일해야 함.
const REVIEW_FIELDS: { key: string; label: string }[] = [
  { key: "company_name", label: "상호 / 법인명" },
  { key: "ceo_name", label: "대표자명" },
  { key: "biz_no", label: "사업자등록번호" },
  { key: "corp_no", label: "법인등록번호" },
  { key: "open_date", label: "개업연월일" },
  { key: "birth_date", label: "생년월일" },
  { key: "business_address", label: "사업장 소재지" },
  { key: "business_category", label: "업태 (OCR 인식값 - 참고용)" },
  { key: "business_item", label: "종목 (OCR 인식값 - 참고용)" },
];

// 법인/개인 구분에 따라 애초에 존재하지 않는 필드 (법인등록번호는 법인만, 생년월일은 개인만).
const NOT_APPLICABLE_WHEN: Record<string, string> = {
  corp_no: "개인",
  birth_date: "법인",
};

// DB(biz_registration_docs)가 NOT NULL로 요구하는 필드 + [2026-09-11] ksic_code도 추가 -
// OCR이 업태/종목 글자를 읽어도 우리 KSIC 참고표에 없는 표현이면 업종코드를 알 방법이
// 없어서(사용자 확인), 업종코드만큼은 항상 확정(자동매칭 또는 직접 선택)돼 있어야 한다.
const REQUIRED_FIELDS = ["company_name", "ceo_name", "biz_no", "open_date", "business_address", "ksic_code"];

// 업태/종목 - 표준 목록이 없는 자유 기재 항목이라 비어 있어도 경고(빨간 테두리) 없이
// "선택 사항"으로만 안내한다. 실제 매칭에 쓰이는 값은 이제 ksic_code(아래 KSIC 셀렉트).
const OPTIONAL_FIELDS = new Set(["business_category", "business_item"]);

const ERROR_FALLBACK = "알 수 없는 오류가 발생했습니다.";

// ══════════════════════════════════════════════════════
// [2026-09-11] KSIC(업종) 선택 — OCR로 업태/종목을 못 읽거나, 읽었어도 우리 KSIC
// 참고표(ksic_codes, 1,202건)에 없는 표현이면 decide_industry()가 자동으로 코드를
// 못 정해준다(백엔드 biz-cert-ocr 응답의 ksic_code가 빈 문자열로 옴). 그 경우
// 사용자가 대분류→중분류→세세분류 3단계로 직접 골라서 ksic_code를 확정한다.
// ══════════════════════════════════════════════════════
interface KsicOption {
  code: string;
  name: string;
  largeCode: string;
  largeName: string;
  mediumCode: string;
  mediumName: string;
}

// 모든 BizCertUpload 인스턴스가 공유하는 캐시 - 팝업을 한 번도 안 열면 요청 자체가 안 간다.
let cachedKsicOptions: KsicOption[] | null = null;
let ksicOptionsPromise: Promise<KsicOption[]> | null = null;

function loadKsicOptions(): Promise<KsicOption[]> {
  if (cachedKsicOptions) return Promise.resolve(cachedKsicOptions);
  if (!ksicOptionsPromise) {
    ksicOptionsPromise = fetch(`${API_BASE_URL}/api/ksic/options`)
      .then((res) => res.json())
      .then((res: { success: boolean; data?: KsicOption[] }) => {
        const options = res.success && res.data ? res.data : [];
        cachedKsicOptions = options;
        return options;
      })
      .catch(() => {
        ksicOptionsPromise = null; // 실패하면 다음에 다시 시도할 수 있게
        return [];
      });
  }
  return ksicOptionsPromise;
}

type KsicStep = "large" | "medium" | "detail";

// [2026-09-11] 검색어를 의미 있는 조각(2글자 이상)으로 쪼갠다 - OCR 업태/종목 텍스트는
// "커피 및 음료" 처럼 KSIC 세부업종명("커피전문점")과 통짜로는 안 겹치는 문구라, 부분
// 문자열 통짜 비교 대신 토큰 단위로 겹치는 게 있으면 매치로 본다.
function tokenizeQuery(text: string): string[] {
  return Array.from(new Set(text.split(/[\s,·/및]+/).map((t) => t.trim()).filter((t) => t.length >= 2)));
}

function KsicSelectPopup({
  onSelect,
  onClose,
  initialQuery = "",
}: {
  onSelect: (code: string, name: string) => void;
  onClose: () => void;
  // [2026-09-11] OCR로 읽은 업태/종목을 그대로 넘겨받아 검색창에 미리 채워둔다 -
  // 사용자가 대분류/중분류를 몰라도 팝업을 열자마자 후보가 바로 보이게. 매치가
  // 없거나 틀리면 검색어를 지우면 기존 3단계 캐스케이드로 돌아간다.
  initialQuery?: string;
}) {
  const [options, setOptions] = useState<KsicOption[] | null>(cachedKsicOptions);
  const [step, setStep] = useState<KsicStep>("large");
  const [large, setLarge] = useState<{ code: string; name: string } | null>(null);
  const [medium, setMedium] = useState<{ code: string; name: string } | null>(null);
  const [query, setQuery] = useState(initialQuery.trim());

  useEffect(() => {
    if (!options) loadKsicOptions().then(setOptions);
  }, [options]);

  const dedupe = <T,>(items: T[], keyOf: (item: T) => string): T[] => {
    const seen = new Set<string>();
    return items.filter((item) => {
      const key = keyOf(item);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  };

  const largeOptions = options
    ? dedupe(options, (o) => o.largeCode).map((o) => ({ code: o.largeCode, name: o.largeName }))
    : [];
  const mediumOptions = options
    ? dedupe(
        options.filter((o) => o.largeCode === large?.code),
        (o) => o.mediumCode,
      ).map((o) => ({ code: o.mediumCode, name: o.mediumName }))
    : [];
  const detailOptions = (options ?? []).filter((o) => o.mediumCode === medium?.code);

  // 검색어가 있으면(자동 채워진 OCR값 포함) 단계 이동 없이 전체 1,202건에서 바로 찾는다 -
  // 결과는 "대분류 > 중분류 > 종목" 경로째로 보여줘서 계층 탐색 없이도 위치를 알 수 있다.
  const searchTokens = tokenizeQuery(query);
  const isSearching = searchTokens.length > 0;
  // 사업자등록증 종목란은 보통 "소프트웨어개발"처럼 띄어쓰기 없이 인쇄되는데 KSIC
  // 공식명은 "소프트웨어 개발"처럼 띄어쓰기가 있어 통짜로 비교하면 안 맞는다 -
  // 양쪽 다 공백을 지우고 비교해서 띄어쓰기 차이를 무시한다.
  const searchResults = isSearching
    ? (options ?? []).filter((o) => {
        const flatName = o.name.replace(/\s+/g, "");
        return searchTokens.some((t) => flatName.includes(t));
      })
    : [];

  const title = isSearching
    ? `검색 결과 (${searchResults.length})`
    : step === "large"
      ? "업종 선택 (1/3) · 대분류"
      : step === "medium"
        ? "업종 선택 (2/3) · 중분류"
        : "업종 선택 (3/3) · 세부업종";

  return (
    <div className={styles.ksicSheetOverlay} onClick={onClose}>
      <div
        className={styles.ksicSheetPanel}
        role="dialog"
        aria-modal="true"
        aria-label="업종 선택"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.ksicSheetHead}>
          {!isSearching && step !== "large" && (
            <button
              type="button"
              className={styles.ksicBackBtn}
              onClick={() => setStep(step === "detail" ? "medium" : "large")}
              aria-label="이전"
            >
              ←
            </button>
          )}
          <p className={styles.ksicSheetTitle}>{title}</p>
          <button type="button" className={styles.ksicSheetCloseBtn} onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </div>

        <div className={styles.ksicSearchWrap}>
          <input
            type="text"
            className={styles.ksicSearchInput}
            placeholder="종목/업종명으로 검색 (예: 커피, 소매, 제조)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button
              type="button"
              className={styles.ksicSearchClearBtn}
              onClick={() => setQuery("")}
              aria-label="검색어 지우기"
            >
              ✕
            </button>
          )}
        </div>

        {!isSearching && (large || medium) && (
          <p className={styles.ksicBreadcrumb}>
            {[large?.name, medium?.name].filter(Boolean).join(" > ")}
          </p>
        )}

        {!options ? (
          <p className={styles.ksicLoading}>업종 목록을 불러오는 중...</p>
        ) : isSearching ? (
          searchResults.length === 0 ? (
            <p className={styles.ksicLoading}>검색 결과가 없어요. 검색어를 지우면 목록에서 고를 수 있어요.</p>
          ) : (
            <ul className={styles.ksicOptionList}>
              {searchResults.map((o) => (
                <li key={o.code}>
                  <button type="button" className={styles.ksicOptionBtn} onClick={() => onSelect(o.code, o.name)}>
                    <span className={styles.radio} aria-hidden="true" />
                    <span className={styles.ksicResultPath}>
                      {o.largeName} &gt; {o.mediumName} &gt; <strong>{o.name}</strong>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : (
          <ul className={styles.ksicOptionList}>
            {step === "large" &&
              largeOptions.map((o) => (
                <li key={o.code}>
                  <button
                    type="button"
                    className={styles.ksicOptionBtn}
                    onClick={() => {
                      setLarge(o);
                      setMedium(null);
                      setStep("medium");
                    }}
                  >
                    <span className={styles.radio} aria-hidden="true" />
                    {o.name}
                  </button>
                </li>
              ))}
            {step === "medium" &&
              mediumOptions.map((o) => (
                <li key={o.code}>
                  <button
                    type="button"
                    className={styles.ksicOptionBtn}
                    onClick={() => {
                      setMedium(o);
                      setStep("detail");
                    }}
                  >
                    <span className={styles.radio} aria-hidden="true" />
                    {o.name}
                  </button>
                </li>
              ))}
            {step === "detail" &&
              (detailOptions.length === 0 ? (
                <p className={styles.ksicLoading}>세부업종이 없어요.</p>
              ) : (
                detailOptions.map((o) => (
                  <li key={o.code}>
                    <button type="button" className={styles.ksicOptionBtn} onClick={() => onSelect(o.code, o.name)}>
                      <span className={styles.radio} aria-hidden="true" />
                      {o.name}
                    </button>
                  </li>
                ))
              ))}
          </ul>
        )}
      </div>
    </div>
  );
}

interface OcrResponse {
  ocr_success: boolean;
  extracted: Record<string, string> | null;
  error: string | null;
  error_type: string | null;
  error_label: string | null;
}

interface BizCertUploadProps {
  // 사용자가 결과를 확인/수정하고 "확인"을 눌렀을 때. 회원가입 제출 시 file은 그대로,
  // fields는 JSON으로 같이 보내면 백엔드가 재OCR 없이 이 값을 그대로 저장한다.
  onConfirm: (fields: Record<string, string>, file: File) => void;
  // "나중에 하기" — 사업자등록증 없이 진행 (선택 사항이라 항상 가능).
  onSkip: () => void;
  // [2026-09-10] true면 파일 선택해도 OCR을 바로 시작 안 하고 파일명만 보여주며
  // 대기한다 - 부모가 ref.start()로 수동 시작(Onboarding.tsx 팝업의 "실행하기"
  // 버튼용). 기본 false면 기존 동작(선택 즉시 자동 시작) 그대로 유지.
  deferStart?: boolean;
  // deferStart일 때, 파일이 선택돼서 "실행하기"를 누를 수 있게 됐음을 부모에게 알림.
  onFileSelected?: (file: File) => void;
  // [2026-09-10] OCR 실패 후 "다시 시도"를 누르면 내부적으로 idle로 돌아가는데(파일도
  // 지워짐), deferStart 쓰는 부모(Onboarding.tsx)의 바깥 버튼 상태(파일명/실행중 여부)도
  // 같이 리셋해야 팝업을 닫았다 열지 않고도 바로 재실행할 수 있어서 이 콜백으로 알려준다.
  onReset?: () => void;
  // [2026-09-10] OCR 실패한 순간 바로 알림 - 넘기면 부모가 자체 경고창(alert 등)으로
  // 대신 안내하고 ref.reset()으로 강제 복귀시키는 용도(Onboarding.tsx 팝업). 안 넘기면
  // (Signup.tsx/ProfileEdit.tsx처럼) 기존과 동일하게 내부 error 페이즈만 보여준다.
  onError?: (message: string) => void;
}

export interface BizCertUploadHandle {
  /** deferStart=true일 때 선택된 파일로 OCR 시작. 선택된 파일 없으면 아무 일도 안 함. */
  start: () => void;
  /** idle(파일 선택 전) 상태로 강제 복귀. onError와 함께 써서 내부 error 페이즈를 건너뛸 때 씀. */
  reset: () => void;
}

type Phase = "idle" | "selected" | "uploading" | "error" | "review";

function validateFile(file: File): string | null {
  const ext = "." + (file.name.split(".").pop() ?? "").toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return "jpg, png, pdf 파일만 업로드할 수 있어요.";
  }
  if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
    return `파일 용량은 ${MAX_FILE_SIZE_MB}MB 이하만 가능해요.`;
  }
  return null;
}

const BizCertUpload = forwardRef<BizCertUploadHandle, BizCertUploadProps>(function BizCertUpload(
  { onConfirm, onSkip, deferStart = false, onFileSelected, onReset, onError },
  ref,
) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  // 입력창으로 열려있는 필드들. 한 번 열리면(빈 값이라 처음부터 열렸든, "수정" 눌러서 열었든)
  // 값이 채워져도 계속 입력창으로 유지 — 안 그러면 빈 값 필드에 타이핑해서 값이 생기는 순간
  // "이제 안 비었네?" 하고 판단해서 스스로 입력창을 닫아버려, 한 글자 치면 튕기는 것처럼 보임.
  const [openFields, setOpenFields] = useState<Set<string>>(new Set());
  const [justOpenedKey, setJustOpenedKey] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState("");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  // 법인/개인은 값이 2개뿐이라 다른 필드(텍스트 입력)와 다르게 "수정" 누르면
  // 선택 팝업이 뜨는 방식으로 처리 - state.
  const [entityTypePopupOpen, setEntityTypePopupOpen] = useState(false);
  // [2026-09-11] 업종(KSIC) 선택 팝업 - 위와 동일한 패턴(값 버튼 누르면 팝업).
  const [ksicPopupOpen, setKsicPopupOpen] = useState(false);

  useEffect(() => {
    if (phase !== "uploading") return;
    setElapsedSeconds(0);
    const timer = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [phase]);

  const reset = () => {
    // deferStart 쓰는 부모(Onboarding.tsx)는 실패해도 파일을 다시 고를 필요 없이
    // 바로 재실행할 수 있어야 하므로, 파일은 유지한 채 "selected" 단계로만 되돌린다.
    if (deferStart && file) {
      setPhase("selected");
      setErrorMessage("");
      onReset?.();
      return;
    }
    setPhase("idle");
    setFile(null);
    setErrorMessage("");
    setOpenFields(new Set());
    setJustOpenedKey(null);
    onReset?.();
  };

  // onError를 받은 부모(Onboarding.tsx)는 실패 처리를 완전히 대신하겠다는 뜻이라
  // 내부 error 페이즈는 아예 안 띄운다(그래야 팝업 안에 또 다른 화면이 겹쳐 보이는
  // 일이 없음) - onError 없으면(Signup.tsx/ProfileEdit.tsx) 기존처럼 내부에서 처리.
  const fail = (message: string) => {
    setErrorMessage(message);
    if (onError) {
      onError(message);
    } else {
      setPhase("error");
    }
  };

  const startUpload = async (target: File) => {
    setPhase("uploading");

    const formData = new FormData();
    formData.append("file", target);

    try {
      const response = await fetch(`${OCR_API_BASE_URL}/api/auth/biz-cert-ocr`, {
        method: "POST",
        body: formData,
      });
      const data: OcrResponse = await response.json();

      if (!data.ocr_success || !data.extracted) {
        fail(data.error_label ?? ERROR_FALLBACK);
        return;
      }

      setFields(data.extracted);
      // 처음부터 비어있는(=확인 필요) 필드는 처음부터 입력창으로 열어둠. 이후 값이 채워져도
      // 계속 열려있음 (openFields 자체를 이 시점 이후로는 값 기준으로 다시 계산하지 않음).
      const extracted = data.extracted;
      const initialOpen = new Set(
        REVIEW_FIELDS.filter(({ key }) => {
          const notApplicable = NOT_APPLICABLE_WHEN[key] === extracted.entity_type;
          return !notApplicable && !extracted[key];
        }).map(({ key }) => key)
      );
      setOpenFields(initialOpen);
      setPhase("review");
    } catch {
      fail("서버에 연결할 수 없습니다.");
    }
  };

  useImperativeHandle(ref, () => ({
    start: () => {
      if (file) startUpload(file);
    },
    reset,
  }));

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0];
    event.target.value = ""; // 같은 파일 다시 선택해도 onChange 다시 뜨게
    if (!selected) return;

    const validationError = validateFile(selected);
    if (validationError) {
      setFile(null);
      setErrorMessage(validationError);
      setPhase("error");
      return;
    }

    setFile(selected);

    if (deferStart) {
      setPhase("selected");
      onFileSelected?.(selected);
      return;
    }

    await startUpload(selected);
  };

  const handleFieldChange = (key: string, value: string) => {
    setFields((prev) => ({ ...prev, [key]: value }));
  };

  const handleConfirm = () => {
    if (!file) return;

    // DB(biz_registration_docs)가 NOT NULL로 요구하는 필드는 비어있으면 저장 자체가 실패하므로,
    // 여기서 먼저 막아서 사용자가 바로 고칠 수 있게 함.
    const missing = REQUIRED_FIELDS.filter((key) => {
      if (NOT_APPLICABLE_WHEN[key] === fields.entity_type) return false;
      return !fields[key];
    });
    if (missing.length > 0) {
      setConfirmError("빨간색으로 표시된 항목을 채워주세요.");
      return;
    }

    setConfirmError("");
    onConfirm(fields, file);
  };

  if (phase === "idle") {
    // 라벨("사업자등록증 (선택)")은 부모(회원가입 화면)에서 그리므로 여기선 드롭존만.
    return (
      <label className={styles.dropzone}>
        <input
          type="file"
          accept="image/*,.pdf"
          onChange={handleFileChange}
          className={styles.fileInput}
        />
        <span className={styles.dropTitle}>파일을 드래그하거나 클릭해서 업로드</span>
        <span className={styles.dropHint}>JPG, PNG, PDF · 최대 10MB</span>
      </label>
    );
  }

  if (phase === "selected") {
    // deferStart용 - 파일명만 보여주고 대기(부모의 "실행하기" 버튼이 ref.start()로 진행시킴).
    return (
      <div className={styles.selectedFile}>
        <span className={styles.selectedFileName}>{file?.name}</span>
        <label className={styles.selectedFileChange}>
          다른 파일 선택
          <input
            type="file"
            accept="image/*,.pdf"
            onChange={handleFileChange}
            className={styles.fileInput}
          />
        </label>
      </div>
    );
  }

  if (phase === "uploading") {
    return <OcrStagePopup elapsedSeconds={elapsedSeconds} onSkip={onSkip} />;
  }

  if (phase === "error") {
    return (
      <div className={styles.field}>
        <p className={styles.errorText}>{errorMessage}</p>
        <button type="button" className={styles.phaseBtn} onClick={reset}>
          다시 시도
        </button>
        <button type="button" className={styles.phaseBtn} onClick={onSkip}>
          나중에 하기
        </button>
      </div>
    );
  }

  const renderReviewRow = (key: string, label: string) => {
    // [2026-09-10] 예: 법인등록번호는 개인일 때 그냥 안 보여준다(이전엔 "-" 회색
    // 텍스트로 보여줬는데, 어차피 못 쓰는 필드를 굳이 노출할 이유가 없다는 사용자 확인).
    const notApplicable = NOT_APPLICABLE_WHEN[key] === fields.entity_type;
    if (notApplicable) return null;

    const value = fields[key] ?? "";
    const isOptional = OPTIONAL_FIELDS.has(key);
    const isOpen = openFields.has(key);
    const showWarnBadge = isOpen && !value && !isOptional; // 열려있는데 아직도 비어있으면 "확인 필요" 유지 (선택 항목 제외)

    return (
      <div key={key} className={styles.fieldRow}>
        <label>
          {label}
          {showWarnBadge && <span className={styles.badgeWarn}> 확인 필요</span>}
          {isOptional && <span className={styles.badgeMuted}> 선택 사항</span>}
        </label>

        {isOpen ? (
          // 열림 여부(openFields)는 값이 바뀌어도 다시 계산 안 함 — 안 그러면 빈 필드에
          // 타이핑해서 값이 생기는 순간 "이제 안 비었네?" 판단해서 스스로 닫혀버려
          // 한 글자 치면 튕기는 것처럼 보이는 문제가 있었음. onBlur로 자동 종료도 안 함
          // (한글 입력 중 브라우저가 순간적으로 blur를 발생시키는 경우가 있어서 동일 문제 재발 방지).
          <input
            type="text"
            value={value}
            autoFocus={justOpenedKey === key}
            onChange={(e) => handleFieldChange(key, e.target.value)}
            className={showWarnBadge ? styles.inputWarn : styles.input}
            // [2026-09-11] 빈 칸만 덩그러니 보이면 "이게 왜 비었지?"가 안 보여서, OCR이
            // 못 읽은 이유를 placeholder로 알려준다 - 필수/선택 문구를 다르게 둬서
            // 바로 아래 필수인 "업종" 셀렉트와 헷갈리지 않게(선택 항목은 "선택 입력"이라 명시).
            placeholder={isOptional ? "OCR로 인식하지 못했어요 (선택 입력)" : "OCR로 인식하지 못했어요 - 직접 입력해주세요"}
          />
        ) : (
          // [2026-09-10] 별도 "수정" 버튼 없이, 값 영역 자체를 누르면 바로 입력창으로
          // 전환되게 함(사용자 확인 - "input 누르면 수정" 방식으로).
          <button
            type="button"
            className={styles.viewText}
            onClick={() => {
              setOpenFields((prev) => new Set(prev).add(key));
              setJustOpenedKey(key);
            }}
          >
            {value}
          </button>
        )}
      </div>
    );
  };

  // phase === "review"
  return (
    <div className={styles.overlay}>
      <div className={styles.reviewBox} role="dialog" aria-modal="true" aria-label="사업자등록증 확인">
        <p className={styles.reviewDesc2}>
          자동으로 인식된 정보예요. 틀린 부분이 있으면 고쳐주세요.
        </p>

        {REVIEW_FIELDS.map(({ key, label }) => (
          <div key={key}>
            {renderReviewRow(key, label)}
            {key === "ceo_name" && (
              <div className={styles.fieldRow}>
                <label>법인/개인</label>
                <button
                  type="button"
                  className={styles.entityValueBtn}
                  onClick={() => setEntityTypePopupOpen(true)}
                >
                  <span className={styles.entityValueText}>{fields.entity_type ?? "개인"}</span>
                  <Chevron />
                </button>
              </div>
            )}
            {key === "business_item" && (
              <div className={styles.fieldRow}>
                <label>
                  업종
                  {!fields.ksic_code && <span className={styles.badgeWarn}> 선택 필요</span>}
                </label>
                <button
                  type="button"
                  className={fields.ksic_code ? styles.entityValueBtn : styles.entityValueBtnWarn}
                  onClick={() => setKsicPopupOpen(true)}
                >
                  <span className={styles.entityValueText}>{fields.ksic_name || "업종을 선택해주세요"}</span>
                  <Chevron />
                </button>
              </div>
            )}
          </div>
        ))}

        {confirmError && <p className={styles.errorText}>{confirmError}</p>}

        <button type="button" className={styles.confirmBtn} onClick={handleConfirm}>
          확인
        </button>
      </div>

      {entityTypePopupOpen && (
        <div className={styles.entityPopupOverlay} onClick={() => setEntityTypePopupOpen(false)}>
          <div
            className={styles.entityPopupCard}
            role="dialog"
            aria-modal="true"
            aria-label="법인/개인 선택"
            onClick={(e) => e.stopPropagation()}
          >
            <p className={styles.entityPopupTitle}>법인/개인 선택</p>
            {["법인", "개인"].map((option) => (
              <button
                key={option}
                type="button"
                className={styles.entityOption}
                onClick={() => {
                  handleFieldChange("entity_type", option);
                  setEntityTypePopupOpen(false);
                }}
              >
                <span
                  className={`${styles.radio} ${(fields.entity_type ?? "개인") === option ? styles.radioOn : ""}`}
                  aria-hidden="true"
                />
                {option}
              </button>
            ))}
          </div>
        </div>
      )}

      {ksicPopupOpen && (
        <KsicSelectPopup
          // [2026-09-11] 종목만 검색어로 - 업태(서비스업/제조업 등)는 국세청 대분류라
          // 너무 뭉뚱그린 단어라서 같이 넣으면 "서비스"류 무관한 KSIC명까지 걸려
          // 정작 중요한 종목 매치가 묻힌다(실측: 업태="서비스"+종목="소프트웨어개발"
          // 검색 시 노이즈 확인). 종목이 비어있을 때만 업태로 대체.
          initialQuery={fields.business_item || fields.business_category || ""}
          onSelect={(code, name) => {
            handleFieldChange("ksic_code", code);
            handleFieldChange("ksic_name", name);
            setKsicPopupOpen(false);
          }}
          onClose={() => setKsicPopupOpen(false)}
        />
      )}
    </div>
  );
});

export default BizCertUpload;
