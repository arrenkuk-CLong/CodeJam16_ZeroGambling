import { permanentRedirect } from 'next/navigation';

// Merged into /about; kept so old links still work.
export default function Page() {
  permanentRedirect('/about');
}
