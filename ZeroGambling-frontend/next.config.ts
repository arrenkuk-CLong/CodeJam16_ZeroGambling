import type { NextConfig } from "next";

// Where the Django backend runs. Change it with BACKEND_URL=... when starting Next.js.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Forward /api/* to Django, so the browser only ever talks to this site: no CORS setup, and the
  // backend address lives in one place.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
    ];
  },
  // Pages from the previous app that now live elsewhere.
  async redirects() {
    return [
      { source: "/game", destination: "/slide", permanent: true },
      { source: "/permissions", destination: "/settings", permanent: true },
      { source: "/skills", destination: "/profile", permanent: true },
    ];
  },
  experimental: {
    agentFeedback: true,
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
