<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { HTMLAttributes } from "svelte/elements";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = HTMLAttributes<HTMLDivElement>;
  let className: $$Props["class"] = undefined;
  export { className as class };
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  class={cn("rounded-xl border border-border bg-card text-card-foreground shadow-elevation-1", className)}
  {...$$restProps}
  on:click
  on:mouseenter
  on:mouseleave
  on:focusin
  on:focusout
>
  <slot />
</div>
