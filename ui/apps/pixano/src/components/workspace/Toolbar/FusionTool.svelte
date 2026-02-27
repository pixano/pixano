<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Check, ArrowsLeftRight, X } from "phosphor-svelte";

  import { ToolType, fusionTool, panTool, type SelectionTool } from "$lib/tools";
  import { Annotation, IconButton, cn } from "$lib/ui";

  import { saveTo } from "$lib/utils/saveItemUtils";
  import {
    annotations,
    entities,
    merges,
    selectedTool,
  } from "$lib/stores/workspaceStores.svelte";

  interface Props {
    selectTool: (tool: SelectionTool) => void;
    clearFusionHighlighting: () => void;
  }

  let { selectTool, clearFusionHighlighting }: Props = $props();

  const onValidate = () => {
    let reassoc_anns: Annotation[] = [];
    if (merges.value.to_fuse.length > 1) {
      const [reference, ...to_fuse] = merges.value.to_fuse;
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
              ann.data.entity_id !== ann.ui.top_entities[0].id
            ) {
              //TODO: if sub entities ! (then we should change top_entities[1] to reference)
              console.error("ERROR: Sub entities currently not managed for fusion.", ann);
              return ann;
            }
            ann.data.entity_id = reference.id;
            ann.ui.top_entities = [reference];
            saveTo("update", ann);
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
        saveTo("delete", ent_to_del);
      });
    }
    clearFusionHighlighting();
  };

  const onAbort = () => {
    clearFusionHighlighting();
    selectTool(panTool);
  };

  function shortcutHandler(event: KeyboardEvent) {
    if (selectedTool.value?.type !== ToolType.Fusion) return;

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
  class={cn(
    "flex items-center gap-1 transition-all duration-300 p-0.5 rounded-xl border border-transparent",
    {
      "bg-muted/40 border-border/20 shadow-inner": selectedTool.value?.type === ToolType.Fusion,
    },
  )}
>
  <IconButton
    tooltipContent={fusionTool.name}
    onclick={() => selectTool(fusionTool)}
    class={cn(
      "h-8 w-8 transition-all duration-300 hover:bg-accent/60",
      selectedTool.value?.type === ToolType.Fusion ? "text-primary" : "text-foreground",
    )}
  >
    <ArrowsLeftRight weight="regular" class="h-4.5 w-4.5" />
  </IconButton>
  {#if selectedTool.value?.type === ToolType.Fusion}
    <div
      class="flex items-center gap-0.5 animate-in fade-in slide-in-from-left-1 duration-500 bg-background/60 backdrop-blur-sm rounded-lg p-0.5 border border-border/40 shadow-sm ml-0.5"
    >
      <IconButton
        tooltipContent={"Validate association (S / Enter)"}
        onclick={onValidate}
        class="h-8 w-8 text-success/80 hover:bg-success/5"
      >
        <Check class="h-4.5 w-4.5" />
      </IconButton>
      <IconButton
        tooltipContent={"Abort association (Escape)"}
        onclick={onAbort}
        class="h-8 w-8 text-destructive/80 hover:bg-destructive/5"
      >
        <X class="h-4.5 w-4.5" />
      </IconButton>
    </div>
  {/if}
</div>
<svelte:window onkeydown={shortcutHandler} />
