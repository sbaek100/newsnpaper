// 상대 경로만 쓴다 — Caddy 가 단일 오리진으로 묶는다 (CORS 없음).
const base = "/api";

async function get(path, params) {
  const qs = params ? "?" + new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
  ) : "";
  const r = await fetch(base + path + qs);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail || `요청 실패 (${r.status})`);
  }
  return r.json();
}

export const api = {
  main: () => get("/main"),
  contents: (p) => get("/contents", p),
  paper: (id) => get(`/papers/${id}`),
};

export function fmtDate(s) {
  if (!s) return "";
  const d = new Date(s);
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`;
}

// 기사 id 해시로 placeholder 를 고정한다. 리렌더마다 바뀌면 안 된다 (F-16).
export function placeholderFor(id) {
  return `/placeholders/0${(Number(id) % 6) + 1}.svg`;
}

export const CATEGORY_LABEL = {
  international: "국제",
  domestic: "국내",
  paper: "논문",
};
