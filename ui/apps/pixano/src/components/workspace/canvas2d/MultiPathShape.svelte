<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type Konva from "konva";
  import { Shape as KonvaShape } from "svelte-konva";

  import { BBOX_STROKEWIDTH } from "./konvaConstants";
  import { NEUTRAL_ENTITY_COLOR } from "$lib/constants/workspaceConstants";
  import type { MultiPath } from "$lib/types/dataset";

  interface Props {
    multiPath: MultiPath;
    colorScale: (id: string) => string;
    zoomFactor: number;
    imageWidth: number;
    imageHeight: number;
  }

  let { multiPath, colorScale, zoomFactor, imageWidth, imageHeight }: Props = $props();

  let color = $derived.by(() => {
    if (multiPath.ui.displayControl.highlighted === "none") return NEUTRAL_ENTITY_COLOR;
    const entityId =
      multiPath.ui.top_entities && multiPath.ui.top_entities.length > 0
        ? multiPath.ui.top_entities[0].id
        : multiPath.data.entity_id;
    return colorScale(entityId);
  });

  let isClosed = $derived(multiPath.data.is_closed);
  let fillColor = $derived(isClosed ? color + "33" : undefined);

  function sceneFunc(ctx: Konva.Context, shape: Konva.Shape) {
    const { coords, num_points } = multiPath.data;
    if (!coords || coords.length === 0 || !num_points || num_points.length === 0) return;

    ctx.beginPath();
    let offset = 0;
    for (const n of num_points) {
      if (n < 2) { offset += n * 2; continue; }
      ctx.moveTo(coords[offset] * imageWidth, coords[offset + 1] * imageHeight);
      for (let i = 1; i < n; i++) {
        ctx.lineTo(coords[offset + i * 2] * imageWidth, coords[offset + i * 2 + 1] * imageHeight);
      }
      if (isClosed) {
        ctx.closePath();
      }
      offset += n * 2;
    }

    if (isClosed) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const rawCtx = (ctx as any)._context as CanvasRenderingContext2D;
      const fill = shape.fill() as string;
      if (fill) {
        rawCtx.fillStyle = fill;
        rawCtx.fill("evenodd");
      }
    }
    ctx.strokeShape(shape);
  }
</script>

<KonvaShape
  {sceneFunc}
  stroke={color}
  strokeWidth={BBOX_STROKEWIDTH}
  strokeScaleEnabled={false}
  perfectDrawEnabled={false}
  shadowForStrokeEnabled={false}
  fill={fillColor}
  opacity={multiPath.ui.opacity ?? 1}
  visible={!multiPath.ui.displayControl.hidden}
  listening={false}
/>
