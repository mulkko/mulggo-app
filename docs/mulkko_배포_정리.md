# mulkko 배포 정리

## 확정된 배포 스택
- **백엔드**: Render
- **프론트엔드**: Vercel
- **DB**: Supabase (PostgreSQL, 프로젝트 ID: `jfcpdqpniutrdiruwlcx`)

## Supabase 보안 설정
- RLS(Row Level Security) 전체 테이블에 적용
- 새 프로젝트 기본 설정: "새 테이블 자동 노출 OFF + 자동 RLS ON"

## 배포 절차 (6단계)
1. **Supabase DB 준비**: 스키마 마이그레이션 후 Settings > API에서 프로젝트 URL, anon/service key 확보
2. **백엔드 Render 배포**: New Web Service → GitHub repo 연결 → Root Directory: `backend` → Build: `pip install -r requirements.txt` → Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. **환경변수 등록 (Render)**: `.env` 내용을 Render Environment 탭에 그대로 등록 (Supabase URL/키, Fernet 키 등). `.env` 파일 자체는 업로드 금지
4. **프론트엔드 Vercel 배포**: New Project → 같은 repo 연결 → Root Directory: `frontend` → Framework: Vite 자동 감지
5. **프론트-백엔드 연결**: Vercel 환경변수에 `VITE_API_URL` = Render 백엔드 주소 등록, 백엔드 CORS 설정(`main.py`)에 Vercel 도메인 추가
6. **배포 확인**: Vercel URL 접속해 회원가입/로그인 등 API 호출 기능 테스트

## 미해결/추후 확인 필요
- (배포 진행하면서 막히는 부분, 계정 이전 시 재설정해야 할 항목 등 여기에 계속 추가)

---
*작성일: 2026-09-10 / 계정 이전 시 참고용*
