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

  // Assets
  import svg_plus from "../../core/src/assets/icons/plus.svg";
  import svg_minus from "../../core/src/assets/icons/minus.svg";
  import svg_ok from "../../core/src/assets/icons/ok.svg";

  // Imports
  import { createEventDispatcher } from "svelte";
  import { ToolType } from "./tools";

  // Exports
  export let className;
  export let classes;
  export let selectedAnnotationTool;
  export let pointPlusTool;
  export let pointMinusTool;

  const dispatch = createEventDispatcher();

  // Validate annotation
  function validate() {
    dispatch("validate");
  }
</script>

<div
  id="point-modal"
  class="absolute top-24 left-1/2 -translate-x-1/2 p-4 flex items-center space-x-4 border rounded-lg z-10 shadow-xl
bg-white dark:bg-zinc-800
border-zinc-300 dark:border-zinc-500"
>
  <div class="group">
    <input
      type="text"
      placeholder="New label"
      class="py-1 px-2 border rounded focus:outline-none
    bg-zinc-100 dark:bg-zinc-700
    text-zinc-900 dark:text-zinc-200
    border-zinc-300 dark:border-zinc-500
    focus:border-rose-600 dark:focus:border-rose-500
    "
      bind:value={className}
    />

    <div
      class="absolute left-0 top-14 w-full px-2 py-2 hidden bg-white rounded-b-lg group-focus-within:flex hover:flex flex-col"
      style="overflow-y:scroll; max-height: 500px;"
    >
      {#each classes as cls}
        <button
          class="py-1 px-2 text-sm cursor-pointer bg-white rounded-lg hover:bg-zinc-100"
          style="text-align:left"
          on:click={() => (className = cls.name)}
        >
          {cls.name}
        </button>
      {/each}
    </div>
  </div>

  {#if selectedAnnotationTool.type === ToolType.LabeledPoint}
    <button
      on:click={() => {
        selectedAnnotationTool = pointPlusTool;
      }}
    >
      <img
        src={svg_plus}
        alt="Plus"
        class="h-8 w-8 p-1 border rounded cursor-pointer
        bg-white hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-600
        {selectedAnnotationTool === pointPlusTool
          ? 'border-rose-500 dark:border-rose-600'
          : 'border-transparent'}"
      />
    </button>
    <button
      on:click={() => {
        selectedAnnotationTool = pointMinusTool;
      }}
    >
      <img
        src={svg_minus}
        alt="Minus"
        class="h-8 w-8 p-1 border rounded cursor-pointer
        bg-white hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-600
        {selectedAnnotationTool === pointMinusTool
          ? 'border-rose-500 dark:border-rose-600'
          : 'border-transparent'}"
      />
    </button>
  {/if}
  <button on:click={validate}>
    <img
      src={svg_ok}
      alt="Validate"
      class="h-8 w-8 p-1 rounded cursor-pointer
      bg-rose-500 hover:bg-rose-600 dark:bg-rose-600 dark:hover:bg-rose-700"
    />
  </button>
</div>
