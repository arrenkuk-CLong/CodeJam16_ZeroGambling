'use client';
// The two TanStack Router pieces Lovable's pages use (Link and useNavigate), on top of the Next.js router.
// Paths keep TanStack's form ("/play/$gameId" + params). An active link gets data-status="active",
// which the header styles with data-[status=active]:...
import NextLink from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { forwardRef, useCallback, type AnchorHTMLAttributes } from 'react';

type Params = Record<string, string>;

function buildHref(to: string, params?: Params) {
  return to.replace(/\$(\w+)/g, (_, key: string) => encodeURIComponent(params?.[key] ?? ''));
}

function isActive(pathname: string, href: string, exact?: boolean) {
  if (exact || href === '/') return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export interface LinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> {
  to: string;
  params?: Params;
  activeOptions?: { exact?: boolean };
  replace?: boolean;
}

export const Link = forwardRef<HTMLAnchorElement, LinkProps>(function Link({ to, params, activeOptions, replace, ...rest }, ref) {
  const href = buildHref(to, params);
  const active = isActive(usePathname() ?? '/', href, activeOptions?.exact);
  return <NextLink ref={ref} href={href} replace={replace} data-status={active ? 'active' : undefined} aria-current={active ? 'page' : undefined} {...rest} />;
});

export function useNavigate() {
  const router = useRouter();
  return useCallback(({ to, params, replace }: { to: string; params?: Params; replace?: boolean }) => {
    const href = buildHref(to, params);
    if (replace) router.replace(href); else router.push(href);
  }, [router]);
}
