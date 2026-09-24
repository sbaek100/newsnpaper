import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ErrorBox } from "../components/States";

export function Keywords() {
  const { authed } = useAuth();
  const [kws, setKws] = useState([]);
  const [max, setMax] = useState(20);
  const [input, setInput] = useState("");
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    authed("/me/keywords").then((d) => { setKws(d.keywords); setMax(d.max); })
      .catch((e) => setErr(e.message));
  }, [authed]);

  function add(e) {
    e.preventDefault();
    const k = input.trim();
    if (k.length < 2 || kws.includes(k) || kws.length >= max) return;
    setKws([...kws, k]); setInput("");
  }

  async function save() {
    setErr(null); setMsg(null);
    try {
      const d = await authed("/me/keywords", { method: "PUT", body: { keywords: kws } });
      setKws(d.keywords); setMsg("저장했습니다");
    } catch (e) { setErr(e.message); }
  }

  return (
    <div className="container section" style={{ maxWidth: 560 }}>
      <h1 className="t-h1" style={{ marginTop: 0 }}>관심 키워드</h1>
      <p className="t-meta" style={{ color: "var(--text-tertiary)" }}>
        {kws.length} / {max}개. 저장된 항목 중에서 이 키워드로 걸러 보여줍니다.
      </p>
      {err && <div style={{ margin: "12px 0" }}><ErrorBox message={err} /></div>}
      {msg && <div className="notice" style={{ margin: "12px 0" }}>{msg}</div>}

      <form onSubmit={add} style={{ display: "flex", gap: 8, margin: "16px 0" }}>
        <input className="input" value={input} onChange={(e) => setInput(e.target.value)}
               placeholder="키워드 (2글자 이상)" style={{ flex: 1 }} />
        <button className="btn" disabled={kws.length >= max}>추가</button>
      </form>

      <div className="filters">
        {kws.map((k) => (
          <button key={k} className="chip on" onClick={() => setKws(kws.filter((x) => x !== k))}>
            {k} ✕
          </button>
        ))}
        {!kws.length && <span className="t-meta" style={{ color: "var(--text-disabled)" }}>
          등록된 키워드가 없습니다</span>}
      </div>

      <button className="btn btn--primary" onClick={save} style={{ marginTop: 20 }}>저장</button>
    </div>
  );
}

export function ChangePassword() {
  const { authed, setUser, user } = useAuth();
  const nav = useNavigate();
  const [cur, setCur] = useState("");
  const [nw, setNw] = useState("");
  const [err, setErr] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    try {
      await authed("/auth/password", { method: "POST",
        body: { currentPassword: cur, newPassword: nw } });
      setUser({ ...user, mustChangePassword: false });
      nav("/login");
    } catch (e2) { setErr(e2.message); }
  }

  return (
    <div className="container section" style={{ maxWidth: 420 }}>
      <h1 className="t-h1" style={{ marginTop: 0 }}>비밀번호 변경</h1>
      {user?.mustChangePassword && (
        <div className="notice" style={{ marginBottom: 16 }}>
          초기 비밀번호는 반드시 변경해야 합니다.
        </div>
      )}
      {err && <div style={{ marginBottom: 16 }}><ErrorBox message={err} /></div>}
      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <label className="t-meta">현재 비밀번호
          <input className="input" type="password" value={cur} required
                 onChange={(e) => setCur(e.target.value)} />
        </label>
        <label className="t-meta">새 비밀번호
          <input className="input" type="password" value={nw} required
                 onChange={(e) => setNw(e.target.value)} />
        </label>
        <p className="t-meta" style={{ color: "var(--text-tertiary)", margin: 0 }}>
          10자 이상. 변경하면 모든 기기에서 로그아웃됩니다.
        </p>
        <button className="btn btn--primary" style={{ marginTop: 8 }}>변경</button>
      </form>
    </div>
  );
}
