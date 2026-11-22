import type { Metadata } from 'next';
import { ResetPassword } from '@/components/pages/reset-password';

export const metadata: Metadata = {
  title: "Choose a new password — ZeroGambling",
  description: "Set a new password for your ZeroGambling account.",
  openGraph: { title: "Choose a new password — ZeroGambling", description: "Set a new password for your ZeroGambling account.", type: 'website' },
};

export default function Page() {
  return <ResetPassword/>;
}
