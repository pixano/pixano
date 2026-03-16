<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Canvas3D from "../canvas3d/Canvas3D.svelte";
  import type { WorkspaceViewerItem } from "$lib/types/workspace";

  interface Props {
    selectedItem: WorkspaceViewerItem;
    resize: number;
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  let { selectedItem, resize }: Props = $props();
</script>

<Canvas3D />
