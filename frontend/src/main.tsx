import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/noto-sans-kr/400.css'
import '@fontsource/noto-sans-kr/700.css'
import '@fontsource/noto-sans-kr/900.css'
import './index.css'
import './styles/adminTokens.css'
import './styles/webTokens.css'
import './styles/adminCommon.css'
import './styles/common.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
