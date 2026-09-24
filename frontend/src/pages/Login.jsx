import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ErrorBox } from "../components/States";

export default function Login({ mode = "login" }) {
  const isSignup = mode === "signup";
  const { login, signup } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      const u = await (isSignup ? signup(email, pw) : login(email, pw));
      nav(u.mustChangePassword ? "/account/password" : "/feed");
    } catch (e2) { setErr(e2.message); } finally { setBusy(false); }
  }

  return (
    <div className="container section" style={{ maxWidth: 420 }}>
      <h1 className="t-h1" style={{ marginTop: 0 }}>{isSignup ? "회원가입" : "로그인"}</h1>
      {err && <div style={{ marginBottom: 16 }}><ErrorBox message={err} /></div>}
      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <label className="t-meta">이메일
          <input className="input" type="text" value={email} required
                 onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
        </label>
        <label className="t-meta">비밀번호
          <input className="input" type="password" value={pw} required
                 onChange={(e) => setPw(e.target.value)}
                 autoComplete={isSignup ? "new-password" : "current-password"} />
        </label>
        {isSignup && <p className="t-meta" style={{ color: "var(--text-tertiary)", margin: 0 }}>
          10자 이상, 같은 문자를 4번 이상 반복할 수 없습니다.
        </p>}
        <button className="btn btn--primary" disabled={busy} style={{ marginTop: 8 }}>
          {busy ? "처리 중…" : (isSignup ? "가입하기" : "로그인")}
        </button>
      </form>
      <p className="t-meta" style={{ color: "var(--text-tertiary)", marginTop: 20 }}>
        {isSignup ? <>이미 계정이 있으신가요? <Link to="/login" style={{ color: "var(--point)" }}>로그인</Link></>
                  : <>계정이 없으신가요? <Link to="/signup" style={{ color: "var(--point)" }}>회원가입</Link></>}
      </p>
      {!isSignup && <p className="t-meta" style={{ color: "var(--text-tertiary)" }}>
        비밀번호를 잊으셨다면 관리자에게 재설정을 요청하세요. (메일 발송 기능 없음)
      </p>}
    </div>
  );
}
