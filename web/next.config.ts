import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  // Build a fully static site (out/) for S3 + CloudFront. /api/* is routed to
  // the Python API by CloudFront (AWS) or nginx (docker-compose).
  output: "export",
  // Emit league/teams/index.html etc.; CloudFront maps directory URLs to index.html.
  trailingSlash: true,
  // `next dev` only: forward /api/* to the local API so the browser stays same-origin.
  ...(isDev && {
    // Otherwise /api/leagues is redirected to /api/leagues/ before the rewrite.
    skipTrailingSlashRedirect: true,
    async rewrites() {
      const apiUrl = process.env.API_URL ?? "http://localhost:8000";
      return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
    },
  }),
};

export default nextConfig;
