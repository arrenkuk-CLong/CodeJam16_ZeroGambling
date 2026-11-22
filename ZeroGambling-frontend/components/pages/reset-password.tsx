'use client';
import { useNavigate } from "@/lib/router";
import { useState } from "react";
import { toast } from "sonner";
import { authClient } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function ResetPassword() {
  const [password, setPassword] = useState(""); const [busy, setBusy] = useState(false); const navigate = useNavigate();
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) { toast.error("At least 8 characters"); return; }
    setBusy(true);
    const { error } = await authClient.auth.updateUser({ password });
    setBusy(false);
    if (error) { toast.error(error.message); return; }
    toast.success("Password updated."); navigate({ to: "/profile", replace: true });
  };
  return (
    <form onSubmit={submit} className="mx-auto max-w-md space-y-4 rounded-2xl border border-border bg-card p-5 shadow-card">
      <h1 className="text-3xl font-extrabold">Choose a new password</h1>
      <div><Label htmlFor="np">New password</Label><Input id="np" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
      <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save password"}</Button>
    </form>
  );
}
