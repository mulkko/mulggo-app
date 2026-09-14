import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // [테스트] 같은 네트워크의 팀원 PC에서 OCR 테스트 페이지 접속 가능하게 0.0.0.0으로 바인딩.
  // (기본값은 localhost만 열림 — 로컬 전용으로 되돌리려면 이 줄 삭제)
  server: {
    host: true,
  },
  // [2026-09-14, 사용자 확인] 실서버(EC2)에서 `vite`(개발서버, 요청마다 즉석 변환이라
  // 느림)를 그대로 띄워서 체감 속도가 느렸던 문제 - `npm run build`로 빌드한 정적
  // 파일을 `npm run preview`로 서빙하도록 바꾼다. server와 동일하게 0.0.0.0:5173으로
  // 고정해서 --host 플래그 없이도 외부 접속 가능하게 함.
  preview: {
    host: true,
    port: 5173,
  },
})
