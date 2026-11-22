'use client';
import { useQueryClient } from "@tanstack/react-query";
import { useQuery } from "@/lib/query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Bell, Eye, ShieldCheck, Volume2 } from "lucide-react";
import { savePreferences } from "@/lib/world.functions";
import { getToken, worldQuery } from "@/lib/player";
import type { Preferences, WorldData } from "@/lib/world-types";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { AccountFields } from "@/components/zg/AccountFields";

const fields: { key: keyof Preferences; title: string; description: string; group: "experience" | "staking" }[] = [
  { key:"reducedMotion",title:"Reduced motion",description:"Minimise wheel, card and course animations.",group:"experience" },
  { key:"sound",title:"Sound",description:"Allow challenge tones and game audio.",group:"experience" },
  { key:"sessionReminders",title:"Session reminders",description:"Show a gentle reminder after extended play.",group:"experience" },
  { key:"confirmStakes",title:"Confirm every stake",description:"Ask before committing gems or another asset.",group:"staking" },
  { key:"allowSkillStakes",title:"Skill progress stakes",description:"Allow rollback wagers on current skill levels.",group:"staking" },
  { key:"allowEquipmentStakes",title:"Equipment stakes",description:"Allow equipment to be lost at the casino.",group:"staking" },
  { key:"allowSlideStakes",title:"Glider level stakes",description:"Allow staking slide-game glider levels; a loss lowers your glider level.",group:"staking" },
  { key:"allowLogStakes",title:"Entire-log stakes",description:"Enable the highest-risk wager. Off by default; trophies and loss records always survive.",group:"staking" },
];
export function Settings() {
  const { data }=useQuery(worldQuery); const world=data as WorldData|undefined; const [prefs,setPrefs]=useState<Preferences|null>(null); const [busy,setBusy]=useState(false); const qc=useQueryClient();
  useEffect(()=>{if(world?.preferences&&!prefs)setPrefs(world.preferences);},[world,prefs]);
  if(!prefs)return <p className="text-muted-foreground">Loading preferences…</p>;
  const save=async()=>{setBusy(true);try{await savePreferences({data:{token:getToken(),preferences:prefs}});qc.invalidateQueries({queryKey:["world"]});toast.success("Preferences saved.");}catch(e){toast.error(e instanceof Error?e.message:"Could not save");}finally{setBusy(false);}};
  const group=(name:"experience"|"staking")=><section className="rounded-2xl border border-border bg-card p-5 shadow-card"><h2 className="flex items-center gap-2 text-2xl font-bold">{name==="experience"?<><Eye/> Experience</>:<><ShieldCheck/> Stake permissions</>}</h2><div className="mt-4 divide-y divide-border/60">{fields.filter((f)=>f.group===name).map((f)=><div key={f.key} className="flex items-center justify-between gap-5 py-4"><div><Label htmlFor={f.key} className="text-base font-semibold">{f.title}</Label><p className="mt-1 text-sm text-muted-foreground">{f.description}</p></div><Switch id={f.key} checked={prefs[f.key]} onCheckedChange={(v)=>setPrefs({...prefs,[f.key]:v})}/></div>)}</div></section>;
  return <div className="mx-auto max-w-3xl space-y-6"><header><p className="font-mono text-xs uppercase tracking-widest text-primary">Your choices · saved to this profile</p><h1 className="mt-2 text-4xl font-extrabold">Permissions & preferences</h1><p className="mt-2 text-muted-foreground">Permissions gate the stake builder on the server as well as in the interface. Existing history is never deleted here.</p></header><AccountFields />{group("experience")}{group("staking")}<div className="flex items-center gap-3"><Button size="lg" disabled={busy} onClick={save}>{busy?"Saving…":"Save preferences"}</Button><span className="inline-flex items-center gap-1 text-xs text-muted-foreground"><Bell className="size-3"/> Changes apply to your next wager.</span><Volume2 className="size-4 text-muted-foreground"/></div></div>;
}
