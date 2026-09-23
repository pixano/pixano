<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  interface Props {
    onmousedown: (event: MouseEvent) => void;
    ariaLabel: string;
    /** Which axis the handle resizes. */
    orientation?: "vertical" | "horizontal";
  }

  let { onmousedown, ariaLabel, orientation = "vertical" }: Props = $props();
</script>

<!-- The one resize-handle: a grippy bar with hover affordance, shared by every split view. -->
<button
  type="button"
  {onmousedown}
  aria-label={ariaLabel}
  class="group relative shrink-0 bg-border transition-colors hover:bg-primary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring {orientation ===
  'vertical'
    ? 'h-full w-1.5 cursor-col-resize'
    : 'h-1.5 w-full cursor-row-resize'}"
>
  <div
    class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-border transition-colors group-hover:bg-primary/50 {orientation ===
    'vertical'
      ? 'h-8 w-1'
      : 'h-1 w-8'}"
  ></div>
</button>
