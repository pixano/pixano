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

  // Imports
  import pixanoLogoWhite from "./assets/pixano_white.png";

  // Exports
  export let app: string = "";
</script>

<header class="w-full h-56 px-60 flex flex-col justify-evenly bg-main z-10">
  <!-- Logo & app name -->
  <button class="flex w-max space-x-6">
    <img src={pixanoLogoWhite} alt="Logo Pixano" class="w-10" />
    <span class="text-3xl font-bold text-slate-50 uppercase font-[Montserrat]">
      Pixano {app}
    </span>
  </button>
</header>

<div
  class="mt-4 py-8 flex w-full justify-center font-bold text-lg italic text-slate-500"
>
  Loading datasets...
</div>
<div
  class="mt-8 mx-auto border rounded-md p-4 max-w-sm w-full
  shadow border-slate-300"
>
  <div class="animate-pulse flex space-x-4">
    <div class="rounded-full bg-slate-300 h-10 w-10" />
    <div class="flex-1 space-y-6 py-1">
      <div class="h-2 bg-slate-300 rounded" />
      <div class="space-y-3">
        <div class="grid grid-cols-3 gap-4">
          <div class="h-2 bg-slate-300 rounded col-span-2" />
          <div class="h-2 bg-slate-300 rounded col-span-1" />
        </div>
        <div class="h-2 bg-slate-300 rounded" />
      </div>
    </div>
  </div>
</div>
