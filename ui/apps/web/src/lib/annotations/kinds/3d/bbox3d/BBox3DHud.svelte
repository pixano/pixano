<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Move, Orbit, Scaling } from "lucide-svelte";

  import type { ToolHudProps } from "$lib/annotations/scene/tool.js";

  import type { BBox3DSession } from "./bbox3dSession.svelte.js";
  import type { GizmoVisibility } from "./bbox3dTypes.js";

  // The host forwards the session opaquely (it names no kind); downcast here.
  // The prop is a stable per-widget instance, so capturing it once is intended.
  let { session: rawSession }: ToolHudProps = $props();
  // svelte-ignore state_referenced_locally
  const session = rawSession as BBox3DSession;

  const GIZMO_TOGGLES: { key: keyof GizmoVisibility; icon: typeof Orbit; label: string }[] = [
    { key: "rings", icon: Orbit, label: "rotation rings" },
    { key: "resizeArrows", icon: Scaling, label: "resize arrows" },
    { key: "translateArrows", icon: Move, label: "translate arrows" },
  ];
</script>

{#if session.confirm}
  <div class="pointer-events-none absolute inset-x-0 bottom-4 flex justify-center">
    <div
      class="pointer-events-auto flex items-center gap-2 rounded-lg border border-border bg-background/95 px-3 py-2 text-sm shadow-lg backdrop-blur-sm"
    >
      <span class="text-muted-foreground">Save this 3D box?</span>
      <button
        type="button"
        onclick={() => session.save()}
        class="rounded bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90"
      >
        Save
      </button>
      <button
        type="button"
        onclick={() => session.cancel()}
        class="rounded border border-border px-2.5 py-1 text-xs hover:bg-accent"
      >
        Cancel
      </button>
      <div class="mx-1 h-4 w-px bg-border"></div>
      {#each GIZMO_TOGGLES as toggle (toggle.key)}
        <button
          type="button"
          onclick={() => session.toggleGizmo(toggle.key)}
          title={session.gizmoVisibility[toggle.key] ? `Hide ${toggle.label}` : `Show ${toggle.label}`}
          class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {session.gizmoVisibility[toggle.key] ? 'bg-accent text-accent-foreground' : ''}"
        >
          <toggle.icon class="h-3.5 w-3.5" />
        </button>
      {/each}
    </div>
  </div>
{/if}
