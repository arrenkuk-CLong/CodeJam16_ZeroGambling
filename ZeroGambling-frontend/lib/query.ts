'use client';
// TanStack's useQuery, made safe for server rendering. The server always renders pages with no data
// (the player's token lives in this browser). The header can finish fetching before a page further down
// hydrates, and the shared cache would then make that page's first client render differ from the
// server's HTML: a hydration error. During hydration this hook therefore reports "no data yet", exactly
// like the server, and shows the real data one render later. After hydration it is plain useQuery.
import { useQuery as useTanstackQuery } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

export const useQuery = ((...args: Parameters<typeof useTanstackQuery>) => {
  const result = useTanstackQuery(...args);
  const hydrated = useSyncExternalStore(subscribe, () => true, () => false);
  return hydrated ? result : { ...result, data: undefined, error: null, isLoading: true, isPending: true, status: "pending" };
}) as typeof useTanstackQuery;
