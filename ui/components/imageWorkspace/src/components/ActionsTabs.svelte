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

  import * as Tabs from "@pixano/core/src/lib/components/ui/tabs";
</script>

<div class="h-full shadow-md w-10 bg-popover flex-[2_0_auto]">
  <Tabs.Root value="scene">
    <Tabs.List>
      <Tabs.Trigger value="scene">Scene</Tabs.Trigger>
      <Tabs.Trigger value="objects">Objets</Tabs.Trigger>
    </Tabs.List>
    <Tabs.Content value="scene">
      <div class="border-b-2 border-b-gray-500 p-4">
        <h3 class="uppercase font-extralight">context</h3>
        <p class="font-extralight pt-4 pb-8">
          Lorem ipsum dolor sit amet consectetur adipisicing elit. Provident, sit delectus!
        </p>
      </div>
      <div class="border-b-2 border-b-gray-500 p-4">
        <h3 class="uppercase font-extralight">Annotations</h3>
        <div class="mt-4 pb-8">
          <p class="mb-2">
            Labels
            <span
              class="ml-2 inline-flex items-center justify-center w-5 h-5 text-xs font-extralight text-white bg-primary rounded-full"
            >
              3</span
            >
          </p>
          <div class="flex gap-1 flex-wrap">
            <div
              class="flex items-center rounded-2xl bg-primary-light py-1 pr-1 px-4 first-letter:uppercase w-fit"
            >
              <p class="font-extralight first-letter:uppercase">rose</p>
              <span
                class="ml-4 inline-flex items-center justify-center w-5 h-5 text-xs font-extralight text-primary bg-white rounded-full"
              >
                2</span
              >
            </div>
            <div
              class="flex items-center rounded-2xl bg-primary-light py-1 pr-1 px-4 first-letter:uppercase w-fit"
            >
              <p class="font-extralight first-letter:uppercase">Sheep</p>
              <span
                class="ml-4 inline-flex items-center justify-center w-5 h-5 text-xs font-extralight text-primary bg-white rounded-full"
              >
                3</span
              >
            </div>
          </div>
        </div>
      </div>
      <div class="border-b-2 border-b-gray-500 p-4">
        <h3 class="uppercase font-extralight">Properties</h3>
        <div class="font-extralight mt-4 pb-8">
          <div class="grid gap-4 grid-cols-[100px_auto] mt-2">
            <p class="font-light first-letter:uppercase">color</p>
            <p>RGB</p>
          </div>
          <div class="grid gap-4 grid-cols-[100px_auto] mt-2">
            <p class="font-light first-letter:uppercase">IR</p>
            <p>00</p>
          </div>
          <div class="grid gap-4 grid-cols-[100px_auto] mt-2">
            <p class="font-light first-letter:uppercase">Depth</p>
            <p>00</p>
          </div>
          <div class="grid gap-4 grid-cols-[100px_auto] mt-2">
            <p class="font-light first-letter:uppercase">Spectral</p>
            <p>00</p>
          </div>
        </div>
      </div>
      <div class=" p-4">
        <h3 class="uppercase font-extralight">File</h3>
        <div class="font-extralight mt-4 pb-8">
          <div class="grid gap-4 grid-cols-[100px_auto] mt-2">
            <p class="font-light first-letter:uppercase">Created</p>
            <p>21/11/2023</p>
          </div>
          <div class="grid gap-4 grid-cols-[100px_auto] mt-2">
            <p class="font-light first-letter:uppercase">Modified</p>
            <p>21/11/2023</p>
          </div>
          <div class="grid gap-4 grid-cols-[100px_auto] mt-2">
            <p class="font-light first-letter:uppercase">By</p>
            <p>John Doe</p>
          </div>
        </div>
      </div>
    </Tabs.Content>
    <Tabs.Content value="objects">Change your password here.</Tabs.Content>
  </Tabs.Root>
</div>
