/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Component } from "svelte";

/**
 * Wraps a Svelte component + its props for deferred rendering by FlexRender.
 */
export class RenderComponentConfig<TProps extends Record<string, unknown>> {
  constructor(
    public component: Component<TProps>,
    public props: TProps,
  ) {}
}

/**
 * Create a renderable component config for use with FlexRender.
 */
export function renderComponent<TProps extends Record<string, unknown>>(
  component: Component<TProps>,
  props: TProps,
): RenderComponentConfig<TProps> {
  return new RenderComponentConfig(component, props);
}
