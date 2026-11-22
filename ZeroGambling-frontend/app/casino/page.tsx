import type { Metadata } from 'next';
import { Casino } from '@/components/pages/casino';

export const metadata: Metadata = {
  title: "Fifteen versioned casino tables — ZeroGambling",
  description: "Play seven realistic virtual-credit casino games with European, American and French roulette, classic blackjack, multiline slots, live crash and video poker.",
  openGraph: { title: "Fifteen versioned casino tables — ZeroGambling", description: "Play seven realistic virtual-credit casino games with European, American and French roulette, classic blackjack, multiline slots, live crash and video poker.", type: 'website' },
};

export default function Page() {
  return <Casino/>;
}
