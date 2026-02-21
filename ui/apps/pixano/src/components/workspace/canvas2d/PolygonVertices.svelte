<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type Konva from "konva";
  import { Circle } from "svelte-konva";

  import type { PolygonVertex } from "$lib/types/shapeTypes";
  import type { Reference } from "$lib/types/dataset";

  interface Props {
    viewRef: Reference;
    zoomFactor: Record<string, number>;
    polygonId: string;
    points: PolygonVertex[][];
    onPointClick?: ((pointIndex: number, shapeIndex: number, viewRef: Reference) => void) | null;
    onPointDragMove?: ((id: number, shapeIndex: number, event: Konva.KonvaEventObject<DragEvent>) => void) | null;
    onPointDragEnd?: (() => void) | null;
  }

  let {
    viewRef,
    zoomFactor,
    polygonId,
    points,
    onPointClick = null,
    onPointDragMove = null,
    onPointDragEnd = null,
  }: Props = $props();

  // Track hovered vertex via $state instead of stage.findOne()
  let hoveredKey = $state<string | null>(null);

  function getScale(shapeIndex: number, pointId: number): number {
    return hoveredKey === `${shapeIndex}-${pointId}` ? 2 : 1;
  }

  function handleMouseOver(shapeIndex: number, pointId: number, e: Konva.KonvaEventObject<MouseEvent>) {
    const targetId = (e.target as Konva.Circle)?.id();
    if (targetId === `dot-${polygonId}-${shapeIndex}-${pointId}`) {
      hoveredKey = `${shapeIndex}-${pointId}`;
    }
  }

  function handleMouseLeave(shapeIndex: number, pointId: number) {
    if (hoveredKey === `${shapeIndex}-${pointId}`) {
      hoveredKey = null;
    }
  }
</script>

{#each points as shape, i}
  {#each shape as point}
    {@const scale = getScale(i, point.id)}
    <Circle
      onclick={(e: Konva.KonvaEventObject<MouseEvent>) => {
        e.cancelBubble = true;
        onPointClick?.(shape.indexOf(point), i, viewRef);
      }}
      ondragmove={(e: Konva.KonvaEventObject<DragEvent>) => onPointDragMove?.(point.id, i, e)}
      ondragend={() => onPointDragEnd?.()}
      onmouseover={(e: Konva.KonvaEventObject<MouseEvent>) => handleMouseOver(i, point.id, e)}
      onmouseleave={() => handleMouseLeave(i, point.id)}
      x={point.x}
      y={point.y}
      radius={(shape.indexOf(point) === 0 ? 6 : 4) / zoomFactor[viewRef.name]}
      fill={shape.indexOf(point) === 0 ? "hsl(330, 65%, 50%)" : "hsl(142, 60%, 40%)"}
      stroke="white"
      strokeWidth={1 / zoomFactor[viewRef.name]}
      id={`dot-${polygonId}-${i}-${point.id}`}
      draggable={true}
      scaleX={scale}
      scaleY={scale}
    />
  {/each}
{/each}
