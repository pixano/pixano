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
  import { createEventDispatcher } from "svelte";
  import type { Dataset } from "./interfaces";

  // Exports
  export let selectedDataset: Dataset = null;

  let selectedTab: string = "";

  const dispatch = createEventDispatcher();
</script>

<!-- Dashboard -->
{#if selectedDataset.page}
  <div class="h-full flex flex-row">
    <div class="w-1/6 flex flex-col items-start">
      <button class="w-full px-8 py-4 rounded-l-sm text-lg text-left text-main bg-slate-200"> Overview </button>
      <button class="w-full px-8 py-4 rounded-l-sm text-lg text-left"> Statistics </button>
    </div>
    <div class="w-5/6 p-8 bg-white rounded-r-sm border border-slate-200 shadow shadow-slate-200">
      <div class="w-full mb-16 flex flex-row justify-between">
        <div>
          <span class="text-5xl font-bold font-[Montserrat]"> {selectedDataset.name} </span>
          <span class="text-xl text-slate-400 font-[Montserrat]"> #{selectedDataset.id} </span>
        </div>
        <div>
          <span class="text-5xl font-bold font-[Montserrat]"> {selectedDataset.num_elements} </span>
          <span class="ml-2 text-xl font-[Montserrat]"> items </span>
        </div>
      </div>
      <div class="text-lg">
        {selectedDataset.description}
        <br />
        <!-- Lorem ipsum -->
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Curabitur vel sagittis massa, eu viverra nisl. Donec nibh
        orci, pellentesque quis elit sed, gravida tempus massa. Quisque laoreet, odio vitae iaculis fermentum, nisi erat
        viverra orci, a tristique tortor arcu quis nisl. Duis et orci condimentum, lobortis lacus in, ultricies metus. Etiam
        sed vestibulum nibh. Mauris id nisi consectetur, porttitor odio sed, ullamcorper diam. In pellentesque tristique
        erat, sit amet cursus ante luctus et. Praesent eros velit, convallis vitae pretium ac, tincidunt non metus. Aenean
        facilisis neque eu velit hendrerit auctor. Donec condimentum nulla eu varius gravida. Praesent lacinia nibh nec augue
        vulputate pretium. Nam eu tellus a nisi posuere pharetra at non metus. Duis molestie nec odio nec laoreet. Ut commodo,
        augue eget sagittis egestas, lectus orci cursus velit, et lobortis libero eros non nunc. Suspendisse arcu lectus,
        sodales id maximus eu, dignissim commodo dui. Integer gravida varius mi, et pretium leo dictum sagittis. Mauris in
        arcu eu urna mattis accumsan. Curabitur ultrices, nisl a molestie tempor, ex ipsum tristique sem, fermentum porta
        nisl odio ac sapien. Integer mauris dui, aliquam et euismod nec, congue vel nulla. Proin accumsan molestie ipsum
        at venenatis. Pellentesque aliquet sapien justo, a euismod velit sagittis fringilla. Maecenas at ornare arcu, et
        ullamcorper ligula.
      </div>
    </div>
  </div>
{/if}
