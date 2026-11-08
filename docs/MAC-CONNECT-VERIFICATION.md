# Mac 연결 후보 검증 기록

2026-11-08, 기준 HEAD `8de6b0e`. 로컬 변경이며 공개 배포 완료 기록이 아니다.

## 통과한 검증

- Python 관련 테스트 92개: portal/release/provider history/packaging 58개,
  추가 management-only 3개, bundle/bot update/reauth 31개.
- Go 연결기와 provider의 Linux race 테스트.
- Windows에서 현재 연결기 테스트 실행: 기존 연결 보존, 재연결, 저장 실패 복구,
  검토된 provider 교체, 알 수 없는 파일 보존. 과거 배포 바이너리 전수 검사는 제외.
- 실제 Chrome + 임시 HTTP 서버: 로그인, Windows 기본 다운로드, Mac 다운로드,
  Mac 파일이 없을 때 버튼 숨김, ZIP 내용, 브라우저 오류 확인.
- 기존 portal 경로/로그인/일시 오류/재시도 Chrome 회귀 검사.
- Windows PE 및 Apple Silicon Mach-O 교차 빌드, 내장 provider 일치,
  배포 후보 manifest의 크기와 SHA-256, Docker 문맥과 공개 소스 패키지 검사.
- release renderer의 기존 형식 및 management-only 계약 생성 확인.
- management-only에서는 실행/중지/보류/로그인 필요 봇과 재시도에서도 자동
  runtime 갱신을 하지 않으며, 관리 서비스 버전 불일치는 여전히 거부함을 검증.

후보: `dist/mac-connect-candidate/`. 재현 명령은 `docs/MAC-CONNECT.md` 참고.
실행 로그는 `.sonol-test/runtime/mac-connect/`에 보관했다.

## 실패 또는 실행하지 못한 검증

- 과거 Windows release 바이너리 다운로드는 재시도에도 GitHub HTTP 504로 실패.
  `TestAllReleasedProvidersUpgrade`는 SKIP이며 통과로 계산하지 않는다.
- 실제 Mac의 Finder 압축 해제, Gatekeeper, 서명/공증, Buzz provider 검색,
  VPS 접속과 모바일 새 요청은 미검증. 현재 지원 후보는 Apple Silicon만 해당.
- Docker 이미지 실제 빌드/업데이트/롤백 및 hPanel 실사용은 미검증.
- 프로젝트 정책 팩 부재로 인증된 정책 게이트 통과를 주장하지 않는다.

## 변경하지 않은 외부 상태

GitHub push, stable 이미지 교체, 운영 VPS, 공개 매뉴얼, zooo.kr은 변경하지 않았다.
기존 고정 설치 URL과 Compose 파일도 수정하지 않았다.
배포 전 Mac 실기 검증과 임시 설치에서 업데이트/롤백 검증이 필요하다.

## 후속 배포 준비 중 갱신

위 기록 이후 후보 소스를 별도 GitHub 브랜치에 올렸다. 운영 main/stable 및
VPS·공개 매뉴얼은 변경하지 않았다. CI 42472261491에서 실제 Docker 이미지와
Apple Silicon macOS의 연결기/provider 테스트가 통과했다. Finder에서 다운로드
파일 열기·Gatekeeper·실제 Buzz 연결은 여전히 미검증이다.
직접 다운로드의 504 오류는 GitHub CLI 경로로 해결했고, 과거 provider 10종의
파일 해시를 확인해 갱신·재연결 테스트에 공급했다. 최신 상태는
`docs/MAC-DEPLOY-STATUS.md`와 해당 CI 기록을 함께 확인한다.
