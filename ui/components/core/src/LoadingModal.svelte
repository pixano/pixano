<script lang="ts">
  /**
    @copyright CEA-LIST/DIASI/SIALV/LVA (2023)
    @author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
    @license CECILL-C

    This software is a collaborative computer program whose purpose is to
    generate and explore labeled data for computer vision applications.
    This software is governed by the CeCILL-C license under French law and
    abiding by the rules of distribution of free software. You can use,
    modify and/ or redistribute the software under the terms of the CeCILL-C
    license as circulated by CEA, CNRS and INRIA at the following URL

    http://www.cecill.info
    */

  // Imports
  import { svg_loading } from "./icons";
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
