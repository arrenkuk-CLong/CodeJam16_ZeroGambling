'use client';
import { useNavigate } from "@/lib/router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { authClient } from "@/lib/auth-client";
import { useAccount, USERNAME_RE } from "@/lib/account";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const signUpSchema = z.object({
  email: z.string().trim().email("Enter a valid email").max(255),
  username: z.string().trim().regex(USERNAME_RE, "3–30 letters, numbers or underscores"),
  password: z.string().min(8, "At least 8 characters").max(72),
});

export function AuthPage() {
  const [mode, setMode] = useState<"signin" | "signup" | "forgot">("signin");
  const [email, setEmail] = useState(""); const [username, setUsername] = useState(""); const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const { account } = useAccount(); const navigate = useNavigate();
  useEffect(() => { if (account) navigate({ to: "/profile", replace: true }); }, [account, navigate]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true);
    try {
      if (mode === "signup") {
        const parsed = signUpSchema.safeParse({ email, username, password });
        if (!parsed.success) throw new Error(parsed.error.issues[0]?.message ?? "Check the form");
        const { error } = await authClient.auth.signUp({ email: parsed.data.email, password: parsed.data.password, options: { emailRedirectTo: window.location.origin, data: { username: parsed.data.username } } });
        if (error) throw error;
        toast.success("Account created. Your current progress has been saved to it.");
      } else if (mode === "signin") {
        const { error } = await authClient.auth.signInWithPassword({ email: email.trim(), password });
        if (error) throw error;
      } else {
        const { error } = await authClient.auth.resetPasswordForEmail(email.trim(), { redirectTo: `${window.location.origin}/reset-password` });
        if (error) throw error;
        toast.success("If that email has an account, a reset link is on its way.");
      }
    } catch (err) { toast.error(err instanceof Error ? err.message : "Something went wrong"); }
    finally { setBusy(false); }
  };

  return (
    <div className="mx-auto max-w-md space-y-6">
      <header>
        <p className="font-mono text-xs uppercase tracking-widest text-primary">Account</p>
        <h1 className="mt-2 text-4xl font-extrabold">{mode === "signup" ? "Create your account" : mode === "signin" ? "Welcome back" : "Reset your password"}</h1>
        <p className="mt-2 text-sm text-muted-foreground">Playing as a guest works too. An account keeps your gems, skills and history safe across devices — progress from this browser moves into your account the first time you sign in.</p>
      </header>
      <form onSubmit={submit} className="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-card">
        <div><Label htmlFor="email">Email</Label><Input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
        {mode === "signup" && <div><Label htmlFor="username">Username</Label><Input id="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required /></div>}
        {mode !== "forgot" && <div><Label htmlFor="password">Password</Label><Input id="password" type="password" autoComplete={mode === "signup" ? "new-password" : "current-password"} value={password} onChange={(e) => setPassword(e.target.value)} required /></div>}
        <Button type="submit" className="w-full" disabled={busy}>{busy ? "Please wait…" : mode === "signup" ? "Create account" : mode === "signin" ? "Sign in" : "Send reset link"}</Button>
      </form>
      <div className="flex flex-wrap justify-between gap-2 text-sm">
        {mode !== "signin" && <button className="text-primary underline" onClick={() => setMode("signin")}>I have an account</button>}
        {mode !== "signup" && <button className="text-primary underline" onClick={() => setMode("signup")}>Create an account</button>}
        {mode !== "forgot" && <button className="text-muted-foreground underline" onClick={() => setMode("forgot")}>Forgot password?</button>}
      </div>
    </div>
  );
}
