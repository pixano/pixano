<script lang="ts">
  import type { NavSection } from "../config/navigation";

  interface Props {
    sections: NavSection[];
    currentPath: string;
    basePath?: string;
  }

  let { sections, currentPath, basePath = "/pixano" }: Props = $props();

  // Track which sections are expanded
  let expandedSections: Record<string, boolean> = $state({});

  // Initialize: expand section containing current page
  $effect(() => {
    const newExpanded: Record<string, boolean> = {};
    for (const section of sections) {
      const hasActive = section.items.some(
        (item) =>
          currentPath === `${basePath}${item.href}` ||
          currentPath.startsWith(`${basePath}${item.href}`) ||
          item.children?.some(
            (child) =>
              currentPath === `${basePath}${child.href}` ||
              currentPath.startsWith(`${basePath}${child.href}`)
          )
      );
      newExpanded[section.title] = hasActive || expandedSections[section.title] || false;
    }
    expandedSections = newExpanded;
  });

  function toggleSection(title: string) {
    expandedSections = { ...expandedSections, [title]: !expandedSections[title] };
  }

  function isActive(href: string): boolean {
    const fullHref = `${basePath}${href}`;
    return currentPath === fullHref || currentPath === fullHref.replace(/\/$/, "");
  }

  function isChildActive(href: string): boolean {
    const fullHref = `${basePath}${href}`;
    return currentPath.startsWith(fullHref);
  }

  // Track expanded children
  let expandedChildren: Record<string, boolean> = $state({});

  $effect(() => {
    const newChildExpanded: Record<string, boolean> = {};
    for (const section of sections) {
      for (const item of section.items) {
        if (item.children) {
          newChildExpanded[item.title] =
            isChildActive(item.href || "") ||
            item.children.some((c) => isActive(c.href || "")) ||
            expandedChildren[item.title] ||
            false;
        }
      }
    }
    expandedChildren = newChildExpanded;
  });

  function toggleChild(title: string) {
    expandedChildren = { ...expandedChildren, [title]: !expandedChildren[title] };
  }
</script>

<aside class="sidebar" aria-label="Documentation navigation">
  <nav>
    {#each sections as section}
      <div class="section">
        <button
          class="section-title"
          onclick={() => toggleSection(section.title)}
          aria-expanded={expandedSections[section.title]}
        >
          <span>{section.title}</span>
          <svg
            class="chevron"
            class:rotated={expandedSections[section.title]}
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>

        {#if expandedSections[section.title]}
          <ul class="section-items">
            {#each section.items as item}
              <li>
                {#if item.children}
                  <button
                    class="nav-item parent"
                    class:child-active={isChildActive(item.href || "")}
                    onclick={() => toggleChild(item.title)}
                  >
                    <span>{item.title}</span>
                    <svg
                      class="chevron-sm"
                      class:rotated={expandedChildren[item.title]}
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                  </button>
                  {#if expandedChildren[item.title]}
                    <ul class="child-items">
                      {#each item.children as child}
                        <li>
                          <a
                            href="{basePath}{child.href}"
                            class="nav-item child"
                            class:active={isActive(child.href || "")}
                            aria-current={isActive(child.href || "") ? "page" : undefined}
                          >
                            {child.title}
                          </a>
                        </li>
                      {/each}
                    </ul>
                  {/if}
                {:else}
                  <a
                    href="{basePath}{item.href}"
                    class="nav-item"
                    class:active={isActive(item.href || "")}
                    aria-current={isActive(item.href || "") ? "page" : undefined}
                  >
                    {item.title}
                  </a>
                {/if}
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    {/each}
  </nav>
</aside>

<style>
  /* ── Glassmorphic Sidebar Panel ── */
  .sidebar {
    width: var(--px-sidebar-width, 280px);
    position: sticky;
    top: calc(var(--px-header-height, 64px) + 2.5rem);
    height: calc(100vh - var(--px-header-height, 64px) - 4rem);
    overflow-y: auto;
    padding: 1.25rem 1rem;
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

  .section {
    margin-bottom: 0.5rem;
  }

  .section-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 0.5rem 0.75rem;
    font-family: var(--px-font-ui);
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--px-text-muted);
    background: none;
    border: none;
    cursor: pointer;
    border-radius: var(--px-radius-sm);
    transition: all 200ms ease;
  }

  .section-title:hover {
    color: var(--px-text);
    background: var(--px-bg-elevated);
  }

  .chevron,
  .chevron-sm {
    transition: transform 200ms ease;
    flex-shrink: 0;
  }

  .chevron.rotated,
  .chevron-sm.rotated {
    transform: rotate(180deg);
  }

  .section-items,
  .child-items {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .child-items {
    padding-left: 0.75rem;
    border-left: 1px solid var(--px-border);
    margin-left: 1rem;
  }

  .nav-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 0.4rem 0.75rem;
    font-size: 0.85rem;
    font-weight: 400;
    color: var(--px-text-secondary);
    text-decoration: none;
    border-radius: var(--px-radius-sm);
    border: none;
    background: none;
    cursor: pointer;
    transition:
      all 150ms ease,
      box-shadow 200ms ease;
    line-height: 1.5;
  }

  a.nav-item:hover,
  button.nav-item:hover {
    color: var(--px-text);
    background: var(--px-bg-elevated);
    text-decoration: none;
    text-shadow: none;
  }

  .nav-item.active {
    color: var(--px-accent);
    background: var(--px-bg-elevated);
    font-weight: 500;
    position: relative;
    box-shadow: 0 0 12px rgba(240, 108, 186, 0.12);
  }

  .nav-item.active::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.3rem;
    bottom: 0.3rem;
    width: 3px;
    background: var(--px-accent);
    border-radius: 0 2px 2px 0;
    box-shadow: 0 0 8px rgba(240, 108, 186, 0.4);
  }

  .nav-item.child {
    font-size: 0.8rem;
    padding: 0.3rem 0.75rem;
  }

  .parent.child-active {
    color: var(--px-accent);
    font-weight: 500;
  }
</style>
