<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { getContext } from "svelte";

  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

  const manager = getContext<WorkspaceManager>("workspaceManager");
</script>

<span data-testid="preset-name">{manager.presetName}</span>
