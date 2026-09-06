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
})
