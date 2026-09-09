const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export async function getContext(question: string) {
  const url = new URL("/context", API);
  url.searchParams.set("question", question);
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAnswer(question: string) {
  const url = new URL("/answer", API);
  url.searchParams.set("question", question);
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getEval() {
  const res = await fetch(`${API}/eval`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getItem(sku: string) {
  const res = await fetch(`${API}/business/items/${encodeURIComponent(sku)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getItemHistory(sku: string) {
  const res = await fetch(
    `${API}/business/items/${encodeURIComponent(sku)}/history`,
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
