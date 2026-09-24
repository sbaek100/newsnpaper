import { createContext, useCallback, useContext, useEffect, useState } from "react";

const Ctx = createContext(null);

// 🔴 액세스 토큰을 localStorage 에 두지 않는다. 메모리에만 둔다 (PRD-01 FR-13).
//    리프레시는 httpOnly 쿠키가 처리하므로 새로고침해도 세션이 복구된다.
let accessToken = null;
export const getToken = () => accessToken;

async function call(path, { method = "GET", body, auth = false } = {}) {
  const headers = { "content-type": "application/json" };
  if (auth && accessToken) headers.authorization = `Bearer ${accessToken}`;
  const r = await fetch("/api" + path, {
    method, headers, body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : (d?.[0]?.msg || `요청 실패 (${r.status})`));
  }
  return data;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  // 새로고침 시 쿠키로 세션 복구
  useEffect(() => {
    call("/auth/refresh", { method: "POST" })
      .then((d) => { accessToken = d.accessToken; setUser(d.user); })
      .catch(() => { accessToken = null; setUser(null); })
      .finally(() => setReady(true));
  }, []);

  const login = useCallback(async (email, password) => {
    const d = await call("/auth/login", { method: "POST", body: { email, password } });
    accessToken = d.accessToken; setUser(d.user); return d.user;
  }, []);

  // 가입은 바로 로그인되지 않는다 — 이메일 인증 + 관리자 승인을 거친다 (PRD-01 §5.1)
  const signup = useCallback(
    (email, password) => call("/auth/signup", { method: "POST", body: { email, password } }),
    []);

  const resend = useCallback(
    (email, password) => call("/auth/resend", { method: "POST", body: { email, password } }),
    []);

  const verify = useCallback(
    (token) => call(`/auth/verify?token=${encodeURIComponent(token)}`, { method: "POST" }),
    []);

  const logout = useCallback(async () => {
    await call("/auth/logout", { method: "POST" }).catch(() => {});
    accessToken = null; setUser(null);
  }, []);

  const authed = useCallback(async (path, opts) => {
    try {
      return await call(path, { ...opts, auth: true });
    } catch (e) {
      // 액세스 토큰 만료면 1회 재발급 후 재시도
      if (/만료|401/.test(e.message)) {
        const d = await call("/auth/refresh", { method: "POST" });
        accessToken = d.accessToken; setUser(d.user);
        return call(path, { ...opts, auth: true });
      }
      throw e;
    }
  }, []);

  return (
    <Ctx.Provider value={{ user, setUser, ready, login, signup, resend, verify, logout, authed }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
