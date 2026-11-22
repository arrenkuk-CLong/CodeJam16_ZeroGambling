import type { Metadata } from 'next';
import { Shop } from '@/components/pages/shop';

export const metadata: Metadata = {
  title: "Equipment & collectibles shop — ZeroGambling",
  description: "Buy slide equipment and generated collectibles with virtual gems, or trade collectibles with demo bot Trader Alex.",
  openGraph: { title: "Equipment & collectibles shop — ZeroGambling", description: "Buy slide equipment and generated collectibles with virtual gems, or trade collectibles with demo bot Trader Alex.", type: 'website' },
};

export default function Page() {
  return <Shop/>;
}
