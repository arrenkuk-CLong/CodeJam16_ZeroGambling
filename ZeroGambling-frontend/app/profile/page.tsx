import type { Metadata } from 'next';
import { Profile } from '@/components/pages/profile';

export const metadata: Metadata = {
  title: "Your progress — ZeroGambling",
  description: "Mastery per challenge, permanent completion history and your gem ledger.",
  openGraph: { title: "Your progress — ZeroGambling", description: "Mastery per challenge, permanent completion history and your gem ledger.", type: 'website' },
};

export default function Page() {
  return <Profile/>;
}
