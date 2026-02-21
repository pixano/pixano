/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

type ProbeStats = {
  windowStartMs: number;
  hitsInWindow: number;
  totalHits: number;
  warnLevel: number;
};

const PROBE_KEY = "__PIXANO_EFFECT_PROBE__";
const WINDOW_MS = 1000;
const WARN_BASE = 40;

const isDebugEnabled = (): boolean => {
  if (typeof window === "undefined") return false;
  try {
    if (window.localStorage.getItem("PIXANO_EFFECT_DEBUG") === "1") return true;
    const params = new URLSearchParams(window.location.search);
    return params.get("effectDebug") === "1";
  } catch {
    return false;
  }
};

const getProbeMap = (): Map<string, ProbeStats> => {
  const target = window as unknown as {
    [PROBE_KEY]?: Map<string, ProbeStats>;
  };
  if (!target[PROBE_KEY]) {
    target[PROBE_KEY] = new Map<string, ProbeStats>();
  }
  return target[PROBE_KEY]!;
};

export const getEffectProbeSnapshot = (): Array<{
  label: string;
  windowStartMs: number;
  hitsInWindow: number;
  totalHits: number;
  warnLevel: number;
}> => {
  if (typeof window === "undefined") return [];
  return Array.from(getProbeMap().entries())
    .map(([label, stats]) => ({
      label,
      windowStartMs: stats.windowStartMs,
      hitsInWindow: stats.hitsInWindow,
      totalHits: stats.totalHits,
      warnLevel: stats.warnLevel,
    }))
    .sort((a, b) => b.hitsInWindow - a.hitsInWindow || b.totalHits - a.totalHits);
};

export const effectProbe = (label: string, details?: Record<string, unknown>) => {
  if (typeof window === "undefined") return;
  const now = typeof performance !== "undefined" ? performance.now() : Date.now();
  const probes = getProbeMap();
  const current = probes.get(label);
  const stats: ProbeStats = current ?? {
    windowStartMs: now,
    hitsInWindow: 0,
    totalHits: 0,
    warnLevel: 0,
  };

  if (now - stats.windowStartMs > WINDOW_MS) {
    stats.windowStartMs = now;
    stats.hitsInWindow = 0;
    stats.warnLevel = 0;
  }

  stats.hitsInWindow += 1;
  stats.totalHits += 1;
  probes.set(label, stats);

  if (isDebugEnabled()) {
    console.debug("[effect-probe]", label, {
      hitsInWindow: stats.hitsInWindow,
      totalHits: stats.totalHits,
      ...details,
    });
  }

  const level = Math.floor(stats.hitsInWindow / WARN_BASE);
  if (level > 0 && level > stats.warnLevel) {
    stats.warnLevel = level;
    console.warn("[effect-probe] high-frequency reactive loop candidate", label, {
      hitsInWindow: stats.hitsInWindow,
      totalHits: stats.totalHits,
      ...details,
    });
    if (isDebugEnabled()) {
      console.trace("[effect-probe] trace", label);
    }
  }
};
