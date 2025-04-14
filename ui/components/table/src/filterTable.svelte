<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CircleSlash2 } from "lucide-svelte";
  import { onMount } from "svelte";

  import { IconButton } from "@pixano/core";

  export let columns: { type?: string; name?: string }[] = [];
  export let handleFilter: (where: string) => void;

  let selectEl: HTMLSelectElement;
  let ghostEl: HTMLSpanElement;
  let selectWidth = 50;

  const allowedTypes = ["str", "int", "float"];
  let filterText: string = "";
  let selectedCol: string =
    columns.find((col) => allowedTypes.includes(col.type) && col.name).name ?? "";

  //Note: as we adjust select size depending on value, chars here are "important"
  //also, it should be something a user won't use as an attribute, hopefully
  const FREE = "!!!!-FREE-!!!!";

  const handleFilterText = () => {
    if (selectedCol === FREE) {
      handleFilter(filterText);
    } else {
      if (filterText === "") {
        handleFilter("");
      } else {
        const colType = columns.find((col) => col.name === selectedCol).type;
        if (colType === "str") handleFilter(`${selectedCol} = '${filterText}'`);
        else handleFilter(`${selectedCol} = ${filterText}`);
      }
    }
  };

  const handleClearFilter = () => {
    filterText = "";
    handleFilter("");
  };

  // cosmetic: use a ghost span to measure width and adjust select width accordingly
  function updateWidth() {
    if (!ghostEl || !selectEl) return;
    ghostEl.textContent = selectedCol;
    const width = ghostEl.getBoundingClientRect().width + 10; // +padding
    selectWidth = Math.max(width, 50); // min width
  }

  $: if (selectedCol) updateWidth();

  onMount(updateWidth);
</script>

<div class="flex justify-end gap-2 mr-4">
  <!-- Hidden ghost element for measuring -->
  <span bind:this={ghostEl} class="invisible absolute whitespace-nowrap px-2 font-normal" />
  <select
    title="Select column to filter on (equality), or Free mode"
    class="rounded-lg font-normal"
    style="width: {selectWidth}px"
    bind:this={selectEl}
    bind:value={selectedCol}
  >
    {#each columns as { type, name }}
      {#if allowedTypes.includes(type) && name}
        <option value={name}>
          {name}
        </option>
      {/if}
    {/each}
    <option value={FREE}>Free mode - enter a where clause</option>
  </select>
  <input
    type="text"
    bind:value={filterText}
    placeholder="filter value"
    class="h-10 pl-10 pr-4 rounded-lg border font-normal text-slate-800 placeholder-slate-500 bg-slate-50 border-slate-300 shadow-slate-300"
    on:change={handleFilterText}
  />
  <IconButton on:click={handleClearFilter} tooltipContent={"Clear filter"}>
    <CircleSlash2 />
  </IconButton>
</div>
