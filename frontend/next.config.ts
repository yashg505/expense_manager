import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  // Cloudflare Pages works best with a fully static export for this app
  // (UI is client-side and talks to the Render API).
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
