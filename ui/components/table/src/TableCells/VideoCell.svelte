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

  // Exports
  export let value: string;

  // Video
  let video: HTMLVideoElement;
  let isHovered = false;

  function toggleHover() {
    isHovered = !isHovered;
    if (isHovered) {
      video.playbackRate = 4;
      video.play().catch(() => console.error("video playback error"));
    } else {
      video.pause();
    }
  }
</script>

<div class="mx-8 h-20 aspect-square">
  <video
    bind:this={video}
    src={value}
    loop
    muted
    class="h-full w-full object-cover rounded"
    on:mouseenter={toggleHover}
    on:mouseleave={toggleHover}
  />
</div>
