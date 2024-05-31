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

  // le dernier point est le noeud de référence
  // en cliquant sur un point, il devient le noeud de reference
  // un point peut avoir zero, un ou plusieurs noeud d'origine. On trace toutes ses lignes

  $: {
    if (zoomFactor.foo === 10000) {
      console.log({ zoomFactor, stage });
    }
  }

  $: console.log({ newShape });
  const findPoint = (id: number) => {
    const point = newShape.points.find((point) => point.id === id);
    return [point.x, point.y];
  };

  const setNewShape = (pointId: number) => {
    newShape = { ...newShape, referencePointId: pointId };
  };
</script>

{#if newShape.viewId === viewId}
  <Group config={{ id: "drag-rect-group" }}>
    <Line
      config={{
        points: [10, 20, 40, 50],
        stroke: "red",
        strokeWidth: 2,
        closed: true,
      }}
    />
    {#each newShape.points as point, i}
      {#if point.origin_points.length > 0}
        {#each point.origin_points as originPoint}
          <Line
            config={{
              points: [point.x, point.y, ...findPoint(originPoint)],
              stroke: "blue",
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
          radius: 4 / zoomFactor[viewId],
          fill: "rgb(0,128,0)",
          stroke: "white",
          strokeWidth: 1 / zoomFactor[viewId],
          id: `dot-${"polygonId"}-${i}-${point.id}`,
          draggable: true,
        }}
      />
    {/each}
  </Group>
{/if}

<!-- on:click={() => console.log("click")}
        on:dragmove={() => console.log("dragmove")}
        on:dragend={() => console.log("dragend")}
        on:mouseover={() => {
          console.log("mouseover");
        }}
        on:mouseleave={() => console.log("mouseleave")} -->
