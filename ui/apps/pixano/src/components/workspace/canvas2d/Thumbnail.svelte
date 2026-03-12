<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Image as KonvaImage, Layer, Stage } from "svelte-konva";

  interface Props {
    imageDimension: { width: number; height: number };
    coords: number[];
    imageUrl: string;
    maxHeight?: number | undefined;
    maxWidth?: number | undefined;
    minSide?: number | undefined;
  }

  let {
    imageDimension,
    coords,
    imageUrl,
    maxHeight = undefined,
    maxWidth = undefined,
    minSide = undefined,
  }: Props = $props();

  const enlargeFactor = 0.2;

  const img = $state(new Image());
  $effect(() => {
    img.src = imageUrl;
  });

  const crop = $derived.by(() => {
    const [x, y, width, height] = coords;
    let cropX = x * imageDimension.width - width * imageDimension.width * enlargeFactor;
    let cropY = y * imageDimension.height - height * imageDimension.height * enlargeFactor;
    let cropWidth = width * imageDimension.width * (1 + enlargeFactor * 2);
    let cropHeight = height * imageDimension.height * (1 + enlargeFactor * 2);

    if (cropX <0) cropX = 0;
    if (cropY <0) cropY = 0;
    if (cropWidth > imageDimension.width) cropWidth = imageDimension.width;
    if (cropHeight > imageDimension.height) cropHeight = imageDimension.height;

    return { cropX, cropY, cropWidth, cropHeight };
  });

  const stageSize = $derived.by(() => {
    let stageWidth = crop.cropWidth;
    let stageHeight = crop.cropHeight;

    if (minSide && Math.max(stageWidth, stageHeight) <minSide) {
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

    return { stageWidth, stageHeight };
  });
</script>

<div class="w-full h-fit flex justify-center">
  <Stage
    width={stageSize.stageWidth}
    height={stageSize.stageHeight}
    name="konva"
    id="thumbnail-stage"
  >
    <Layer>
      <KonvaImage
        x={0}
        y={0}
        width={stageSize.stageWidth}
        height={stageSize.stageHeight}
        image={img}
        id="thumbnail-image"
        crop={{ x: crop.cropX, y: crop.cropY, height: crop.cropHeight, width: crop.cropWidth }}
      />
    </Layer>
  </Stage>
</div>
