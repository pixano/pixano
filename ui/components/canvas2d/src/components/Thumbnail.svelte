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
  export let maxSize: number = 48;

  let [x, y, width, height] = coords;

  let stage: Konva.Stage;

  const img = new Image();
  img.src = imageUrl;

  let stageWidth = width * imageDimension.width;
  let stageHeight = height * imageDimension.height;

  $: {
    if (Math.max(stageWidth, stageHeight) > maxSize) {
      const ratio = Math.max(stageWidth, stageHeight) / maxSize;
      stageWidth /= ratio;
      stageHeight /= ratio;
    }
  }
</script>

<div class="w-fit z-40">
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
          crop: {
            x: x * imageDimension.width,
            y: y * imageDimension.height,
            width: width * imageDimension.width,
            height: height * imageDimension.height,
          },
        }}
      />
    </Layer>
  </Stage>
</div>
