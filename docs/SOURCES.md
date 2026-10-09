# 규약 참고 자료

2026-10-09에 공식 규약과 실제 소스를 확인하여 v0.2 연결을 작성했습니다.
기존 v0.1 패키지의 common.py/nostr.mjs 및 Docker 기본 틀은 유지·수정했고, 고정 작업 관리 코드는 제거했습니다.
타사 작업관리기 코드를 복사한 구현은 아닙니다. 외부 프로그램/라이브러리는 각 라이선스를 따릅니다.

## 이번 구현에서 확인한 핵심 규약

- Buzz 원격 제공자 문서(드래프트):
  https://github.com/block/buzz/blob/4db7bb0e7f904b2f0ea232aacae6cd7f6b8a3b39/docs/remote-agents.md
- 실제 desktop deploy payload/launch 생성 코드:
  https://github.com/block/buzz/blob/4db7bb0e7f904b2f0ea232aacae6cd7f6b8a3b39/desktop/src-tauri/src/commands/agents_deploy.rs
- native buzz-acp 환경 설정과 기본값:
  https://github.com/block/buzz/blob/4db7bb0e7f904b2f0ea232aacae6cd7f6b8a3b39/crates/buzz-acp/src/config.rs
- 공식 Buzz CLI 메시지·멘션 처리:
  https://github.com/block/buzz/blob/4db7bb0e7f904b2f0ea232aacae6cd7f6b8a3b39/crates/buzz-cli/src/commands/messages.rs
- Windows 제공자 파일 확장자 처리 코드/시험:
  https://github.com/block/buzz/blob/e9269cbdf66b0e2fdb588aa20aad65bcba3ca622/desktop/src-tauri/src/managed_agents/backend.rs
  https://github.com/block/buzz/blob/e9269cbdf66b0e2fdb588aa20aad65bcba3ca622/desktop/src-tauri/src/managed_agents/backend_tests.rs
- Hostinger의 공식 기본 설치 설명:
  https://www.hostinger.com/support/how-to-install-buzz-on-a-hostinger-vps-using-docker/

## 참고한 알려진 한계

- 원격 봇 표시와 로컬 실행 소유권 혼동 보고:
  https://github.com/block/buzz/issues/2349
- 원격 봇 상태/재배포 UI 문제 보고:
  https://github.com/block/buzz/issues/5938

특정 이슈가 사용자 버전에서 재현되는지 또는 이미 수정되었는지는 설치된 앱/Relay/실행기 조합으로 확인해야 합니다.
공식 문서의 과거 알려진 결함과 현재 소스의 구현을 구분하며, 문서에 적혔다고 앱에 항상 노출된다고 단정하지 않습니다.

## 기존 참고 프로젝트

- https://github.com/eldios/buzz-agent-docker
- https://github.com/assafshafran/buzz-agent-fleet
- https://github.com/alext-avi/agent-dock

이 목록은 이전 설계에서 참고한 사례입니다. 이번 검사 결과를 해당 프로젝트나 Hostinger의 인증으로 표현하지 않습니다.

## 라이브러리/빌드

- 암호 연산: @noble/secp256k1 3.0.0 (MIT). 본 패키지에서 암호 알고리즘을 자체 구현하지 않습니다.
- NIP-19 Bech32 디코딩만 Python으로 처리하며 실제 공개키 도출은 라이브러리에 위임합니다.
- Go 제공자는 Go 1.23.2, 외부 모듈 없이 빌드했습니다.
- Dockerfile의 Sprig/Node 지문과 ACP 버전은 v0.1 원본에서 유지한 배포 후보입니다.
  이 실행 환경에서 실제 이미지 pull/build 또는 레지스트리 무결성을 재검증한 것은 아닙니다.
