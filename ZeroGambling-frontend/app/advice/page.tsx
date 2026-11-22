import type { Metadata } from 'next';
import { Advice } from '@/components/pages/advice';

export const metadata: Metadata = {
  title: "Gambling help & learning resources — ZeroGambling",
  description: "Confidential gambling support in Quebec and Canada, crisis help, and clear lessons about house edge and casino design.",
  openGraph: { title: "Gambling help & learning resources — ZeroGambling", description: "Confidential gambling support in Quebec and Canada, crisis help, and clear lessons about house edge and casino design.", type: 'website' },
};

export default function Page() {
  return <Advice/>;
}
