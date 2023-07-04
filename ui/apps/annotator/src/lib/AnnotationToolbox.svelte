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

  // Click mode
  export let click_mode: string;

  // Change mode to points add
  function onPointsAdd() {
    click_mode = "point_add";
    //change mouse pointer (visual ‘+’ near mouse)
    //show « floating » point (green because « + »)
  }

  // Change mode to points minus
  function onPointsMinus() {
    click_mode = "point_minus";
  }

  // Change mode to box
  function onBox() {
    click_mode = "box";
  }
</script>

<div
  class="w-28 max-h-[90vh] overflow-y-auto absolute top-1/2 -translate-y-1/2 left-4 px-2 py-2 flex flex-col space-y-2
  bg-zinc-50 border rounded-lg shadow-lg dark:bg-zinc-800 dark:text-zinc-100 dark:border-zinc-700"
>
  <button
    on:click={onPointsAdd}
    class="px-2 py-1 rounded text-sm font-bold cursor-pointer uppercase
    transition-colors hover:brightness-75
    {click_mode == 'point_add'
      ? 'bg-rose-500 text-zinc-50'
      : 'bg-zinc-200 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-50'}"
  >
    Point +
  </button>
  <button
    on:click={onPointsMinus}
    class="px-2 py-1 rounded text-sm font-bold cursor-pointer uppercase
    transition-colors hover:brightness-75
    {click_mode == 'point_minus'
      ? 'bg-rose-500 text-zinc-50'
      : 'bg-zinc-200 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-50'}"
  >
    Point -
  </button>
  <button
    on:click={onBox}
    class="px-2 py-1 rounded text-sm font-bold cursor-pointer uppercase
    transition-colors hover:brightness-75
    {click_mode == 'box'
      ? 'bg-rose-500 text-zinc-50'
      : 'bg-zinc-200 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-50'}"
  >
    Box
  </button>
</div>
