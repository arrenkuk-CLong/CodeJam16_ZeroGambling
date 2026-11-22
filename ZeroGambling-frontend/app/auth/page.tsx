import type { Metadata } from 'next';
import { AuthPage } from '@/components/pages/auth';

export const metadata: Metadata = {
  title: "Sign in or create an account — ZeroGambling",
  description: "Create a ZeroGambling account to keep your gems, skills and history across devices.",
  openGraph: { title: "Sign in or create an account — ZeroGambling", description: "Create a ZeroGambling account to keep your gems, skills and history across devices.", type: 'website' },
};

export default function Page() {
  return <AuthPage/>;
}
