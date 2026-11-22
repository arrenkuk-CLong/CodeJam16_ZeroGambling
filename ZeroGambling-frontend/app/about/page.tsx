import type { Metadata } from 'next';
import { About } from '@/components/pages/about';

export const metadata: Metadata = {
  title: "About, rules & odds — ZeroGambling",
  description: "What ZeroGambling is, how challenges pay gems, how assets are valued, and every casino table's rules and house edge.",
  openGraph: { title: "About, rules & odds — ZeroGambling", description: "What ZeroGambling is, how challenges pay gems, how assets are valued, and every casino table's rules and house edge.", type: 'website' },
};

export default function Page() {
  return <About/>;
}
