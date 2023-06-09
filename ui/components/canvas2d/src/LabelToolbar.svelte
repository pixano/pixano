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
  import { createEventDispatcher } from "svelte";
  import { ToolType } from "./tools";
  import {
    svg_point_plus,
    svg_point_minus,
    svg_validate,
  } from "../../core/src/icons";

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

  function filterLabels() {
    var input, filter, a, i;
    input = document.getElementById("label_input");
    filter = input.value.toUpperCase();
    let div = document.getElementById("label_list");
    a = div.getElementsByTagName("button");
    for (i = 0; i < a.length; i++) {
      let txtValue = a[i].textContent || a[i].innerText;
      if (txtValue.toUpperCase().indexOf(filter) > -1) {
        a[i].style.display = "";
      } else {
        a[i].style.display = "none";
      }
    }
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
      id="label_input"
      class="py-1 px-2 border rounded focus:outline-none
      bg-zinc-100 dark:bg-zinc-700
      border-zinc-300 dark:border-zinc-500
      focus:border-rose-600 dark:focus:border-rose-500
      "
      on:keyup={filterLabels}
      bind:value={className}
    />

    <div
      id="label_list"
      class="absolute left-0 top-14 w-full px-2 py-2 hidden bg-white rounded-b-lg group-focus-within:flex hover:flex flex-col"
      style="overflow-y:scroll; max-height: 500px;"
    >
      {#each classes as cls}
        <button
          class="py-1 px-2 text-sm bg-white rounded-lg hover:bg-zinc-100"
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
      <svg
        xmlns="http://www.w3.org/2000/svg"
        height="48"
        viewBox="0 -960 960 960"
        width="48"
        class="h-8 w-8 p-1 border-2 rounded
        bg-white dark:bg-zinc-800
        hover:bg-zinc-200 dark:hover:bg-zinc-600
        {selectedAnnotationTool === pointPlusTool
          ? 'border-rose-500 dark:border-rose-600'
          : 'border-transparent'}"
      >
        <title>Positive point</title>
        <path d={svg_point_plus} fill="currentcolor" />
      </svg>
    </button>
    <button
      on:click={() => {
        selectedAnnotationTool = pointMinusTool;
      }}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        height="48"
        viewBox="0 -960 960 960"
        width="48"
        class="h-8 w-8 p-1 border-2 rounded
        bg-white dark:bg-zinc-800
        hover:bg-zinc-200 dark:hover:bg-zinc-600
        {selectedAnnotationTool === pointMinusTool
          ? 'border-rose-500 dark:border-rose-600'
          : 'border-transparent'}"
      >
        <title>Negative point</title>
        <path d={svg_point_minus} fill="currentcolor" />
      </svg>
    </button>
  {/if}
  <button on:click={validate}>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      height="48"
      viewBox="0 -960 960 960"
      width="48"
      class="h-8 w-8 p-1 rounded cursor-pointer text-zinc-50
      bg-rose-500 dark:bg-rose-600
      hover:bg-rose-600 dark:hover:bg-rose-500"
    >
      <title>Validate</title>
      <path d={svg_validate} fill="currentcolor" />
    </svg>
  </button>
</div>
