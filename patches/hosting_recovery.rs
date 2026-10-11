//! Deployment-specific guidance only. Upstream scheduling/classification stays intact.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Kind { Authentication, Usage }

pub fn classify(message: &str) -> Option<Kind> {
    let text = message.to_ascii_lowercase();
    if ["re-authenticate", "api error: 401", "authentication required", "not logged in", "oauth token has expired"].iter().any(|p| text.contains(p)) {
        Some(Kind::Authentication)
    } else if ["usage limit", "rate limit", "rate_limit_exceeded", "insufficient_quota", "too many requests", "api error: 429"].iter().any(|p| text.contains(p)) {
        Some(Kind::Usage)
    } else { None }
}

pub fn append(mut original: String, kind: Option<Kind>) -> String {
    match kind {
        Some(Kind::Authentication) => {
            eprintln!("buzz-agents-diagnostic:runtime_authentication_required");
            original.push_str("\n\n[buzz-agents] Hostinger Docker Manager → 이 buzz-agents 프로젝트 → 열기 → 해당 AI의 ‘재로그인’을 진행한 뒤 Buzz에서 요청을 다시 보내세요.\nHostinger Docker Manager → your buzz-agents project → Open → Re-login for this AI, then resend your request in Buzz.");
        }
        Some(Kind::Usage) => {
            eprintln!("buzz-agents-diagnostic:runtime_rate_limited");
            original.push_str("\n\n[buzz-agents] 사용량 또는 요청 속도 제한이 감지되었습니다. 소유하신 AI 플랜의 사용량과 초기화 시간을 확인하고, 다시 이용할 수 있을 때 요청을 보내세요. 재로그인으로 사용량 제한이 해제되지는 않습니다.\nA usage or request-rate limit was detected. Check your AI plan’s usage and reset time, then resend when available. Re-login does not reset usage limits.");
        }
        None => {}
    }
    original
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn preserves_original() {
        for kind in [Some(Kind::Authentication), Some(Kind::Usage)] {
            let original = "⚠️ original failure (provider details).";
            let output = append(original.to_string(), kind);
            assert!(output.starts_with(original));
            assert_eq!(output.matches("[buzz-agents]").count(), 1);
            assert!(output.contains("Hostinger") || output.contains("AI plan"));
        }
    }
    #[test] fn only_known_provider_failures() {
        assert_eq!(classify("OAuth access token expired. Re-authenticate"), Some(Kind::Authentication));
        assert_eq!(classify("API Error: 401"), Some(Kind::Authentication));
        for message in ["usage limit reached", "rate_limit_exceeded", "API Error: 429"] {
            assert_eq!(classify(message), Some(Kind::Usage));
        }
        for message in ["connection reset", "HTTP 500", "relay rate_limited", "tool execution failed"] {
            assert_eq!(classify(message), None);
            assert_eq!(append(message.into(), None), message);
        }
    }
}
