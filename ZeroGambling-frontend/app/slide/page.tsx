import type { Metadata } from 'next';
import { Slide } from '@/components/pages/slide';

export const metadata: Metadata = {
  title: "Slide game — ZeroGambling",
  description: "A synthwave downhill run: steer the roulette ball past cards, tokens and dice. Your glider level decides how fast you steer.",
  openGraph: { title: "Slide game — ZeroGambling", description: "A synthwave downhill run: steer the roulette ball past cards, tokens and dice. Your glider level decides how fast you steer.", type: 'website' },
};

export default function Page() {
  return <Slide/>;
}
