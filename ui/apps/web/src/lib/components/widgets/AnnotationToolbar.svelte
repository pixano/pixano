<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Save } from "lucide-svelte";
  import type { Snippet } from "svelte";

  import type { ToolDefinition } from "$lib/annotations/scene/tool.js";

  interface Props {
    /** Toolbar entries (TOOLS_2D / TOOLS_3D / …); each renders an icon button. */
    tools: readonly ToolDefinition[];
    activeToolId: string;
    /** Tool to fall back to when toggling off the active one. */
    defaultToolId: string;
    onSelectTool: (id: string) => void;
    /** Count shown as "{n} unsaved" (widget- or record-scoped, host's choice). */
    pendingCount: number;
    saveDisabled: boolean;
    saving: boolean;
    saveError?: string | null;
    onSave: () => void;
    ariaLabel: string;
    /** Widget-specific controls rendered right after the tool buttons. */
    controls?: Snippet;
  }

  let {
    tools,
    activeToolId,
    defaultToolId,
    onSelectTool,
    pendingCount,
    saveDisabled,
    saving,
    saveError = null,
    onSave,
    ariaLabel,
    controls,
  }: Props = $props();
</script>

<div
  class="flex items-center gap-0.5 border-b border-border bg-muted/30 px-1.5 py-0.5"
  role="toolbar"
  aria-label={ariaLabel}
  tabindex="0"
  onpointerdown={(e) => e.stopPropagation()}
>
  {#each tools as tool (tool.id)}
    <button
      type="button"
      onclick={() => onSelectTool(activeToolId === tool.id ? defaultToolId : tool.id)}
      title={tool.label}
      class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {activeToolId === tool.id ? 'bg-accent text-accent-foreground' : ''}"
    >
      <tool.icon class="h-3.5 w-3.5" />
    </button>
  {/each}

  {#if controls}
    <span class="mx-1 h-4 w-px bg-border"></span>
    {@render controls()}
  {/if}

  <div class="flex-1"></div>

  {#if pendingCount > 0}
    <span class="text-[10px] text-muted-foreground">{pendingCount} unsaved</span>
  {/if}
  {#if saveError}
    <span class="max-w-[200px] truncate text-[10px] text-destructive" title={saveError}>Save failed</span>
  {/if}
  <button
    type="button"
    onclick={onSave}
    disabled={saveDisabled}
    title="Save annotations"
    class="flex items-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground disabled:opacity-40"
  >
    <Save class="h-3.5 w-3.5" />
    {saving ? "Saving…" : "Save"}
  </button>
</div>
