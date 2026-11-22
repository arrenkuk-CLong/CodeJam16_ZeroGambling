'use client';
import { useState } from "react";
import { useNavigate } from "@/lib/router";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { authClient } from "@/lib/auth-client";
import { accountStorageKey, signOutAccount, useAccount, USERNAME_RE } from "@/lib/account";
import { deleteOwnAccount } from "@/lib/account.functions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";

function Field({ id, label, type = "text", value, onChange, autoComplete }: { id: string; label: string; type?: string; value: string; onChange: (v: string) => void; autoComplete?: string }) {
  return <div className="flex-1"><Label htmlFor={id}>{label}</Label><Input id={id} type={type} value={value} autoComplete={autoComplete} onChange={(e) => onChange(e.target.value)} /></div>;
}

export function AccountFields() {
  const { account, profile, refresh } = useAccount();
  const qc = useQueryClient(); const navigate = useNavigate();
  const [username, setUsername] = useState(""); const [email, setEmail] = useState("");
  const [current, setCurrent] = useState(""); const [next, setNext] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  if (!account) return null;

  const run = async (key: string, fn: () => Promise<void>) => { setBusy(key); try { await fn(); } catch (e) { toast.error(e instanceof Error ? e.message : "Something went wrong"); } finally { setBusy(null); } };
  const saveUsername = () => run("u", async () => {
    const clean = username.trim();
    if (!USERNAME_RE.test(clean)) throw new Error("Use 3–30 letters, numbers or underscores.");
    const { error } = await authClient.profiles.update({ username: clean, display_name: clean });
    if (error?.code === "23505") throw new Error("That username is already taken.");
    if (error) throw error;
    await refresh(); setUsername(""); toast.success("Username updated.");
  });
  const saveEmail = () => run("e", async () => {
    const { error } = await authClient.auth.updateUser({ email: email.trim() }, { emailRedirectTo: `${window.location.origin}/auth` });
    if (error) throw error;
    setEmail(""); toast.success("Email updated. Use it the next time you sign in.");
  });
  const savePassword = () => run("p", async () => {
    if (next.length < 8) throw new Error("New password needs at least 8 characters.");
    const { error } = await authClient.auth.updateUser({ password: next, current_password: current });
    if (error) throw error;
    setCurrent(""); setNext(""); toast.success("Password changed.");
  });
  const signOut = async () => { await signOutAccount(qc, account.id); navigate({ to: "/auth", replace: true }); };
  const remove = () => run("d", async () => {
    await deleteOwnAccount();
    localStorage.removeItem(accountStorageKey(account.id));
    await signOutAccount(qc); navigate({ to: "/auth", replace: true });
    toast.success("Your account and its history were deleted.");
  });

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
      <h2 className="text-2xl font-bold">Account</h2>
      <p className="mt-1 text-sm text-muted-foreground">Signed in as <span className="font-semibold text-foreground">{profile?.username ?? "…"}</span> · {account.email}</p>
      <div className="mt-5 space-y-5">
        <div className="flex flex-wrap items-end gap-2"><Field id="acc-username" label="New username" value={username} onChange={setUsername} autoComplete="username" /><Button disabled={busy === "u" || !username} onClick={saveUsername}>Update username</Button></div>
        <div className="flex flex-wrap items-end gap-2"><Field id="acc-email" label="New email" type="email" value={email} onChange={setEmail} autoComplete="email" /><Button disabled={busy === "e" || !email} onClick={saveEmail}>Update email</Button></div>
        <div className="flex flex-wrap items-end gap-2"><Field id="acc-cur" label="Current password" type="password" value={current} onChange={setCurrent} autoComplete="current-password" /><Field id="acc-new" label="New password" type="password" value={next} onChange={setNext} autoComplete="new-password" /><Button disabled={busy === "p" || !current || !next} onClick={savePassword}>Change password</Button></div>
        <div className="flex flex-wrap gap-2 border-t border-border/60 pt-5">
          <Button variant="outline" onClick={signOut}>Sign out</Button>
          <AlertDialog>
            <AlertDialogTrigger asChild><Button variant="destructive" disabled={busy === "d"}>Delete account</Button></AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader><AlertDialogTitle>Delete your account?</AlertDialogTitle><AlertDialogDescription>This permanently removes your account, gems, skills, inventory, trophies and history. It can't be undone.</AlertDialogDescription></AlertDialogHeader>
              <AlertDialogFooter><AlertDialogCancel>Keep account</AlertDialogCancel><AlertDialogAction onClick={remove}>Delete forever</AlertDialogAction></AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>
    </section>
  );
}
