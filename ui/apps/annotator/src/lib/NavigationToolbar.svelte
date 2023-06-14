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
  export let database: string;
  export let imageName: string;
  export let handleCloseClick;
  export let handleSaveClick;
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<div class="h-20 flex items-center shrink-0">
  <div class="flex items-center grow space-x-2 font-bold text-2xl uppercase">
    <img src="icons/image.svg" alt="icon" class="h-6 w-6 opacity-40" />
    <span class="cursor-pointer" on:click={handleCloseClick}>
      {database}
    </span>
    <img src="icons/next.svg" alt="icon" class="h-6 w-6 opacity-40" />
    <span>
      {imageName}
    </span>
  </div>
  <div class="pr-4 flex space-x-4">
    <img src="icons/zoom_out.svg" alt="icon" class="h-8 w-8 cursor-pointer" />
    <img src="icons/zoom_in.svg" alt="icon" class="h-8 w-8 cursor-pointer" />
  </div>
  <div class="pr-4 flex space-x-4">
    <img src="icons/save.svg" alt="icon" class="h-8 w-8 cursor-pointer" on:click={handleSaveClick} />
  </div>
  <div class="w-80 pr-4 flex justify-end" on:click={handleCloseClick}>
    <img src="icons/close.svg" alt="icon" class="h-8 w-8 cursor-pointer" />
  </div>
</div>
