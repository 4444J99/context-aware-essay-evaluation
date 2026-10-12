import type { NextConfig } from "next";
import { backendOrigin } from "./lib/gateway";
const origin = backendOrigin(process.env.EDU_BACKEND_ORIGIN, process.env.NODE_ENV === "production");
const config: NextConfig = {
  poweredByHeader: false,
  async rewrites() { return origin ? [
    { source: "/auth/:path*", destination: `${origin}/auth/:path*` },
    { source: "/v1/:path*", destination: `${origin}/v1/:path*` }
  ] : []; },
  async headers() { return [{ source: "/:path*", headers: [
    { key: "Cache-Control", value: "no-store" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "no-referrer" },
    { key: "Content-Security-Policy", value: "frame-ancestors 'none'; object-src 'none'; base-uri 'self'" }
  ] }]; }
};
export default config;
