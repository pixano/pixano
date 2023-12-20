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
  import { cn } from "../../utils";
  import Button from "../ui/button/button.svelte";

  export let isSelected: boolean = false;
</script>

<Button
  class={cn("font-medium h-10 px-6 border transition-colors flex gap-2 hover:bg-primary-light", {
    "bg-primary border-primary rounded-full text-slate-50": isSelected,
    "bg-slate-50 border-slate-300 rounded-full text-primary": !isSelected,
  })}
  on:click
>
  <slot />
</Button>
