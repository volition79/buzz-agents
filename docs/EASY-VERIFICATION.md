# v0.3.0 간편 설치 후보 검증 결과

결과: **로컬 검증 통과 / 실환경 목표 미입증**.

## 변경 내용

- Windows 콘솔 연결 도우미: 관리자 SSH를 통한 자체 소스 전송·Docker 빌드·전용 연결 준비.
- 기존 Windows Buzz 원격 제공자는 도우미의 전용 SSH config를 사용. 일반 alias의 이전 동작 유지.
- VPS 제한 명령 수신기: 배포, 공개 상태 조회, 등록된 봇의 공식 로그인, 예약 설정만 허용.
- 인증은 VPS의 봇별 UID10001 홈에서 실행. 실패 시 ready/auth 상태를 기록하지 않음. 동시 인증 잠금 추가.
- 일일 예약 1개를 도우미에서 설정·중지. 권한 부여는 Buzz에서 명시적으로 완료해야 함.
- Windows 연결기 기본 공유 폴더는 team. 서버의 private 옵션과 기존 실행 보호 정책은 유지.
- Python 기본 이미지 digest 고정, 암호 라이브러리 npm lock/ci 적용. ACP의 전이 의존성 전체를 고정한 것은 아님.

## 실행 증거

작성/검증 환경은 Linux 컨테이너. Go 1.26.5, Python 3.12, Node 25 계열.

| 검사 | 실제 결과 |
|---|---|
| Python unittest | 86개 통과, 미실행 0개 |
| Go provider (`-race`) | 9개 통과 |
| Go setup (`-race`) | 7개 통과 |
| 합계 | **102개 통과** |
| Go vet 두 모듈 | 통과 |
| 설치 스크립트 sh 문법 | 통과 |
| 런타임·스크립트 Python AST 파싱 | 통과 |
| Windows x64 연결 도우미/제공자 교차 빌드 | 성공 |
| 임베디드 서버 소스/원본 비교, PE x64 형식, ZIP·manifest·SHA256 | 통과 |

실행 기록: `.sonol-test/runtime/easy-v03/report.json`, 각 명령의 `*.log`.
재현: `python3 scripts/build-easy.py` 후 `python3 scripts/verify-local.py`.
`BUZZ_BUILD_GO`로 검증용 Go 실행 경로를 지정할 수 있습니다. 빌드용 Go는 PATH에서 찾습니다.

새 테스트는 설치 충돌 보존, 경로·SSH 명령 삽입 거부, 전용 config 선택, 설치 실패의 성공 처리 방지, 원격 PTY 인증 전달, 인증 실패 상태 보존, 알려진 예약 대상·권한 확인을 검증합니다. 기존 테스트를 삭제하거나 기대값을 약화하지 않았습니다. Python 암호 라이브러리를 설치하여 이전 후보에서 미실행이던 실제 공개키 도출 검사도 통과했습니다.

네트워크에서 확인한 것은 npm의 지정 ACP 버전 메타데이터/배포 소스, Python 태그, Sprig·Node 이미지 manifest의 digest 일치, Buzz LICENSE의 checksum입니다. 이것은 이미지 pull/build 성공과 다릅니다.

원본 ZIP SHA256: `35624b5fa369bbfad745c93b184d64299a9d91d57f6d7fbe9c490da2a24faa65`.
원본 ZIP과 사용자 기존 설치 가이드 파일은 변경하지 않았습니다.

## 증거의 한계

SSH·Docker·공식 로그인 경계 테스트는 모의 프로세스/호출을 사용했습니다. 이 결과로 실제 서버 또는 계정 인증을 통과했다고 말할 수 없습니다. Windows 바이너리는 교차 빌드한 것이며 Windows에서 실행하지 않았습니다.

Sonol Test의 집중 검증 절차와 프로젝트 adapter를 사용했습니다. 현재 설치된 자동 plan/verify 엔진은 정책 test-registry를 요구하므로, 승인된 Policy Validator off 범위를 지키며 직접 명령과 원본 로그로 검증했습니다. 자동 계획 receipt나 정책 gate 통과를 주장하지 않습니다.

## 아직 실행하지 않은 필수 시험

- 실제 Docker 이미지 빌드와 Compose 동작 (현재 환경에 Docker daemon 없음).
- Windows에서 도우미·OpenSSH·Buzz 제공자 검색/배포 (Windows 런타임 접근 없음).
- 실제 SSH 서버의 강제 명령·sudo·PTY 및 Hostinger SSH 접속 방식.
- Codex·Claude 플랜 로그인, 실제 모델 응답과 토큰 갱신.
- 실제 Relay 회원·채널 권한, 봇 표시와 상호 멘션.
- 두 AI의 공동 파일 작업 완료.
- Windows 완전 종료 이후 **새** 예약 작업의 시작과 완료.
- KVM 2 CPU/RAM 및 정상/강제 재부팅·장시간 운영.

인증 홈과 작업 폴더는 영구 마운트하도록 설계했습니다. 사용량 제한, 인증 재승인, held 복구가 불필요하다는 보장은 하지 않습니다. 공개 이미지/설치 URL과 코드 서명도 아직 없습니다.

## 실제 VPS에 적용할 변경 범위

도우미를 실행할 경우: `/opt/buzz-agents`, `/var/lib/buzz-agents-v2`, 전용 사용자 `buzzdeploy`, 전용 SSH 공개키·forced-command, `/usr/local/bin/buzz-agents-ssh`, `/usr/local/sbin/buzz-agents-easy-bridge`, 기존 패키지의 제한 수신기와 전용 sudo 규칙, 봇 컨테이너를 생성합니다. 예약 선택 시 `/var/lib/buzz-agents-easy-scheduler`와 스케줄러 컨테이너를 추가합니다.
기존 Relay와 Traefik을 변경하거나 삭제하지 않습니다. 다른 버전이 존재하면 자동 업그레이드하지 않습니다. 개발 중 실제 VPS 적용은 하지 않았습니다.
