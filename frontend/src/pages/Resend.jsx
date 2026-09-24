import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ErrorBox } from "../components/States";

export default function Resend() {
  const { resend } = useAuth();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [done, setDone] = useState(false);
  const [err, setErr] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    try { await resend(email, pw); setDone(true); } catch (e2) { setErr(e2.message); }
  }

  if (done) return (
    <div className="container section auth-page">
      <h1 className="t-h1" style={{ marginTop: 0 }}>인증 메일 재발송</h1>
      <div className="notice">
        인증 대기 중인 계정이라면 메일을 다시 보냈습니다. 받은편지함을 확인해 주세요.
      </div>
      <p className="t-meta auth-note" style={{ marginTop: 16 }}>
        <Link to="/login" style={{ color: "var(--point)" }}>로그인으로</Link>
      </p>
    </div>
  );

  return (
    <div className="container section auth-page">
      <h1 className="t-h1" style={{ marginTop: 0 }}>인증 메일 재발송</h1>
      <p className="t-meta" style={{ color: "var(--text-secondary)" }}>
        가입할 때 쓴 이메일과 비밀번호를 입력하세요.
      </p>
      {err && <div style={{ margin: "16px 0" }}><ErrorBox message={err} /></div>}
      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <label className="t-meta">이메일
          <input className="input" type="text" value={email} required
                 onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="t-meta">비밀번호
          <input className="input" type="password" value={pw} required
                 onChange={(e) => setPw(e.target.value)} />
        </label>
        <button className="btn btn--primary" style={{ marginTop: 6, height: 46 }}>
          다시 보내기
        </button>
      </form>
    </div>
  );
}
