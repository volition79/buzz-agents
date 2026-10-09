# Buzz VPS 연결 도우미 — v0.4 Docker 설정 화면

현재 개발 방향은 **Docker 배포 → 최초 설정 화면 → Windows Buzz 연결**입니다. 각 사용자가 Windows Buzz 신원과 본인 공개키로 설정한 Hostinger Buzz Relay를 먼저 준비합니다. 기존 Relay를 찾고 공개 정보만 확인하며, root 비밀번호·SSH·인간 nsec 입력 없이 연결합니다.

- [새 설치 흐름과 현재 한계](docs/PORTAL-INSTALL.ko.md)
- [검증 결과](docs/PORTAL-VERIFICATION.md)
- 새 로컬 패키지: `dist/portal-v0.4/`

공개 이미지 3개와 [설치 Compose](https://raw.githubusercontent.com/volition79/buzz-agents/main/docker-compose.yml)가 준비되었습니다. GitHub Docker 빌드·임시 실행·익명 다운로드 검증은 통과했으며, 기존 후보의 실제 Hostinger 설치와 공인 HTTPS는 확인했습니다. 기존 「열기」 접속은 확인됐으며, 새 후보는 코드 자동 입력·로그 대체 안내·비밀번호 복구·Windows 재연결을 포함합니다. Docker 업데이트 시 계정과 기존 연결 보존을 검증했습니다. 실제 hPanel의 인증값 전달과 KVM 2 Windows-off 검증은 아직 남아 있습니다.

## 보존된 v0.3 SSH 방식

웹 관리 화면 없이 Windows Buzz의 봇 생성·설정·실행을 유지합니다. 별도 콘솔 도우미가 VPS 최초 설치와 봇별 원격 인증을 안내합니다.

- [사용 방법](docs/EASY-INSTALL.ko.md)
- [현재 검증 결과](docs/EASY-VERIFICATION.md)
- [작업 범위와 남은 합격 조건](TASK.md)

`dist/Buzz-VPS-Setup.exe`를 Windows에서 실행합니다. 이 파일에는 서버 소스와 원격 실행 연결기가 포함됩니다. 설치 URL 공개나 웹 관리 서비스가 필요하지 않습니다.

## 구현 상태

로컬 개발 후보입니다. Windows 실행 파일 교차 빌드와 Linux 테스트를 실제 Windows 실행·Hostinger 배포 성공으로 해석하지 마세요. 실제 VPS Docker 빌드, 공식 계정 인증, AI 협업과 Windows 종료 시험은 별도로 필요합니다.

처음에는 root SSH 접근이 이미 허용된 Ubuntu/Docker VPS가 필요합니다. 도우미는 SSH 보안을 낮추거나 기존 Buzz Relay를 재설치하지 않습니다. 현재 버전은 새 설치와 같은 패키지의 재시도를 지원하며, 기존 v0.2 설치의 자동 업그레이드는 거부합니다.

## 개발자 빌드

Go 1.23.0 이상, Python 3.12 이상으로 실행합니다.

```bash
python3 scripts/build-easy.py
```

도우미에 포함되는 서버 파일은 `scripts/build-easy.py`의 명시적 목록으로 결정됩니다. Go 의존성은 표준 라이브러리뿐입니다. 서버 런타임 패키지는 Docker 빌드 중 다운로드합니다.

기존 원격 실행·보호 정책은 유지합니다. 기본 공유 폴더 선택은 `team`이며, 독립 폴더는 `private`를 지정합니다. 봇 간 멘션은 서로의 공개키를 allowlist에 허용해야 합니다.

v0.2 문서와 테스트 로그는 이력입니다. 새 사용자 설치는 위 사용 방법을 따릅니다.

자동 초기 설정 후보는 도메인 환경값 없이 기존 Hostinger 기본 도메인의 Buzz Relay를 검색합니다. `setup-route`가 추가 생성되며, 기존 후보의 URL 설치·공인 TLS는 확인했으며, 인증값 자동 전달·AI 인증·Windows-off 수용 시험은 별도입니다.
