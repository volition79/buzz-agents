# 0.2.0

## 변경

- 고정 Codex/Claude/Codex 작업 순서 및 `/ba run` 기반 controller/store/worker 제거.
- 봇마다 공식 native `buzz-acp`가 직접 Relay와 대화하는 실행 모드.
- Buzz desktop `info/deploy` 계약을 사용하는 Windows/Linux 원격 제공자 직접 구현.
- OpenSSH forced command 기반 호스트 배포 수신기. 컨테이너에는 Docker socket 없음.
- 봇마다 역할·모델·공급자 선택을 전달. 동종 봇 여러 개 지원.
- 봇별/공급자별 인증 홈 분리, 기본 private 작업 공간, 명시적 공유 workspace.
- 최초 로그인 전 needs_login, 공식 로그인 후 시작.
- native 종료와 정책 중단을 영구 기록하여 자동 부활 방지.
- prompt 시작 횟수·기간·실패 감지 guard. 전역 직렬 prompt 잠금 없음.
- 실행 중 구성 변경 거부; 중지 후 재배포; 이름 충돌 방지; 이미지 ID 검증.
- 호스트의 retire 명령은 컨테이너/등록만 정리하고 데이터 보존.
- 선택적인 일정→native 멘션 발송과 별도 전송 장부.
- 새 프로젝트 buzz-agents-v2. 기존 Relay/기존 v0.1 데이터는 그대로 보존.

## 주의

이는 변경된 구현과 로컬 검증 묶음입니다. 실제 Hostinger 운영 배포를 완료한 버전은 아닙니다.
예약 설정 편집과 초기 서버 준비는 아직 Buzz UI 하나로 처리하지 않습니다.
외부 CLI 내부 호출·하위 AI까지 포함한 정확한 비용 상한은 제공하지 않습니다.
