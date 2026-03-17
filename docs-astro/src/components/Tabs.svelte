<script lang="ts">
  /**
   * Interactive Tabs component — replacement for MkDocs pymdownx.tabbed.
   *
   * Usage from MDX:
   *   <Tabs labels={["Python", "Bash", "Docker"]}>
   *     <div slot="tab-0">Python content</div>
   *     <div slot="tab-1">Bash content</div>
   *     <div slot="tab-2">Docker content</div>
   *   </Tabs>
   */

  import type { Snippet } from "svelte";

  interface Props {
    labels: string[];
    children?: Snippet;
  }

  let { labels, children }: Props = $props();
  let activeIndex = $state(0);

  function selectTab(index: number) {
    activeIndex = index;
  }
</script>

<div class="tabs-wrapper">
  <div class="tabs-header" role="tablist">
    {#each labels as label, i}
      <button
        class="tab-button"
        class:active={activeIndex === i}
        role="tab"
        aria-selected={activeIndex === i}
        onclick={() => selectTab(i)}
      >
        {label}
      </button>
    {/each}
    <div
      class="tab-indicator"
      style="left: {(activeIndex / labels.length) * 100}%; width: {100 / labels.length}%"
    ></div>
  </div>
  <div class="tabs-content">
    {#each labels as _, i}
      <div
        class="tab-panel"
        class:active={activeIndex === i}
        role="tabpanel"
        aria-hidden={activeIndex !== i}
      >
        {#if activeIndex === i}
          {@render children?.()}
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  .tabs-wrapper {
    margin: 1.5rem 0;
    border: 1px solid var(--px-border);
    border-radius: var(--px-radius);
    overflow: hidden;
    box-shadow: var(--px-shadow-sm);
  }

  .tabs-header {
    display: flex;
    position: relative;
    background: var(--px-bg-alt);
    border-bottom: 1px solid var(--px-border);
  }

  .tab-button {
    flex: 1;
    padding: 0.65rem 1rem;
    font-family: var(--px-font-body);
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--px-text-muted);
    background: none;
    border: none;
    cursor: pointer;
    transition: color 200ms ease;
    position: relative;
    z-index: 1;
  }

  .tab-button:hover {
    color: var(--px-text);
  }

  .tab-button.active {
    color: var(--px-primary);
    font-weight: 600;
  }

  .tab-indicator {
    position: absolute;
    bottom: 0;
    height: 2px;
    background: var(--px-primary);
    transition: left 200ms ease, width 200ms ease;
    border-radius: 1px 1px 0 0;
  }

  .tabs-content {
    background: var(--px-bg);
  }

  .tab-panel {
    display: none;
    padding: 1rem 1.25rem;
  }

  .tab-panel.active {
    display: block;
    animation: fadeIn 200ms ease-out;
  }

  .tab-panel :global(p:last-child) {
    margin-bottom: 0;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
</style>
