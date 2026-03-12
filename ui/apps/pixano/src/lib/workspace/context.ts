import { getContext, setContext } from "svelte";

import type { FeaturesValues } from "$lib/types/dataset";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

const WORKSPACE_CONTEXT_KEY = Symbol("workspace-context");

export interface WorkspaceContextValue {
  readonly manifest: WorkspaceManifest;
  readonly featureValues: FeaturesValues;
}

export function setWorkspaceContext(value: WorkspaceContextValue): WorkspaceContextValue {
  setContext(WORKSPACE_CONTEXT_KEY, value);
  return value;
}

export function getWorkspaceContext(): WorkspaceContextValue {
  return getContext<WorkspaceContextValue>(WORKSPACE_CONTEXT_KEY);
}
