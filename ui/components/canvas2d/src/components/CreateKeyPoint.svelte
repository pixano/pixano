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

  // Imports

  import { Group, Line, Circle } from "svelte-konva";

  import type { CreateKeyPointShape } from "@pixano/core";
  //   import type { CreateKeyPointShape, SaveKeyBoxShape } from "@pixano/core";
  import type Konva from "konva";

  export let zoomFactor: Record<string, number>;
  export let newShape: CreateKeyPointShape;
  export let stage: Konva.Stage;
  export let viewId: string;

  let polygonId = "keyPoints";

  // le dernier point est le noeud de référence
  // en cliquant sur un point, il devient le noeud de reference
  // un point peut avoir zero, un ou plusieurs noeud d'origine. On trace toutes ses lignes

  $: {
    if (zoomFactor.foo === 10000) {
      console.log({ zoomFactor, stage });
    }
  }

  const findPoint = (id: number) => {
    const point = newShape.points.find((point) => point.id === id);
    if (!point) return [0, 0];
    return [point.x, point.y];
  };

  const setNewShape = (pointId: number) => {
    newShape = { ...newShape, referencePointId: pointId };
  };

  const onPointDragMove = (pointId: number) => {
    const pointPosition = stage.findOne(`#keyPoint-${polygonId}-${pointId}`).position();
    const points = newShape.points.map((point) => {
      if (point.id === pointId) {
        return { ...point, x: pointPosition.x, y: pointPosition.y };
      }
      return point;
    });
    newShape = { ...newShape, points };
  };

  const deletePoint = (pointId: number) => {
    let referencePointId = newShape.referencePointId;
    const garbage = [pointId];
    const points = newShape.points.filter((point) => {
      if (garbage.includes(point.id)) {
        garbage.push(pointId);
        return false;
      }
      if (point.origin_points.some((p) => garbage.includes(p))) {
        garbage.push(point.id);
        return false;
      }
      return true;
    });
    if (!points.map((p) => p.id).includes(referencePointId)) {
      referencePointId = points[points.length - 1].id;
    }
    newShape = { ...newShape, points, referencePointId };
  };
</script>

{#if newShape.viewId === viewId}
  <Group config={{ id: "keyPointStructure" }}>
    {#each newShape.points as point}
      {#if point.origin_points.length > 0}
        {#each point.origin_points as originPoint}
          <Line
            config={{
              points: [point.x, point.y, ...findPoint(originPoint)],
              stroke: "#781e60",
              strokeWidth: 1 / zoomFactor[viewId],
            }}
          />
        {/each}
      {/if}
      <Circle
        on:click={() => setNewShape(point.id)}
        config={{
          x: point.x,
          y: point.y,
          radius: (point.id === newShape.referencePointId ? 6 : 4) / zoomFactor[viewId],
          fill: point.id === newShape.referencePointId ? "#781e60" : "rgb(0,128,0)",
          stroke: "white",
          strokeWidth: 1 / zoomFactor[viewId],
          id: `keyPoint-${polygonId}-${point.id}`,
          draggable: true,
        }}
        on:dragmove={() => onPointDragMove(point.id)}
        on:dblclick={() => deletePoint(point.id)}
      />
    {/each}
  </Group>
{/if}

<!-- on:mouseover={(e) => {
        e.detail.target?.attrs?.id === `dot-${polygonId}-${i}-${point.id}` &&
          scaleCircleRadius(point.id, i, 2);
      }} -->

<!-- on:click={() => console.log("click")}
        on:dragmove={() => console.log("dragmove")}
        on:dragend={() => console.log("dragend")}
        on:mouseover={() => {
          console.log("mouseover");
        }}
        on:mouseleave={() => console.log("mouseleave")} -->
