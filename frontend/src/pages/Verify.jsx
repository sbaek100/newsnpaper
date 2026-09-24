import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ErrorBox } from "../components/States";

export default function Verify() {
  const [sp] = useSearchParams();
  const { verify } = useAuth();
  const [s, setS] = useState({ loading: true, error: null, msg: null });

  useEffect(() => {
    const t = sp.get("token");
    if (!t) return setS({ loading: false, error: "인증 토큰이 없습니다", msg: null });
    verify(t)
      .then((d) => setS({ loading: false, error: null, msg: d.message }))
      .catch((e) => setS({ loading: false, error: e.message, msg: null }));
  }, [sp, verify]);

  return (
    <div className="container section auth-page">
      <h1 className="t-h1" style={{ marginTop: 0 }}>이메일 인증</h1>
      {s.loading && <div className="skel" style={{ height: 80 }} />}
      {s.error && <>
        <ErrorBox message={s.error} />
        <p className="t-meta auth-note" style={{ marginTop: 16 }}>
          링크가 만료됐다면 <Link to="/signup/resend" style={{ color: "var(--point)" }}>
          인증 메일을 다시 받으세요</Link>.
        </p>
      </>}
      {s.msg && <>
        <div className="notice">{s.msg}</div>
        <p className="t-meta auth-note" style={{ marginTop: 16 }}>
          승인되면 메일로 알려드립니다. <Link to="/login" style={{ color: "var(--point)" }}>로그인</Link>
        </p>
      </>}
    </div>
  );
}
