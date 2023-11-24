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
  import { MousePointer, Square, Share2, BrushIcon } from "lucide-svelte";
  import TooltipIconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";

  import MagicIcon from "../assets/MagicIcon.svelte";
</script>

<div class="h-full shadow-md w-10 bg-popover">
  <div class="border-b border-gray-400 pb-4 flex items-center flex-col gap-4 bg-popover">
    <TooltipIconButton tooltipContent="TODO">
      <MousePointer />
    </TooltipIconButton>
    <TooltipIconButton tooltipContent="TODO">
      <Square />
    </TooltipIconButton>
    <TooltipIconButton tooltipContent="TODO">
      <Share2 />
    </TooltipIconButton>
    <TooltipIconButton tooltipContent="TODO">
      <BrushIcon />
    </TooltipIconButton>
  </div>
  <div class="flex items-center flex-col gap-4 mt-4">
    <TooltipIconButton tooltipContent="TODO">
      <BrushIcon />
      <MagicIcon />
    </TooltipIconButton>
    <TooltipIconButton tooltipContent="TODO">
      <Square />
      <MagicIcon />
    </TooltipIconButton>
  </div>
</div>
