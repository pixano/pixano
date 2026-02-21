<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { DatasetItem } from "$lib/ui";
  import Canvas3D from "../canvas3d/Canvas3D.svelte";

  interface Props {
    selectedItem: DatasetItem;
    resize: number;
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  let { selectedItem, resize }: Props = $props();
</script>

<Canvas3D />
