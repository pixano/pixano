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
  import { PrimaryButton, Slider, IconButton, Switch } from "@pixano/core";
  import FeatureFormInputs from "../Features/FeatureFormInputs.svelte";

  let isFormValid: boolean = false;
  let isActive: boolean = false;
</script>

<div class="my-4">
  <div class="flex justify-between my-4">
    <div class="flex gap-4">
      <Switch bind:checked={isActive} />
      <h3>PRE ANNOTATION</h3>
    </div>
    {#if isActive}
      <span>1 / 5</span>
    {/if}
  </div>
  {#if isActive}
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
      <div class="flex flex-col gap-4 py-4">
        <FeatureFormInputs bind:isFormValid />
      </div>
      <div class="flex gap-4 mt-4 w-full justify-center">
        <PrimaryButton isSelected disabled={!isFormValid}><Check />Accept</PrimaryButton>
        <PrimaryButton>Ignore</PrimaryButton>
      </div>
    </div>
  {/if}
</div>
