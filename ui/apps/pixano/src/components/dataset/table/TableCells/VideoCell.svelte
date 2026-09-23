<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  interface Props {
    // Exports
    value: string;
  }

  let { value }: Props = $props();

  // Video
  let video: HTMLVideoElement = $state();
  let isHovered = false;

  function toggleHover() {
    isHovered = !isHovered;
    if (isHovered) {
      video.playbackRate = 2;
      video.play().catch(() => console.error("video playback error"));
    } else {
      video.pause();
    }
  }
</script>

<div class="mx-auto h-10 w-10">
  <video
    bind:this={video}
    src={value}
    loop
    muted
    playsinline
    class="h-full w-full object-cover rounded-lg bg-muted"
    onmouseenter={toggleHover}
    onmouseleave={toggleHover}
  ></video>
</div>
