# scripts/

로컬 PC 스케줄러로 돌리는 배치 스크립트 모음.

## crawl_bizinfo.bat — 기업마당 원본 공고 매일 수집

### 왜 GitHub Actions가 아니라 로컬인가

기업마당 API(`www.bizinfo.go.kr`)는 해외 IP 접속을 차단한다. GitHub Actions 러너는
미국에 있어서 접속 타임아웃이 난다 (`Connection to www.bizinfo.go.kr timed out`).
그래서 **기업마당 수집만** 한국에 있는 PC에서 작업 스케줄러로 돌린다.

창업진흥원(K-Startup) 수집은 `apis.data.go.kr`이라 해외에서도 붙어서,
`.github/workflows/crawl-daily.yml`에서 매일 04:00(KST)에 계속 자동 실행된다.

### 사전 준비

- 이 저장소가 clone 되어 있고, `.venv`(파이썬 3.11 가상환경)와 `.env`가 세팅된 PC
  (= 백엔드 개발이 되는 PC면 이미 끝)
- 그 PC가 매일 04:00에 켜져 있고 로그인 상태일 것 (화면 잠금은 무방)

### 작업 스케줄러 등록 (PowerShell, 한 번만)

경로는 이 저장소를 clone 한 실제 위치로 바꿔서 실행한다.

```powershell
$bat = "C:\workspaces\10_Final\mulggo-app\scripts\crawl_bizinfo.bat"

$action   = New-ScheduledTaskAction -Execute $bat
$trigger  = New-ScheduledTaskTrigger -Daily -At 4:00am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable
Register-ScheduledTask -TaskName "mulkko-crawl-bizinfo" -Action $action -Trigger $trigger `
  -Settings $settings -Description "기업마당 원본 공고 매일 수집 (해외 IP 차단으로 GitHub Actions 대신 로컬 실행)"
```

- `-StartWhenAvailable`: 04:00에 PC가 꺼져 있었으면, 켜진 직후 밀린 작업을 실행한다.
- 로그인한 사용자 계정으로 실행된다 (비밀번호 저장 안 함). PC가 켜져 있고 로그인만 돼 있으면 됨.

### 확인 / 관리

```powershell
# 지금 바로 한 번 실행해보기
Start-ScheduledTask -TaskName "mulkko-crawl-bizinfo"

# 마지막 실행 결과 (LastTaskResult가 0이면 성공)
Get-ScheduledTaskInfo -TaskName "mulkko-crawl-bizinfo"

# 삭제
Unregister-ScheduledTask -TaskName "mulkko-crawl-bizinfo" -Confirm:$false
```

- 실행 로그: `logs\crawl_bizinfo.log` (저장소 루트, git 추적 안 함)
- DB 실행 이력: `crawl_batch_logs` 테이블의 `source = 'bizinfo'` 행
- 수집 코드(`backend/crawler/bizinfo_api.py`)가 바뀌면 그 PC에서 `git pull` 해줘야 최신으로 돈다.
