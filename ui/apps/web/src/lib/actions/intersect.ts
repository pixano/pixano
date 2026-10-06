/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Action } from "svelte/action";

export interface IntersectParams {
  onEnter: () => void;
  rootMargin?: string;
  threshold?: number | number[];
  enabled?: boolean;
}

/**
 * Svelte action that invokes `onEnter` whenever the node intersects the
 * viewport (or the nearest scroll ancestor). Silently no-ops in environments
 * without `IntersectionObserver` so existing tests keep working.
 */
export const intersect: Action<HTMLElement, IntersectParams> = (node, params) => {
  let current = params;

  if (typeof IntersectionObserver === "undefined") {
    return {
      update(next: IntersectParams) {
        current = next;
      },
      destroy() {},
    };
  }

  const observer = new IntersectionObserver(
    (entries) => {
      if (current.enabled === false) return;
      if (entries.some((entry) => entry.isIntersecting)) current.onEnter();
    },
    {
      rootMargin: params.rootMargin ?? "0px",
      threshold: params.threshold ?? 0,
    },
  );

  observer.observe(node);

  return {
    update(next: IntersectParams) {
      current = next;
    },
    destroy() {
      observer.disconnect();
    },
  };
};
