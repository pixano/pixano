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
  import svg_next from "../assets/icons/next.svg";
  import svg_save from "../assets/icons/save.svg";
  import svg_close from "../assets/icons/close.svg";

  // Exports
  export let database: string;
  export let imageName: string;
  export let save_flag: boolean;
  export let handleCloseClick;
  export let handleSaveClick;
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<div
  class="h-20 py-4 px-4 flex justify-start items-center shrink-0 bg-white border-b-2 border-white dark:bg-zinc-800 dark:border-zinc-800"
>
  <div class="flex items-center grow space-x-2 font-bold text-3xl">
    <button
      class="cursor-pointer flex items-center space-x-2 hover:text-rose-800 dark:hover:text-rose-300"
      on:click={handleCloseClick}
    >
      <span class="transition-colors"> Pixano Annotator</span>
    </button>
    <img src={svg_next} alt="icon" class="h-6 w-6 opacity-75" />
    <span>
      {database}
    </span>
    <img src={svg_next} alt="icon" class="h-6 w-6 opacity-75" />
    <span>
      {imageName}
    </span>
  </div>

  <button class="w-30 h pr-4 flex justify-end" on:click={handleSaveClick}>
    <img
      src={svg_save}
      alt="icon"
      class="h-8 w-8 cursor-pointer cursor-pointer opacity-75"
      style={save_flag
        ? "background-color: #ffe4e6; box-shadow: 0px 0px 5px 5px #ffe4e6;"
        : ""}
    />
  </button>
  <button class="w-30 pr-4 flex justify-end" on:click={handleCloseClick}>
    <img src={svg_close} alt="icon" class="h-8 w-8 cursor-pointer opacity-75" />
  </button>
</div>
