<script lang="ts">
  /// <reference types="svelte" />
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

  // Imports
  import { cn } from "../../../lib/utils/styleUtils";
  import Button from "../button/button.svelte";

  export let isSelected: boolean = false;
</script>

<Button
  class={cn("font-medium h-10 px-6 border rounded-full transition-colors flex gap-2 ", {
    "bg-primary hover:bg-primary-foreground border-primary hover:border-primary-foreground text-slate-50":
      isSelected,
    "bg-white border-primary text-primary hover:bg-primary-light": !isSelected,
  })}
  on:click
>
  <slot />
</Button>
