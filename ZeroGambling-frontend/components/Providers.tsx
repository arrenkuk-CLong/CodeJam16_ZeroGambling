'use client';
// Everything Lovable's __root.tsx RootComponent wrapped around each page: the query client, the account
// provider, preference effects (reduced motion, sound, session reminder), the header and toasts.
// app/layout.tsx stays a Server Component and renders this.
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { AppHeader } from "@/components/zg/AppHeader";
import { Toaster } from "@/components/ui/sonner";
import { worldQuery } from "@/lib/player";
import { AccountProvider } from "@/lib/account";
import type { WorldData } from "@/lib/world-types";

function PreferenceEffects() {
  const { data } = useQuery(worldQuery);
  const prefs = (data as WorldData | undefined)?.preferences;
  useEffect(() => {
    document.documentElement.classList.toggle("reduce-motion", !!prefs?.reducedMotion);
    document.documentElement.dataset["sound"] = prefs?.sound === false ? "off" : "on";
  }, [prefs?.reducedMotion, prefs?.sound]);
  useEffect(() => {
    if (!prefs?.sessionReminders) return;
    const timer = window.setTimeout(() => toast.message("A gentle pause: you've been here for 20 minutes. Stretch, hydrate, or head back to challenges."), 20 * 60 * 1000);
    return () => window.clearTimeout(timer);
  }, [prefs?.sessionReminders]);
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      <AccountProvider>
        <PreferenceEffects />
        <AppHeader />
        <main className="mx-auto max-w-7xl px-4 pb-24 pt-8">{children}</main>
      </AccountProvider>
      <Toaster />
    </QueryClientProvider>
  );
}
