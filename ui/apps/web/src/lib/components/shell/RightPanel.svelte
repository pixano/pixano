<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    Eye,
    EyeOff,
    Layers,
    LayoutGrid,
    MessageSquare,
    RotateCcw,
    ScanSearch,
  } from "lucide-svelte";

  import EntitiesPanel from "./EntitiesPanel.svelte";
  import SaveAnnotationForm from "./SaveAnnotationForm.svelte";
  // Measured here, next to the grid, so the manager stays environment-agnostic
  // — the same split `LeftPanel` uses when it opens a record.
  import { measureGridViewport } from "$lib/workspace/layoutPlanner.js";
  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

  interface Props {
    manager: WorkspaceManager;
  }

  let { manager }: Props = $props();

  let activeTab = $state<"inspector" | "entities" | "agent">("inspector");

  // Locking the workspace means "don't rearrange my widgets while I annotate",
  // so it covers every control that can move a widget — not just dragging.
  // Visibility is one of them: hiding a widget compacts its neighbours and the
  // grid then stores the result as the dataset's arrangement, which is exactly
  // what the lock exists to prevent.
  const locked = $derived(!manager.editMode);
  const LOCKED_HINT = "Unlock the workspace to rearrange the widgets";

  const LAYOUT_ACTION_CLASS =
    "flex items-center gap-1 rounded-md border border-border px-1.5 py-0.5 text-[10px] " +
    "text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground " +
    "disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent " +
    "disabled:hover:text-muted-foreground";

  // Surface the entity form as soon as a drawn box is awaiting its entity.
  $effect(() => {
    if (manager.pendingAnnotation) activeTab = "entities";
  });

  const tabs = [
    { id: "inspector" as const, label: "Inspector", icon: ScanSearch },
    { id: "entities" as const, label: "Entities", icon: Layers },
    { id: "agent" as const, label: "Agent", icon: MessageSquare },
  ];
</script>

<div class="flex h-full flex-col bg-background">
  <!-- Tab bar -->
  <div class="flex h-10 items-center border-b border-border">
    {#each tabs as tab (tab.id)}
      {@const Icon = tab.icon}
      <button
        onclick={() => (activeTab = tab.id)}
        class="flex h-full flex-1 items-center justify-center gap-1.5 text-xs font-medium transition-colors
					{activeTab === tab.id
          ? 'border-b-2 border-primary text-foreground'
          : 'text-muted-foreground hover:text-foreground'}"
      >
        <Icon class="h-3.5 w-3.5" />
        {tab.label}
      </button>
    {/each}
  </div>

  <!-- Tab content -->
  <div class="flex-1 overflow-y-auto">
    {#if activeTab === "entities"}
      <SaveAnnotationForm {manager} />
      {#if manager.recordId !== null}
        <EntitiesPanel {manager} />
      {:else}
        <div class="p-3">
          <p class="text-xs text-muted-foreground">Open a record to inspect its entities.</p>
        </div>
      {/if}
    {:else if activeTab === "inspector"}
      <div class="p-3">
        <h4 class="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Properties
        </h4>

        {#if manager.widgetCount > 0}
          <div class="mb-3 flex flex-wrap items-center gap-1.5">
            <button
              onclick={() => manager.restoreOpeningLayout()}
              disabled={locked || !manager.hasOpeningLayout}
              title={locked ? LOCKED_HINT : "Put the widgets back where this record opened them"}
              class={LAYOUT_ACTION_CLASS}
            >
              <RotateCcw class="h-3 w-3" />
              Reset layout
            </button>
            <button
              onclick={() => manager.fitLayoutToViewport(measureGridViewport())}
              disabled={locked}
              title={locked ? LOCKED_HINT : "Show every widget and tile them to fit the screen"}
              class={LAYOUT_ACTION_CLASS}
            >
              <LayoutGrid class="h-3 w-3" />
              Fit layout
            </button>
          </div>

          <div class="space-y-2">
            {#each manager.widgets as widget (widget.id)}
              <div
                class="rounded-md border border-border bg-card p-2 transition-opacity {widget.hidden
                  ? 'opacity-50'
                  : ''}"
              >
                <div class="flex items-center gap-2">
                  <button
                    onclick={() => manager.toggleWidgetVisibility(widget.id)}
                    disabled={locked}
                    title={locked ? LOCKED_HINT : widget.hidden ? "Show widget" : "Hide widget"}
                    class="shrink-0 text-muted-foreground transition-colors hover:text-foreground
                      disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:text-muted-foreground"
                  >
                    {#if widget.hidden}
                      <EyeOff class="h-3.5 w-3.5" />
                    {:else}
                      <Eye class="h-3.5 w-3.5" />
                    {/if}
                  </button>
                  <span
                    class="flex-1 truncate text-xs font-medium {widget.hidden
                      ? 'text-muted-foreground line-through'
                      : 'text-card-foreground'}"
                  >
                    {widget.title}
                  </span>
                  <span
                    class="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
                  >
                    {widget.extensionName}
                  </span>
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-xs text-muted-foreground">No widgets in workspace.</p>
        {/if}
      </div>
    {:else if activeTab === "agent"}
      <div class="flex h-full flex-col">
        <!-- Chat messages -->
        <div class="flex-1 p-3">
          <div class="flex flex-col gap-3">
            <div class="rounded-lg bg-muted/50 px-3 py-2">
              <p class="text-xs text-muted-foreground">
                AI Agent ready. Ask questions about your dataset or request annotations.
              </p>
            </div>
          </div>
        </div>

        <!-- Chat input -->
        <div class="border-t border-border p-2">
          <div class="flex gap-2">
            <input
              type="text"
              placeholder="Ask the agent..."
              class="flex-1 rounded-md border border-input bg-muted/50 px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <button
              class="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    {/if}
  </div>
</div>
