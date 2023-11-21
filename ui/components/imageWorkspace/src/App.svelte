<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */
  import { MousePointer, Square, Share2, BrushIcon } from "lucide-svelte";
</script>

<div class="flex w-full bg-red-white h-screen">
  <div class="h-full bg-red-50 shadow-sm w-10">
    <div class="border-b border-green-400 flex items-center flex-col gap-4">
      <MousePointer />
      <Square />
      <Share2 />
      <BrushIcon />
    </div>
    <div class="flex items-center flex-col gap-4 mt-4">
      <Square />
      <BrushIcon />
    </div>
  </div>
  <div>main image goes her</div>
  <div>nav tools go here</div>
</div>
