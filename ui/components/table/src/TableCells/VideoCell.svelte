<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
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
