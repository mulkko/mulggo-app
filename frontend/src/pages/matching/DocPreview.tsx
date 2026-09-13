import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import styles from "../../styles/docPreview.module.css";
import type { RequiredDoc } from "./matchingDetailData";
import { fetchFilledDocument, saveFilledBlob } from "../../utils/downloadFilledDoc";
import { authHeaders } from "../../auth/session";

// ============================================================
// [실험용, 2026-09-11] "채워질 정보 미리보기" 카드 - 사용자 확인 중인 실험 기능.
// 별로면 이 블록(타입 + BizCertPreview 컴포넌트) 통째로 지우고, 아래 DocPreview
// 본문에서 <BizCertPreview /> 쓰는 줄만 빼면 깔끔하게 원상복구됨.
// 값 출처: GET /api/matching/biz-cert-preview (backend/api/matching.py, 같은 표시로 실험용 표시).
// 재OCR 없음 - 이미 저장된 사업자등록증 값을 그대로 조회만 함.
// ============================================================
interface BizCertPreviewData {
  name: string;
  ceoName: string;
  bizNo: string;
  address: string;
  entityType: string;
}

function BizCertPreview() {
  const [data, setData] = useState<BizCertPreviewData | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/matching/biz-cert-preview`, { headers: authHeaders() })
      .then((res) => res.json())
      .then((body: { success: boolean; data?: BizCertPreviewData }) => {
        if (body.success && body.data) setData(body.data);
      })
      .catch(() => {
        /* 등록된 사업자등록증 없거나 실패 - 카드 자체를 안 보여주고 조용히 넘어감(실험용) */
      });
  }, []);

  if (!data) return null;

  return (
    <div className={styles.bizCertPreviewCard}>
      <p className={styles.bizCertPreviewTitle}>이 정보로 채워져요</p>
      <dl className={styles.bizCertPreviewList}>
        <div>
          <dt>상호명</dt>
          <dd>{data.name || "-"}</dd>
        </div>
        <div>
          <dt>대표자명</dt>
          <dd>{data.ceoName || "-"}</dd>
        </div>
        <div>
          <dt>사업자등록번호</dt>
          <dd>{data.bizNo || "-"}</dd>
        </div>
        <div>
          <dt>사업장 주소</dt>
          <dd>{data.address || "-"}</dd>
        </div>
      </dl>
    </div>
  );
}
// ============================================================
// [실험용 끝]
// ============================================================

/**
 * 서류 미리보기 화면 (16-1).
 *
 * 공고 상세(MatchingDetail.tsx)의 신청서류 카드에서 "채우기"를 누르면
 * `/matching/:id/doc-preview`로 들어온다. 파일명/attachmentId는 navigate state로
 * 넘어오는데, 주소창에 `/matching/:id/doc-preview`를 직접 쳐서 들어온 경우(state 없음 -
 * 테스트할 때 편하게 바로 접근하려는 용도)는 GET /api/matching/:id를 호출해서
 * fillable한 서류 중 첫 번째를 자동으로 골라 채운다(없으면 첫 번째 서류).
 *
 * 하단 네비게이션(BottomNav) 없음 — 뒤로가기 헤더만 있는 구조(뒤로가기 → /matching/:id).
 *
 * 실제 동작으로 만든 것: 뒤로가기, "나의 정보로 채우기"
 *   → GET /api/matching/attachments/:id/fill 호출해서 실제로 채운 hwpx를 받아옴
 *   (utils/downloadFilledDoc.ts 공용 함수 - 로그인한 본인의 사업자등록증으로 채움).
 *   [2026-09-10] 받아오자마자 바로 다운로드시키지 않고, "서류가 준비됐어요" 모달을
 *   띄워서 "로컬저장"을 눌러야 그때 실제로 저장되도록 함(원래 의도된 흐름 - 예전엔
 *   확인 없이 바로 다운로드됐음). 실패하면(원본 첨부 소실 등) 화면에 에러 메시지 표시.
 * TODO로만 남긴 것: 카카오톡 공유.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function DocPreview() {
  const navigate = useNavigate();
  const location = useLocation();
  const { id } = useParams<{ id: string }>();

  const state = location.state as { fileName?: string; attachmentId?: number } | null;
  const [doc, setDoc] = useState<{ fileName: string; attachmentId?: number } | null>(
    state?.fileName ? { fileName: state.fileName, attachmentId: state.attachmentId } : null,
  );
  const [loading, setLoading] = useState(!state?.fileName);

  useEffect(() => {
    if (state?.fileName || !id) return;
    fetch(`${API_BASE_URL}/api/matching/${id}`)
      .then((res) => res.json())
      .then((body: { success: boolean; data?: { docs: RequiredDoc[] } }) => {
        const docs = body.success ? body.data?.docs ?? [] : [];
        const picked = docs.find((d) => d.fillable) ?? docs[0];
        setDoc(picked ? { fileName: picked.fileName, attachmentId: picked.attachmentId } : null);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const fileName = doc?.fileName ?? "신청 서류";
  const attachmentId = doc?.attachmentId;

  // 다운로드 모달 open 여부 — 이 화면 안에서만 쓰는 로컬 UI 상태
  const [downloadOpen, setDownloadOpen] = useState(false);
  const [fillError, setFillError] = useState("");
  const [filling, setFilling] = useState(false);
  // [2026-09-10] 채우기 성공 시 바로 다운로드하지 않고 여기 잠깐 들고 있다가,
  // 모달에서 "로컬저장" 눌렀을 때만 실제로 저장한다(attachmentId 없는 더미 fallback
  // 케이스는 채울 blob 자체가 없어서 null로 둠).
  const [filledBlob, setFilledBlob] = useState<Blob | null>(null);

  const handleBack = () => {
    navigate(`/matching/${id}`);
  };

  const handleFill = async () => {
    if (!attachmentId) {
      // attachmentId 없이 들어온 경우(더미데이터 fallback) - 실제 실행할 대상이 없어 모달만 보여준다.
      setFilledBlob(null);
      setDownloadOpen(true);
      return;
    }
    setFillError("");
    setFilling(true);
    const result = await fetchFilledDocument(attachmentId);
    setFilling(false);
    if ("error" in result) {
      setFillError(result.error);
      return;
    }
    setFilledBlob(result.blob);
    setDownloadOpen(true);
  };

  const handleCloseModal = () => {
    setDownloadOpen(false);
  };

  const handleLocalSave = () => {
    if (filledBlob) saveFilledBlob(filledBlob, fileName);
    setDownloadOpen(false);
  };

  const handleKakaoShare = () => {
    // TODO: 카카오톡 공유 SDK 연동 — 지금은 모달만 닫는다
    setDownloadOpen(false);
  };

  if (loading) {
    return (
      <div className={`pageContainer ${styles.page}`}>
        <p className={styles.docDesc}>불러오는 중...</p>
      </div>
    );
  }

  return (
    <div className={`pageContainer ${styles.page}`}>
      {/* 헤더: 뒤로가기 + 파일명 */}
      <header className={styles.header}>
        <button
          type="button"
          className={styles.backButton}
          onClick={handleBack}
          aria-label="뒤로가기"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M16 5l-8 7 8 7" />
          </svg>
        </button>
        <span className={styles.headerTitle}>{fileName}</span>
      </header>

      <main className={styles.body}>
        <div className={styles.iconCircle}>
          <svg
            className={styles.docIcon}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
            <path d="M14 3v5h5" />
            <path d="M9 13h6" />
            <path d="M9 17h6" />
          </svg>
        </div>
        <h1 className={styles.docTitle}>{fileName}</h1>
        <p className={styles.docDesc}>
          아직 만들지 않았어요. 회원님의 사업자 프로필에서
          상호명·대표자명·사업자등록번호·사업장 주소·연락처 등으로 채워 문서를 만들어드려요.
        </p>
        {/* [실험용, 2026-09-11] 위 docDesc가 "이런 필드로 채워요"만 말하고 실제 값은
            안 보여줘서 추가한 카드 - 지우려면 이 줄만 빼면 됨. */}
        <BizCertPreview />
      </main>

      <div className={styles.ctaBar}>
        {fillError && <p className={styles.fillErrorText}>{fillError}</p>}
        <button type="button" className={styles.fillButton} onClick={handleFill} disabled={filling}>
          {filling ? "채우는 중..." : "나의 정보로 채우기"}
        </button>
      </div>

      {downloadOpen && (
        <div className={styles.overlay} onClick={handleCloseModal}>
          <div
            className={styles.modalCard}
            role="dialog"
            aria-modal="true"
            aria-label="서류 다운로드"
            onClick={(event) => event.stopPropagation()}
          >
            <div className={styles.modalHead}>
              <p className={styles.modalTitle}>서류가 준비됐어요</p>
              <p className={styles.modalSub}>{fileName}</p>
            </div>
            <div className={styles.modalButtons}>
              <button
                type="button"
                className={styles.localSaveButton}
                onClick={handleLocalSave}
              >
                <svg
                  className={styles.modalIcon}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M12 3v12" />
                  <path d="M7 11l5 5 5-5" />
                  <path d="M5 20h14" />
                </svg>
                <span className={styles.modalButtonText}>{"로컬 저장소에\n저장하기"}</span>
              </button>
              <button
                type="button"
                className={styles.kakaoButton}
                onClick={handleKakaoShare}
              >
                <svg
                  className={styles.modalIcon}
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path d="M12 3.5C6.75 3.5 2.5 6.9 2.5 11.1c0 2.7 1.79 5.06 4.5 6.42-.2.72-.72 2.62-.83 3.03-.13.5.19.5.39.36.16-.1 2.55-1.73 3.58-2.44.44.06.9.09 1.36.09 5.25 0 9.5-3.4 9.5-7.6S17.25 3.5 12 3.5z" />
                </svg>
                <span className={styles.modalButtonText}>{"카카오톡\n공유하기"}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DocPreview;
