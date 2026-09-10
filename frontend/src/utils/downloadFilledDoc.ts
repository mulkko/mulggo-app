import { authHeaders } from "../auth/session";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

type FetchResult = { blob: Blob } | { error: string };

/** `/api/matching/attachments/:id/fill`을 호출해서 채워진 서류(hwpx) blob만 받아온다
 * (다운로드는 안 시킴 - 호출부가 바로 저장할지, 확인 후 저장할지 결정). */
async function fetchFilled(attachmentId: number): Promise<FetchResult> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/matching/attachments/${attachmentId}/fill`, {
      headers: authHeaders(),
    });
    const contentType = res.headers.get("content-type") || "";
    const isError = !res.ok || contentType.includes("application/json");
    if (isError) {
      const body = contentType.includes("application/json")
        ? ((await res.json()) as { error?: { message?: string } })
        : null;
      return { error: body?.error?.message ?? "다운로드에 실패했어요." };
    }
    return { blob: await res.blob() };
  } catch {
    return { error: "다운로드에 실패했어요. 서버에 연결할 수 없어요." };
  }
}

/** blob을 실제로 브라우저 다운로드시킨다(파일명 뒤에 "_채움" 붙임). */
export function saveFilledBlob(blob: Blob, fileNameHint: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${fileNameHint.replace(/\.[^.]+$/, "")}_채움.hwpx`;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * attachment_id로 채워진 서류(hwpx)를 받아 즉시 다운로드한다(확인 단계 없음).
 * MyPage.tsx "채우기 이용내역"에서 재다운로드할 때 씀 - 이미 한 번 저장했던 걸
 * 다시 받는 거라 "저장할지 물어보는" 확인 단계가 필요 없음.
 *
 * DocPreview.tsx(처음 채우는 화면)는 이 함수 대신 fetchFilledDocument() + saveFilledBlob()을
 * 따로 써서, 다운로드 전에 "로컬저장/카카오공유" 중 고를 수 있는 확인 모달을 보여준다.
 *
 * 반환값: 성공하면 undefined, 실패하면 사용자에게 보여줄 에러 메시지.
 */
export async function downloadFilledDocument(attachmentId: number, fileNameHint: string): Promise<string | undefined> {
  const result = await fetchFilled(attachmentId);
  if ("error" in result) return result.error;
  saveFilledBlob(result.blob, fileNameHint);
  return undefined;
}

/** DocPreview.tsx 전용: 채워진 서류를 blob으로만 받아온다(저장은 호출부가 모달에서 결정). */
export async function fetchFilledDocument(attachmentId: number): Promise<FetchResult> {
  return fetchFilled(attachmentId);
}
