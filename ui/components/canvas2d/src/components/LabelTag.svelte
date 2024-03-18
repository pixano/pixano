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
  import { Label, Tag, Text } from "svelte-konva";

  export let id: string;
  export let x: number;
  export let y: number;
  export let visible: boolean;
  export let zoomFactor: number;
  export let opacity: number;
  export let tooltip: string | undefined;
  export let color: string;
</script>

<Label
  config={{
    id: `tooltip${id}`,
    x,
    y,
    width: 500,
    height: 50,
    offsetY: 12,
    visible: visible,
    scale: {
      x: 1 / zoomFactor,
      y: 1 / zoomFactor,
    },
    opacity: opacity,
  }}
>
  <Tag
    config={{
      fill: color,
      stroke: tooltip ? color : "transparent",
    }}
  />
  <Text
    config={{
      id: `text${id}`,
      x: 0,
      y: 0,
      text: tooltip,
      fontSize: 12,
      fontStyle: "100",
    }}
  />
</Label>
