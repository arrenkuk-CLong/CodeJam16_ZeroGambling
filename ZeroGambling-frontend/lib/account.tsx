'use client';
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authClient, type AuthUser } from "./auth-client";
import { claimPlayer } from "./account.functions";
import { getToken, startNewProfile } from "./player";

export type Profile = { id: string; username: string; display_name: string | null; streak_days: number; timezone: string };
type Ctx = { account: AuthUser | null; profile: Profile | null; username: string | null; ready: boolean; refresh: () => Promise<void> };
const AccountCtx = createContext<Ctx>({ account: null, profile: null, username: null, ready: false, refresh: async () => {} });

export const USERNAME_RE = /^[A-Za-z0-9_]{3,30}$/;
export const accountStorageKey = (id: string) => `zerogambling-state:${id}`;

export function AccountProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [account, setAccount] = useState<AuthUser | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [ready, setReady] = useState(false);

  const loadProfile = useCallback(async (u: AuthUser | null) => {
    if (!u) { setProfile(null); return; }
    setProfile(await authClient.profiles.get());
  }, []);

  const link = useCallback(async (u: AuthUser) => {
    const key = accountStorageKey(u.id);
    if (!localStorage.getItem(key)) {
      // First sign-in on this device: adopt this browser's guest progress if it isn't linked yet.
      try { const r = await claimPlayer({ data: { guestToken: getToken() } }); localStorage.setItem(key, JSON.stringify({ linkedAt: Date.now(), adoptedGuest: r.adoptedGuest })); } catch { /* resolver falls back */ }
    }
  }, []);

  useEffect(() => {
    let alive = true;
    authClient.auth.getUser().then(async ({ data }) => {
      if (!alive) return;
      const u = data.user ?? null;
      setAccount(u);
      if (u) await link(u);
      await loadProfile(u);
      setReady(true);
      if (u) qc.resetQueries();
    });
    const { data: sub } = authClient.auth.onAuthStateChange((event, session) => {
      if (!["SIGNED_IN", "SIGNED_OUT", "USER_UPDATED", "PASSWORD_RECOVERY"].includes(event)) return;
      const u = session?.user ?? null;
      setAccount(u);
      setTimeout(async () => {
        if (event === "SIGNED_IN" && u) { await link(u); qc.resetQueries(); }
        await loadProfile(u);
      }, 0);
    });
    return () => { alive = false; sub.subscription.unsubscribe(); };
  }, [qc, link, loadProfile]);

  const refresh = useCallback(() => loadProfile(account), [account, loadProfile]);
  return <AccountCtx.Provider value={{ account, profile, username: profile?.username ?? null, ready, refresh }}>{children}</AccountCtx.Provider>;
}

/** Sign out; if this browser's guest progress moved into the account, give the browser a fresh guest profile. */
export async function signOutAccount(qc: ReturnType<typeof useQueryClient>, accountId?: string) {
  await qc.cancelQueries();
  qc.clear();
  await authClient.auth.signOut();
  if (accountId) {
    try { if (JSON.parse(localStorage.getItem(accountStorageKey(accountId)) ?? "{}").adoptedGuest) startNewProfile(false); } catch { startNewProfile(false); }
  }
}

export const useAccount = () => useContext(AccountCtx);
