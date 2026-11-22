import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { Suspense } from 'react';
import { ACTIVE_IDS, getEntry } from '@/lib/catalog';
import { Play } from '@/components/pages/play';

// All 19 challenges are prerendered at build time; any other ID (including retracted #9) is a 404.
export function generateStaticParams() {
  return ACTIVE_IDS.map((id) => ({ gameId: String(id) }));
}

export async function generateMetadata({ params }: PageProps<'/play/[gameId]'>): Promise<Metadata> {
  const entry = getEntry(Number((await params).gameId));
  const title = `${entry?.name ?? 'Challenge'} — ZeroGambling`;
  const description = entry?.measures ?? 'A procedural skill challenge.';
  return { title, description, openGraph: { title, description, type: 'website' } };
}

// Cache Components: the route param is read inside <Suspense>, so navigation stays instant.
export default function Page({ params }: PageProps<'/play/[gameId]'>) {
  return <Suspense fallback={null}><Challenge params={params}/></Suspense>;
}

async function Challenge({ params }: { params: PageProps<'/play/[gameId]'>['params'] }) {
  const id = Number((await params).gameId);
  if (!getEntry(id)) notFound();
  return <Play gameId={id}/>;
}
