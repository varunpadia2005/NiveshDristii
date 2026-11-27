import type { NextConfig } from "next";

// P20-WEB: /api/* proxies to the loopback-only stdlib API
// (python -m niveshdristi.webapi --fund-base <dir> --port 8000).
// No external hosts — the app never talks to anything but localhost.
const config: NextConfig = {
  // WEB-FIX-1: Next 16 dev blocks cross-origin dev resources (HMR) for
  // origins not in this list; the app is reachable at both localhost and
  // 127.0.0.1 on loopback.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" },
    ];
  },
};
export default config;
