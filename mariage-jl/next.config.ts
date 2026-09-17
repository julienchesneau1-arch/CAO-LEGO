import type { NextConfig } from "next";

/** Sortie standalone : une image Docker minimale (section 0 bis du brief). */
const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
