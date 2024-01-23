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

  import { Check, BoxSelectIcon, Filter } from "lucide-svelte";
  import { PrimaryButton, Slider, IconButton } from "@pixano/core";
</script>

<div class="my-4">
  <div class="flex justify-between my-4">
    <h3>PRE ANNOTATION</h3>
    <span>1 / 5</span>
  </div>
  <div class="my-2 flex items-center">
    <IconButton tooltipContent="confidence slider">
      <Filter />
    </IconButton>
    <div class="px-8 w-full">
      <Slider value={[0]} max={100} step={1} />
    </div>
  </div>
  <div class="bg-white rounded-sm p-4 mt-4">
    <p class="flex gap-2">
      <BoxSelectIcon color="#133AFC" />
      <span>obj535253453</span>
    </p>
    <div>infos diverses</div>
    <div class="flex gap-4 mt-4 w-full justify-center">
      <PrimaryButton isSelected><Check />Accept</PrimaryButton>
      <PrimaryButton>Ignore</PrimaryButton>
    </div>
  </div>
</div>
