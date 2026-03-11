/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Component } from "svelte";

import { WorkspaceType } from "$lib/ui";
import type { WorkspaceViewerItem } from "$lib/types/workspace";

import WorkspaceImage from "./variants/WorkspaceImage.svelte";
import WorkspaceVideo from "./variants/WorkspaceVideo.svelte";
import WorkspaceVqa from "./variants/WorkspaceVqa.svelte";
import WorkspaceEntityLinking from "./variants/WorkspaceEntityLinking.svelte";
import Workspace3D from "./variants/Workspace3D.svelte";

type VariantProps = { selectedItem: WorkspaceViewerItem; resize: number };

const registry: Record<string, Component<VariantProps>> = {
  [WorkspaceType.IMAGE]: WorkspaceImage,
  [WorkspaceType.VIDEO]: WorkspaceVideo,
  [WorkspaceType.IMAGE_VQA]: WorkspaceVqa,
  [WorkspaceType.IMAGE_TEXT_ENTITY_LINKING]: WorkspaceEntityLinking,
  [WorkspaceType.PCL_3D]: Workspace3D,
};

export function resolveWorkspaceVariant(type: WorkspaceType | undefined): Component<VariantProps> {
  if (!type || type === WorkspaceType.UNDEFINED) return WorkspaceImage;
  return registry[type] ?? WorkspaceImage;
}
