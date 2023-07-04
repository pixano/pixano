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
  import svg_image from "../assets/icons/image.svg";
  import svg_next from "../assets/icons/next.svg";
  import svg_zoomout from "../assets/icons/zoom_out.svg";
  import svg_zoomin from "../assets/icons/zoom_in.svg";
  import svg_save from "../assets/icons/save.svg";
  import svg_close from "../assets/icons/close.svg";

  export let database: string;
  export let imageName: string;
  export let save_flag: boolean;
  export let handleCloseClick;
  export let handleSaveClick;
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<div class="h-20 flex items-center shrink-0">
  <div class="flex items-center grow space-x-2 font-bold text-2xl uppercase">
    <img
      src={svg_image}
      alt="icon"
      class="h-6 w-6 opacity-40 cursor-pointer"
      on:click={handleCloseClick}
    />
    <span class="cursor-pointer" on:click={handleCloseClick}>
      {database}
    </span>
    <img src={svg_next} alt="icon" class="h-6 w-6 opacity-40" />
    <span>
      {imageName}
    </span>
  </div>
  <!-- TODO: unused zoom buttons
  <div class="pr-4 flex space-x-4">
    <img src={svg_zoomout} alt="icon" class="h-8 w-8 cursor-pointer" />
    <img src={svg_zoomin} alt="icon" class="h-8 w-8 cursor-pointer" />
  </div> -->
  <div
    class="w-30 h-full gap-y-px pt-6 pl-4 pr-4 border-b-4 flex justify-end {save_flag
      ? 'bg-rose-100 border-rose-900'
      : 'border-transparent'}"
    on:click={handleSaveClick}
  >
    <img src={svg_save} alt="icon" class="h-8 w-8 cursor-pointer" />
  </div>
  <div class="w-30 pr-4 flex justify-end" on:click={handleCloseClick}>
    <img src={svg_close} alt="icon" class="h-8 w-8 cursor-pointer" />
  </div>
</div>
