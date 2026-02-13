<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { svg_loading } from "../../icons";
</script>

<div class="fixed inset-0 z-50 overflow-y-auto">
  <div class="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity" />
  <div class="flex min-h-full justify-center text-center items-center">
    <div
      class="relative transform overflow-hidden rounded-2xl p-6 max-w-2xl
      bg-card/95 backdrop-blur-[24px] border border-border/40 shadow-glass-lg"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        height="48"
        viewBox="0 -960 960 960"
        width="48"
        class="h-10 w-10 p-1 text-primary animate-spin"
      >
        <path d={svg_loading} fill="currentcolor" />
      </svg>
    </div>
  </div>
</div>
