import type { Metadata, Viewport } from 'next';
import { Bricolage_Grotesque, Instrument_Sans, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { Providers } from '@/components/Providers';

// The three Lovable fonts, self-hosted by next/font (globals.css maps them to font-sans/-display/-mono).
const instrument = Instrument_Sans({ variable: '--font-instrument', subsets: ['latin'], weight: ['400', '500', '600'] });
const bricolage = Bricolage_Grotesque({ variable: '--font-bricolage', subsets: ['latin'], weight: ['500', '700', '800'] });
const jetbrains = JetBrains_Mono({ variable: '--font-jetbrains', subsets: ['latin'], weight: ['400', '600'] });

export const metadata: Metadata = {
  title: 'ZeroGambling — earn by getting better',
  description: 'Practice measurable skills to earn virtual gems. A hackathon prototype.',
  openGraph: { type: 'website' },
  twitter: { card: 'summary_large_image' },
};

export const viewport: Viewport = { width: 'device-width', initialScale: 1 };

// 'children' is whatever page.tsx matches the current URL.
export default function RootLayout({ children }: LayoutProps<'/'>) {
  return (
    <html lang="en" className={`dark ${instrument.variable} ${bricolage.variable} ${jetbrains.variable}`}>
      <body><Providers>{children}</Providers></body>
    </html>
  );
}
