<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Konva from "konva";
  import { Image as KonvaImage, Layer, Stage } from "svelte-konva";

  export let imageDimension: { width: number; height: number };
  export let coords: number[];
  export let imageUrl: string;
  export let maxHeight: number | undefined = undefined;
  export let maxWidth: number | undefined = undefined;
  export let minSide: number | undefined = undefined;

  let [x, y, width, height] = coords;
  const enlargeFactor = 0.2;
  console.log("box", coords, imageDimension.width, imageDimension.height);
  let stage: Konva.Stage;

  const img = new Image();
  img.src = imageUrl;

  let cropX = x * imageDimension.width - width * imageDimension.width * enlargeFactor;
  if (cropX < 0) {
    cropX = 0;
  }
  let cropY = y * imageDimension.height - height * imageDimension.height * enlargeFactor;
  if (cropY < 0) {
    cropY = 0;
  }
  let cropWidth = width * imageDimension.width * (1 + enlargeFactor * 2);
  if (cropWidth > imageDimension.width) {
    cropWidth = imageDimension.width;
  }
  let cropHeight = height * imageDimension.height * (1 + enlargeFactor * 2);
  if (cropHeight > imageDimension.height) {
    cropHeight = imageDimension.height;
  }

  let stageWidth = cropWidth;
  let stageHeight = cropHeight;

  $: {
    if (minSide && Math.max(stageWidth, stageHeight) < minSide) {
      const ratio = Math.max(stageWidth, stageHeight) / minSide;
      stageWidth /= ratio;
      stageHeight /= ratio;
    }
    if (maxHeight && stageHeight > maxHeight) {
      const ratio = stageHeight / maxHeight;
      stageWidth /= ratio;
      stageHeight /= ratio;
    }
    if (maxWidth && stageWidth > maxWidth) {
      const ratio = stageWidth / maxWidth;
      stageWidth /= ratio;
      stageHeight /= ratio;
    }
  }
</script>

<div class="w-full h-fit flex justify-center">
  <Stage
    bind:handle={stage}
    config={{
      width: stageWidth,
      height: stageHeight,
      name: "konva",
      id: "thumbnail-stage",
    }}
  >
    <Layer>
      <KonvaImage
        config={{
          x: 0,
          y: 0,
          width: stageWidth,
          height: stageHeight,
          image: img,
          id: "thumbnail-image",
          crop: { x: cropX, y: cropY, height: cropHeight, width: cropWidth },
        }}
      />
    </Layer>
  </Stage>
</div>
