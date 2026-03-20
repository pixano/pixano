<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { onMount } from "svelte";

  interface Heading {
    depth: number;
    slug: string;
    text: string;
  }

  interface Props {
    headings: Heading[];
  }

  let { headings }: Props = $props();

  let activeId = $state("");

  onMount(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            activeId = entry.target.id;
          }
        }
      },
      {
        rootMargin: "-100px 0px -70% 0px",
        threshold: 0,
      }
    );

    // Observe all heading elements
    const headingElements = headings
      .map((h) => document.getElementById(h.slug))
      .filter(Boolean) as HTMLElement[];

    for (const el of headingElements) {
      observer.observe(el);
    }

    return () => observer.disconnect();
  });

  function handleClick(slug: string) {
    const element = document.getElementById(slug);
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
      activeId = slug;
    }
  }

  // Filter to h2 and h3 only
  const filteredHeadings = $derived(
    headings.filter((h) => h.depth === 2 || h.depth === 3)
  );
</script>

{#if filteredHeadings.length > 0}
  <aside class="toc" aria-label="Table of contents">
    <div class="toc-header">On this page</div>
    <nav>
      <ul class="toc-list">
        {#each filteredHeadings as heading}
          <li>
            <button
              class="toc-link"
              class:active={activeId === heading.slug}
              class:depth-3={heading.depth === 3}
              onclick={() => handleClick(heading.slug)}
            >
              {heading.text}
            </button>
          </li>
        {/each}
      </ul>
    </nav>
  </aside>
{/if}

<style>
  /* ── Glassmorphic ToC Panel ── */
  .toc {
    width: var(--px-toc-width, 240px);
    position: sticky;
    top: calc(var(--px-header-height, 64px) + 2.5rem);
    max-height: calc(100vh - var(--px-header-height, 64px) - 4rem);
    overflow-y: auto;
    padding: 1.25rem;
    background: var(--px-glass-bg);
    backdrop-filter: var(--px-glass-blur);
    -webkit-backdrop-filter: var(--px-glass-blur);
    border: 1px solid var(--px-glass-border);
    border-radius: var(--px-radius-lg);
    box-shadow: var(--px-glass-shadow-inset);
    flex-shrink: 0;
    transition:
      background var(--px-transition),
      border-color var(--px-transition);
  }

  .toc-header {
    font-family: var(--px-font-ui);
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--px-text-muted);
    padding: 0 0.5rem;
    margin-bottom: 0.75rem;
  }

  .toc-list {
    list-style: none;
    margin: 0;
    padding: 0;
    border-left: 1px solid var(--px-border);
  }

  .toc-link {
    display: block;
    width: 100%;
    text-align: left;
    padding: 0.3rem 0.75rem;
    font-size: 0.78rem;
    line-height: 1.5;
    color: var(--px-text-muted);
    background: none;
    border: none;
    border-left: 2px solid transparent;
    margin-left: -1px;
    cursor: pointer;
    transition:
      all 150ms ease,
      text-shadow 200ms ease;
    text-overflow: ellipsis;
    overflow: hidden;
    white-space: nowrap;
  }

  .toc-link:hover {
    color: var(--px-text);
  }

  .toc-link.active {
    color: var(--px-accent);
    border-left-color: var(--px-accent);
    font-weight: 500;
    text-shadow: 0 0 8px rgba(240, 108, 186, 0.25);
  }

  .toc-link.depth-3 {
    padding-left: 1.5rem;
    font-size: 0.75rem;
  }
</style>
