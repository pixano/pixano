<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Tooltip } from "bits-ui";
  import type { Snippet } from "svelte";

  import { cn } from "$lib/utils/styleUtils";

  // The one tooltip surface of the app: below the trigger so the Konva canvas does
  // not mask it, and above every overlay.
  interface Props {
    class?: string;
    children?: Snippet;
  }

  let { class: className = undefined, children }: Props = $props();
</script>

<Tooltip.Content
  side="bottom"
  sideOffset={6}
  class={cn(
    "z-[9999] overflow-hidden rounded-md border border-border/40 bg-popover/95 backdrop-blur-md px-3 py-1.5 text-sm text-popover-foreground shadow-glass-sm",
    className,
  )}
>
  {@render children?.()}
</Tooltip.Content>
