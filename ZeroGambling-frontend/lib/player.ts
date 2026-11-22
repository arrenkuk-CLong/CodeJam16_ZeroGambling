// Browser-held profile token. The server stores only its hash.
import { queryOptions } from "@tanstack/react-query";
import { getSummary } from "./zg.functions";
import { getWorld } from "./world.functions";

const KEY = "zg.token";
const DEMO_KEY = "zg.demo-pending";

function newToken() {
  return crypto.randomUUID().replace(/-/g, "") + crypto.randomUUID().replace(/-/g, "");
}

export function getToken(): string {
  let t = localStorage.getItem(KEY);
  if (!t) { t = newToken(); localStorage.setItem(KEY, t); }
  return t;
}

export function startNewProfile(demo: boolean) {
  localStorage.setItem(KEY, newToken());
  if (demo) localStorage.setItem(DEMO_KEY, "1"); else localStorage.removeItem(DEMO_KEY);
}

export function newRequestId() {
  return crypto.randomUUID();
}

export const summaryQuery = queryOptions({
  queryKey: ["summary"],
  queryFn: async () => {
    const demo = localStorage.getItem(DEMO_KEY) === "1";
    const res = await getSummary({ data: { token: getToken(), demo } });
    localStorage.removeItem(DEMO_KEY);
    return res;
  },
  staleTime: 5_000,
});

export const worldQuery = queryOptions({
  queryKey: ["world"],
  queryFn: () => getWorld({ data: { token: getToken(), demo: localStorage.getItem(DEMO_KEY) === "1" } }),
  staleTime: 5_000,
});
