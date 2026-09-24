import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ErrorBox } from "../components/States";

/* PRD-01 §5 확정 사항을 화면에 그대로 드러낸다.
   - 공개 가입 (초대제 아님)
   - 이메일 + 비밀번호. 소셜 로그인 없음 (FR-11)
   - 이메일 인증 없음 — 이메일은 식별자일 뿐 연락 수단이 아니다
   - 비밀번호 찾기 메일 없음. 잊으면 관리자가 재설정한다 (§9) */

function policyError(pw) {
  if (pw.length < 10) return "비밀번호는 10자 이상이어야 합니다";
  for (let i = 0; i < pw.length - 3; i++) {
    if (pw[i].repeat(4) === pw.slice(i, i + 4))
      return "같은 문자를 4번 이상 반복할 수 없습니다";
  }
  return null;
}

export default function Login({ mode = "login" }) {
  const isSignup = mode === "signup";
  const { login, signup } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  // 클라이언트 검증은 보조일 뿐이다. 서버가 강제한다 (PRD-01 FR-5).
  const pwErr = isSignup && pw ? policyError(pw) : null;
  const mismatch = isSignup && pw2 && pw !== pw2;

  async function submit(e) {
    e.preventDefault();
    if (pwErr || mismatch) return;
    setErr(null);
    setBusy(true);
    try {
      const u = await (isSignup ? signup(email, pw) : login(email, pw));
      nav(u.mustChangePassword ? "/account/password"
        : isSignup ? "/account/keywords" : "/feed");
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container section auth-page">
      <h1 className="t-h1" style={{ marginTop: 0 }}>
        {isSignup ? "회원가입" : "로그인"}
      </h1>

      {isSignup && (
        <div className="notice" style={{ marginBottom: 20 }}>
          <strong>가입하면 관심 키워드 구독을 쓸 수 있습니다.</strong>
          <p className="t-meta" style={{ margin: "6px 0 0", color: "var(--text-secondary)" }}>
            등록한 키워드로 수집된 뉴스·논문을 걸러 <b>내 피드</b>에서 봅니다.
            로그인 없이도 열람·검색·논문 상세는 모두 이용할 수 있습니다.
          </p>
        </div>
      )}

      {err && <div style={{ marginBottom: 16 }}><ErrorBox message={err} /></div>}

      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <label className="t-meta">
          이메일
          <input className="input" type="text" value={email} required
                 placeholder="you@example.com"
                 onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
          {isSignup && (
            <span className="hint">
              인증 메일을 보내지 않습니다. 이메일은 로그인 식별자로만 씁니다.
            </span>
          )}
        </label>

        <label className="t-meta">
          비밀번호
          <input className="input" type="password" value={pw} required
                 onChange={(e) => setPw(e.target.value)}
                 autoComplete={isSignup ? "new-password" : "current-password"} />
          {isSignup && (
            <span className={pwErr ? "hint hint--bad" : "hint"}>
              {pwErr || "10자 이상, 같은 문자를 4번 이상 반복할 수 없습니다."}
            </span>
          )}
        </label>

        {isSignup && (
          <label className="t-meta">
            비밀번호 확인
            <input className="input" type="password" value={pw2} required
                   onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" />
            {mismatch && <span className="hint hint--bad">비밀번호가 일치하지 않습니다.</span>}
          </label>
        )}

        <button className="btn btn--primary" disabled={busy || !!pwErr || !!mismatch}
                style={{ marginTop: 6, height: 46 }}>
          {busy ? "처리 중…" : isSignup ? "가입하기" : "로그인"}
        </button>
      </form>

      <div className="auth-alt">
        {isSignup ? (
          <p>이미 계정이 있으신가요? <Link to="/login">로그인</Link></p>
        ) : (
          <p>계정이 없으신가요? <Link to="/signup">회원가입</Link></p>
        )}
      </div>

      <div className="auth-note t-meta">
        <p>· 소셜 로그인은 제공하지 않습니다. 이메일과 비밀번호만 씁니다.</p>
        <p>· 수집하는 개인정보는 <b>이메일 하나</b>뿐입니다. 탈퇴하면 즉시 삭제됩니다.</p>
        {!isSignup && (
          <p>· 비밀번호를 잊으셨다면 <b>관리자에게 재설정을 요청</b>하세요.
             메일 발송 기능이 없습니다.</p>
        )}
      </div>
    </div>
  );
}
