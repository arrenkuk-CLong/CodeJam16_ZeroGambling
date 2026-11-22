// Accounts on Django instead of Supabase. It keeps the small part of the supabase-js API that Lovable's pages
// use (auth.signUp / signInWithPassword / resetPasswordForEmail / updateUser / signOut / getUser /
// onAuthStateChange, plus the profile row), returning { error } the same way, so those pages barely change.
import { ApiError, call, readSession, writeSession, type AuthUser, type StoredSession } from "./api";

export type { AuthUser };
export type AuthEvent = "SIGNED_IN" | "SIGNED_OUT" | "USER_UPDATED" | "PASSWORD_RECOVERY";
export interface AccountProfileRow { id: string; username: string; display_name: string | null; streak_days: number; timezone: string }
type Listener = (event: AuthEvent, session: { user: AuthUser } | null) => void;
type SessionResponse = { token: string; account: AuthUser; profile: AccountProfileRow | null };

/** Same shape as Supabase's AuthError: an Error with an optional code (23505 = username taken). */
export class AuthError extends Error {
  constructor(message: string, public code?: string) { super(message); }
}

const listeners = new Set<Listener>();
let recovery: { uid: string; token: string } | null = null;

function emit(event: AuthEvent) {
  const s = readSession();
  for (const l of listeners) l(event, s ? { user: s.user } : null);
}

async function attempt<T>(fn: () => Promise<T>): Promise<{ data: T | null; error: AuthError | null }> {
  try { return { data: await fn(), error: null }; }
  catch (e) { return { data: null, error: new AuthError(e instanceof Error ? e.message : "Something went wrong", e instanceof ApiError ? e.code : undefined) }; }
}

function signedIn(r: SessionResponse) {
  writeSession({ token: r.token, user: r.account } satisfies StoredSession);
  emit("SIGNED_IN");
}

// A password-reset email links to /reset-password#type=recovery&uid=…&token=… (like Supabase's recovery link).
if (typeof window !== "undefined" && window.location.hash.includes("type=recovery")) {
  const p = new URLSearchParams(window.location.hash.slice(1));
  const uid = p.get("uid"), token = p.get("token");
  if (uid && token) {
    recovery = { uid, token };
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    setTimeout(() => emit("PASSWORD_RECOVERY"), 0);
  }
}

export const authClient = {
  auth: {
    async getUser(): Promise<{ data: { user: AuthUser | null } }> {
      const s = readSession();
      if (!s) return { data: { user: null } };
      try {
        const me = await call<{ account: AuthUser | null }>("auth/me", undefined, "GET");
        if (!me.account) { writeSession(null); return { data: { user: null } }; }
        writeSession({ ...s, user: me.account });
        return { data: { user: me.account } };
      } catch { return { data: { user: s.user } }; } // offline: trust the saved session
    },
    onAuthStateChange(cb: Listener) {
      listeners.add(cb);
      return { data: { subscription: { unsubscribe: () => { listeners.delete(cb); } } } };
    },
    async signUp({ email, password, options }: { email: string; password: string; options?: { emailRedirectTo?: string; data?: { username?: string } } }) {
      const r = await attempt(() => call<SessionResponse>("auth/signup", { email, password, username: options?.data?.username }));
      if (r.data) signedIn(r.data);
      return { error: r.error };
    },
    async signInWithPassword({ email, password }: { email: string; password: string }) {
      const r = await attempt(() => call<SessionResponse>("auth/signin", { email, password }));
      if (r.data) signedIn(r.data);
      return { error: r.error };
    },
    async resetPasswordForEmail(email: string, opts?: { redirectTo?: string }) {
      const r = await attempt(() => call("auth/recover", { email, redirectTo: opts?.redirectTo }));
      return { error: r.error };
    },
    /** Change email or password. After a reset link, setting a password also signs you in. */
    // The second argument (Supabase's emailRedirectTo) is accepted for compatibility; Django changes the email directly.
    async updateUser(attrs: { email?: string; password?: string; current_password?: string }, ...compat: [{ emailRedirectTo?: string }?]) {
      void compat;
      if (recovery && attrs.password && !readSession()) {
        const r = await attempt(() => call<SessionResponse>("auth/recover/confirm", { ...recovery, password: attrs.password }));
        if (r.data) { recovery = null; signedIn(r.data); }
        return { error: r.error };
      }
      if (!readSession()) return { error: new AuthError("Your reset link has expired. Ask for a new one.") };
      const r = await attempt(() => call<{ account: AuthUser }>("auth/user", { email: attrs.email, password: attrs.password, currentPassword: attrs.current_password }));
      if (r.data) { const s = readSession(); if (s) writeSession({ ...s, user: r.data.account }); emit("USER_UPDATED"); }
      return { error: r.error };
    },
    async signOut() {
      await attempt(() => call("auth/signout", {}));
      writeSession(null);
      emit("SIGNED_OUT");
      return { error: null };
    },
  },
  profiles: {
    async get(): Promise<AccountProfileRow | null> {
      const r = await attempt(() => call<{ profile: AccountProfileRow | null }>("auth/me", undefined, "GET"));
      return r.data?.profile ?? null;
    },
    async update(row: { username: string; display_name?: string }) {
      const r = await attempt(() => call<{ profile: AccountProfileRow }>("auth/profile", { username: row.username }));
      return { error: r.error };
    },
  },
};
