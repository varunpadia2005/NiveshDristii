import type { NextConfig } from "next";

// P20-WEB: /api/* proxies to the loopback-only stdlib API
// (python -m niveshdristi.webapi --fund-base <dir> --port 8000).
// No external hosts — the app never talks to anything but localhost.
const config: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" },
    ];
  },
};
export default config;
