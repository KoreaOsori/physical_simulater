import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // docker-compose.yml's WATCHPACK_POLLING=true is a webpack-era knob that
  // does nothing for Turbopack (this project's dev default since Next 15+) —
  // without this, new files created on the host can go unnoticed by the
  // frontend container's dev server indefinitely on Docker Desktop/WSL2
  // bind mounts (inotify events don't reliably cross that boundary), which
  // is exactly what caused the "Module not found" errors after adding
  // DiveRevealSlider.tsx/human-dive-stages.ts — only a full container
  // restart picked them up. This is Turbopack's actual polling knob.
  watchOptions: {
    pollIntervalMs: 500,
  },
};

export default nextConfig;
