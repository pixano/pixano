<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Check, ReplaceAll, X } from "lucide-svelte";

  import { ToolType } from "@pixano/canvas2d/src/tools";
  import { Annotation, cn, IconButton, type SaveItem, type SelectionTool } from "@pixano/core/src";

  import { addOrUpdateSaveItem } from "../../lib/api/objectsApi";
  import { fusionTool, panTool } from "../../lib/settings/selectionTools";
  import {
    annotations,
    entities,
    merges,
    saveData,
    selectedTool,
  } from "../../lib/stores/datasetItemWorkspaceStores";

  export let selectTool: (tool: SelectionTool) => void;
  export let clearFusionHighlighting: () => void;

  const onValidate = () => {
    let reassoc_anns: Annotation[] = [];
    if ($merges.to_fuse.length > 1) {
      const [reference, ...to_fuse] = $merges.to_fuse;
      to_fuse.forEach((entity) => {
        if (entity.ui.childs) reassoc_anns = [...reassoc_anns, ...entity.ui.childs];
      });
      //change merged annotations entity reference
      annotations.update((anns) =>
        anns.map((ann) => {
          if (reassoc_anns.includes(ann)) {
            if (
              ann.ui.top_entities &&
              ann.ui.top_entities.length > 0 &&
              ann.data.entity_ref.id !== ann.ui.top_entities[0].id
            ) {
              //TODO: if sub entities ! (then we should change top_entities[1] to reference)
              console.error("ERROR: Sub entities currently not managed for fusion.", ann);
              return ann;
            }
            ann.data.entity_ref = { id: reference.id, name: reference.table_info.name };
            ann.ui.top_entities = [reference];
            const save_item: SaveItem = {
              change_type: "update",
              object: ann,
            };
            saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
          }
          return ann;
        }),
      );
      //update entities
      entities.update((ents) => {
        const remaining_ents = ents.filter((ent) => !to_fuse.includes(ent));
        if (remaining_ents.length > 0) {
          remaining_ents.map((ent) => {
            if (ent.id === reference.id) {
              //update reference childs (note: no save needed as 'ui' field is front only)
              ent.ui.childs = ent.ui.childs ? [...ent.ui.childs, ...reassoc_anns] : reassoc_anns;
            }
            return ent;
          });
        }
        return remaining_ents;
      });
      // save deletion of fused entities
      to_fuse.forEach((ent_to_del) => {
        const save_item: SaveItem = {
          change_type: "delete",
          object: ent_to_del,
        };
        saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
      });
    }
    clearFusionHighlighting();
  };

  const onAbort = () => {
    clearFusionHighlighting();
    selectTool(panTool);
  };

  function shortcutHandler(event: KeyboardEvent) {
    if ($selectedTool?.type !== ToolType.Fusion) return;

    const activeElement = document.activeElement;
    if (
      activeElement instanceof HTMLInputElement ||
      activeElement instanceof HTMLTextAreaElement ||
      activeElement?.getAttribute("contenteditable") === "true"
    ) {
      return; // Ignore shortcut when typing text
    }

    switch (event.key) {
      case "Escape":
        onAbort();
        break;
      case "Enter":
      case "s":
      case "S":
        onValidate();
        break;
    }
  }
</script>

<div
  class={cn("flex items-center gap-4", {
    "bg-accent rounded-sm": $selectedTool?.type === ToolType.Fusion,
  })}
>
  <IconButton
    tooltipContent={fusionTool.name}
    on:click={() => selectTool(fusionTool)}
    selected={$selectedTool?.type === ToolType.Fusion}
  >
    <ReplaceAll />
  </IconButton>
  {#if $selectedTool?.type === ToolType.Fusion}
    <IconButton
      tooltipContent={"Validate association (S / Enter)"}
      on:click={onValidate}
      selected={false}
    >
      <Check />
    </IconButton>
    <IconButton tooltipContent={"Abort association (Escape)"} on:click={onAbort} selected={false}>
      <X />
    </IconButton>
  {/if}
</div>
<svelte:window on:keydown={shortcutHandler} />
