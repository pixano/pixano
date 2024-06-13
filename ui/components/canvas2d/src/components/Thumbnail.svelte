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

  import Konva from "konva";
  import { Image as KonvaImage, Layer, Stage } from "svelte-konva";

  export let imageDimension: { width: number; height: number };
  export let coords: number[];
  export let imageUrl: string;
  export let maxHeight: number | undefined = undefined;
  export let maxWidth: number | undefined = undefined;
  export let minWidth: number | undefined = undefined;

  let [x, y, width, height] = coords;

  let stage: Konva.Stage;

  const img = new Image();
  img.src = imageUrl;

  let stageWidth = width * imageDimension.width;
  let stageHeight = height * imageDimension.height;

  $: {
    if (maxHeight && stageHeight > maxHeight) {
      const ratio = stageHeight / maxHeight;
      stageWidth /= ratio;
      stageHeight /= ratio;
    }
    if (maxHeight && stageHeight < maxHeight) {
      const ratio = maxHeight / stageHeight;
      stageWidth *= ratio;
      stageHeight *= ratio;
    }
    if (maxWidth && stageWidth > maxWidth) {
      const ratio = stageWidth / maxWidth;
      stageWidth /= ratio;
      stageHeight /= ratio;
    }
  }

  $: {
    if (minWidth && Math.max(stageWidth, stageHeight) < minWidth) {
      const ratio = Math.max(stageWidth, stageHeight) / minWidth;
      stageWidth /= ratio;
      stageHeight /= ratio;
    }
  }

  const defineCrop = () => {
    let cropX = x * imageDimension.width - (width * imageDimension.width) / 2;
    if (cropX < 0) {
      cropX = 0;
    }
    let cropY = y * imageDimension.height - (height * imageDimension.height) / 2;
    if (cropY < 0) {
      cropY = 0;
    }
    let cropWidth = width * imageDimension.width * 2;
    if (cropWidth > imageDimension.width) {
      cropWidth = imageDimension.width;
    }
    let cropHeight = height * imageDimension.height * 2;
    if (cropHeight > imageDimension.height) {
      cropHeight = imageDimension.height;
    }
    return {
      x: cropX,
      y: cropY,
      width: cropWidth,
      height: cropHeight,
    };
  };
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
          crop: { ...defineCrop() },
        }}
      />
    </Layer>
  </Stage>
</div>
