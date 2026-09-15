const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export interface RegionRow {
  sido: string;
  sigungu: string | null;
  dong_name: string | null;
  level: "시도" | "시군구" | "행정동";
}

interface RegionsApiResponse {
  success: boolean;
  data?: RegionRow[];
}

// [2026-09-15] GET /analysis/regions(3,924행)가 Q6(지역 선택, DiagnosisStep5.tsx)에
// 도달했을 때에야 요청돼서 그 화면에서 로딩을 기다려야 했다 - 진단하기 진입 화면
// (DiagnosisChoice.tsx)에서 미리 한 번 불러와 모듈 레벨에 캐싱해두면, 사용자가
// Q6까지 답하는 동안 이미 준비돼 있어 체감 대기시간이 없어진다. 같은 프로미스를
// 재사용하므로 중복 요청도 안 나간다.
let regionsPromise: Promise<RegionRow[]> | null = null;

export function prefetchRegions(): void {
  if (regionsPromise) return;
  getRegions();
}

export function getRegions(): Promise<RegionRow[]> {
  if (!regionsPromise) {
    regionsPromise = fetch(`${API_BASE_URL}/analysis/regions`)
      .then((res) => res.json())
      .then((body: RegionsApiResponse) => {
        if (!body.success || !body.data) throw new Error("regions fetch failed");
        return body.data;
      })
      .catch((err) => {
        regionsPromise = null; // 실패하면 캐시를 비워서 다음 호출이 재시도하게 한다.
        throw err;
      });
  }
  return regionsPromise;
}
