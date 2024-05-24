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
  import { cn } from "@pixano/core";
  let className: string | undefined | null = undefined;

  export { className as class };
</script>

<div class={cn("flex px-4", className)}>
  <div class={cn("w-full sticky top-0 bg-white z-20")}>
    <slot name="timeTrack" />
  </div>
</div>
