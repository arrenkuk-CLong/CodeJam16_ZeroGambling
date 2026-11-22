import { useMemo, useState } from "react";
import { CATALOG } from "@/lib/catalog";
import { equipmentStakeValue, gliderStakeValue, logStakeValue, skillStakeValue, type AssetType } from "@/lib/economy-assets";
import type { AssetInput, WorldData } from "@/lib/world-types";
import type { Summary } from "@/lib/engine/service-types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { gliderInvested, reachM, steerPct } from "@/lib/engine/slide-balance";
import { formatCents, parseCents, type CasinoVariant } from "@/lib/casino";

export function estimateAssetCents(summary: Summary, world: WorldData, value: AssetInput): number {
  const gliderLevel = world.game.gliderLevel ?? 0;
  if (value.type === "gems") return parseCents(value.amount) ?? 0;
  if (value.type === "skill") {
    const skill = summary.mastery.find((m) => m.gameId === value.gameId);
    return (skill ? skillStakeValue(skill.level, value.rollbackLevel) : 0) * 100;
  }
  if (value.type === "equipment") {
    const item = world.inventory.find((i) => i.id === value.itemId);
    return (item ? equipmentStakeValue(item.key === "glider" ? gliderInvested(item.level) : item.price) : 0) * 100;
  }
  if (value.type === "glider") return gliderStakeValue(gliderLevel, value.levels) * 100;
  return logStakeValue(summary.mastery.map((m) => m.level), summary.player.lifetimePasses) * 100;
}

export function StakeBuilder({ summary, world, value, onChange: setValue, disabled, variant, undoable = false }: { summary: Summary; world: WorldData; value: AssetInput; onChange: (a: AssetInput) => void; disabled: boolean; variant: CasinoVariant; undoable?: boolean }) {
  // Earlier stakes, so a single-stake game can take back a change before the bet is committed.
  const [history, setHistory] = useState<AssetInput[]>([]);
  const onChange = (next: AssetInput) => { setHistory((h) => [...h.slice(-49), value]); setValue(next); };
  const undo = () => { const prev = history[history.length - 1]; if (!prev) return; setHistory((h) => h.slice(0, -1)); setValue(prev); };
  const equipment = world.inventory.filter((i) => i.kind === "equipment");
  const gliderLevel = world.game.gliderLevel ?? 0;
  const skills = summary.mastery.filter((m) => m.level > 1);
  const type = value.type;
  const skill = value.type === "skill" ? skills.find((m) => m.gameId === value.gameId) ?? skills[0] : skills[0];
  const item = value.type === "equipment" ? equipment.find((i) => i.id === value.itemId) ?? equipment[0] : equipment[0];
  const estimateCents = useMemo(() => {
    if (value.type === "gems") return parseCents(value.amount) ?? 0;
    if (value.type === "skill") return (skill ? skillStakeValue(skill.level, value.rollbackLevel) : 0) * 100;
    if (value.type === "equipment") return (item ? equipmentStakeValue(item.key === "glider" ? gliderInvested(item.level) : item.price) : 0) * 100;
    if (value.type === "glider") return gliderStakeValue(gliderLevel, value.levels) * 100;
    return logStakeValue(summary.mastery.map((m) => m.level), summary.player.lifetimePasses) * 100;
  }, [value, skill, item, gliderLevel, summary]);
  const selectType = (next: AssetType) => {
    if (next === "gems") onChange({ type: "gems", amount: "5.00" });
    if (next === "skill" && skill) onChange({ type: "skill", gameId: skill.gameId, rollbackLevel: Math.max(1, skill.level - 1) });
    if (next === "equipment" && item) onChange({ type: "equipment", itemId: item.id });
    if (next === "glider") onChange({ type: "glider", levels: 1 });
    if (next === "log") onChange({ type: "log" });
  };
  const available: { id: AssetType; label: string; show: boolean }[] = [
    { id: "gems", label: "Gems", show: true }, { id: "skill", label: "Skill", show: variant.assetStakes && skills.length > 0 && world.preferences.allowSkillStakes },
    { id: "equipment", label: "Equipment", show: variant.assetStakes && equipment.length > 0 && world.preferences.allowEquipmentStakes },
    { id: "glider", label: "Glider levels", show: variant.assetStakes && gliderLevel > 0 && world.preferences.allowSlideStakes },
    { id: "log", label: "Entire log", show: variant.assetStakes && world.preferences.allowLogStakes && summary.mastery.length > 0 },
  ];
  const gemCents = value.type === "gems" ? parseCents(value.amount) ?? 0 : 0;
  return <div className="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-card">
    <div><h2 className="text-xl font-bold">Stake builder</h2><p className="text-xs text-muted-foreground">Exact decimal credits. Non-gem estimates price risk only and can never be sold or converted directly.</p></div>
    <div className="flex flex-wrap gap-2">{available.filter((a) => a.show).map((a) => <Button key={a.id} size="sm" variant={type === a.id ? "default" : "outline"} disabled={disabled} onClick={() => selectType(a.id)}>{a.label}</Button>)}</div>
    {!variant.assetStakes && <p className="rounded-xl bg-muted p-3 text-xs text-muted-foreground">This variant uses gem credits only because it can require partial returns or additional wagers.</p>}
    {value.type === "gems" && <div><div className="flex justify-between"><Label htmlFor="gem-stake">Gem stake</Label><span className="font-mono text-gem">{formatCents(gemCents)}</span></div><Input id="gem-stake" type="text" inputMode="decimal" placeholder="0.00" value={value.amount} disabled={disabled} onChange={(e) => onChange({ type: "gems", amount: e.target.value })} className="mt-2 font-mono"/><Slider className="mt-4" value={[Math.min(Math.floor(gemCents / 100), Math.max(1, summary.player.gems))]} min={1} max={Math.max(1, Math.min(1000, summary.player.gems))} onValueChange={(v) => onChange({ type: "gems", amount: `${v[0] ?? 1}.00` })} disabled={disabled || summary.player.gems < 1}/><p className="mt-2 text-xs text-muted-foreground">Available {formatCents(summary.player.gemCents)} · table step and exact-paying rules are checked before commit.</p>{undoable && <div className="mt-3 flex gap-2"><Button size="sm" variant="outline" disabled={disabled || !history.length} onClick={undo}>Undo stake change</Button><Button size="sm" variant="outline" disabled={disabled || gemCents === 0} onClick={() => onChange({ type: "gems", amount: "0.00" })}>Clear stake</Button></div>}</div>}
    {value.type === "skill" && skill && <div className="space-y-3"><Label htmlFor="skill-select">Skill tree</Label><select id="skill-select" className="h-10 w-full rounded-md border border-input bg-background px-3" value={value.gameId} disabled={disabled} onChange={(e) => { const m=skills.find((x)=>x.gameId===Number(e.target.value))!; onChange({type:"skill",gameId:m.gameId,rollbackLevel:Math.max(1,m.level-1)}); }}>{skills.map((m) => <option key={m.gameId} value={m.gameId}>{CATALOG.find((g) => g.id === m.gameId)?.name} · Lv {m.level}</option>)}</select><Label htmlFor="rollback">Rollback to level {value.rollbackLevel}</Label><Slider id="rollback" min={1} max={skill.level - 1} step={1} value={[value.rollbackLevel]} disabled={disabled} onValueChange={(v) => onChange({ type: "skill", gameId: skill.gameId, rollbackLevel: v[0] ?? 1 })}/><p className="text-xs text-muted-foreground">A loss moves this skill from level {skill.level} to {value.rollbackLevel}. Trophies are never at risk.</p></div>}
    {value.type === "equipment" && item && <div><Label htmlFor="item-select">Equipment item</Label><select id="item-select" className="mt-2 h-10 w-full rounded-md border border-input bg-background px-3" value={value.itemId} disabled={disabled} onChange={(e) => onChange({ type: "equipment", itemId: e.target.value })}>{equipment.map((i) => <option key={i.id} value={i.id}>{i.symbol} {i.name}{i.key === "glider" ? ` Lv ${i.level}` : ""} · shop {i.key === "glider" ? gliderInvested(i.level) : i.price}</option>)}</select><p className="mt-2 text-xs text-muted-foreground">A loss permanently removes this item. A win keeps it and pays the named gem prize.</p></div>}
    {value.type === "glider" && <div><Label htmlFor="glider-levels">Stake {value.levels} glider level{value.levels === 1 ? "" : "s"}</Label><Slider id="glider-levels" className="mt-3" min={1} max={Math.max(1, gliderLevel)} step={1} value={[value.levels]} disabled={disabled} onValueChange={(v) => onChange({ type: "glider", levels: v[0] ?? 1 })}/><p className="mt-2 text-xs text-muted-foreground">A loss drops your glider from level {gliderLevel} to {gliderLevel - value.levels} (steering {steerPct(gliderLevel)}% → {steerPct(gliderLevel - value.levels)}%, expected reach {Math.round(reachM(gliderLevel))} m → {Math.round(reachM(gliderLevel - value.levels))} m). You keep the glider itself.</p></div>}
    {value.type === "log" && <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-3 text-xs"><p className="font-semibold text-destructive">Full-log risk</p><p className="mt-1 text-muted-foreground">A loss clears active completion history and resets every open skill to level 1. A permanent loss record remains. Trophies stay intact.</p></div>}
    <div className="flex items-center justify-between rounded-xl bg-muted p-3 text-sm"><span className="text-muted-foreground">Estimated stake value</span><span className="font-mono text-lg text-gem">{formatCents(estimateCents)} gems</span></div>
  </div>;
}
