import type { Metadata } from 'next';
import { Chooser } from '@/components/pages/index';

export const metadata: Metadata = {
  title: "ZeroGambling — pick a skill challenge",
  description: "19 procedural challenges in logic, memory and perception. Practice a measurable skill to earn virtual gems.",
  openGraph: { title: "ZeroGambling — pick a skill challenge", description: "19 procedural challenges in logic, memory and perception. Practice a measurable skill to earn virtual gems.", type: 'website' },
};

export default function Page() {
  return <Chooser/>;
}
