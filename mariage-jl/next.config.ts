import withSerwistInit from "@serwist/next";
import type { NextConfig } from "next";

/** Sortie standalone : une image Docker minimale (section 0 bis du brief). */
const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
};

/**
 * Service worker (brief §5). Désactivé en développement : un cache qui garde
 * une version périmée pendant qu'on travaille coûte plus de temps qu'il n'en
 * fait gagner.
 */
const avecServiceWorker = withSerwistInit({
  swSrc: "app/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development",
  reloadOnOnline: false,
});

export default avecServiceWorker(nextConfig);
