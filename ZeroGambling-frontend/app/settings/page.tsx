import type { Metadata } from 'next';
import { Settings } from '@/components/pages/settings';

export const metadata: Metadata = {
  title: "Permissions & preferences — ZeroGambling",
  description: "Control motion, sound, reminders, stake confirmations and which non-gem assets may be wagered.",
  openGraph: { title: "Permissions & preferences — ZeroGambling", description: "Control motion, sound, reminders, stake confirmations and which non-gem assets may be wagered.", type: 'website' },
};

export default function Page() {
  return <Settings/>;
}
