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
  <div class="fixed inset-0 transition-opacity" />
  <div class="flex min-h-full justify-center text-center items-center">
    <div
      class="relative transform overflow-hidden rounded-lg p-6 max-w-2xl
      bg-black bg-opacity-50 text-slate-800"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        height="48"
        viewBox="0 -960 960 960"
        width="48"
        class="h-10 w-10 p-1 text-slate-50 animate-spin"
      >
        <path d={svg_loading} fill="currentcolor" />
      </svg>
    </div>
  </div>
</div>
