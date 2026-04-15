/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { SchemaDescriptor } from '$lib/types/dataset';

export interface ViewComposition {
  /** Logical names of Image views */
  images: string[];
  /** Logical names of PointCloud / PointCloudFrame views */
  pointClouds: string[];
  /** Logical names of SequenceFrame views */
  sequences: string[];
  /** Logical names of Text views */
  texts: string[];
}

/**
 * Inspect a dataset's views dict and group each logical name by its base type.
 * The `base` field of each SchemaDescriptor is the Python class name written
 * by the backend (e.g. "Image", "PointCloud", "SequenceFrame", "Text").
 */
export function analyzeViews(
  views: Record<string, SchemaDescriptor> | undefined
): ViewComposition {
  const composition: ViewComposition = {
    images: [],
    pointClouds: [],
    sequences: [],
    texts: [],
  };

  if (!views) return composition;

  for (const [logicalName, descriptor] of Object.entries(views)) {
    const base = descriptor.base ?? '';
    if (base === 'Image') {
      composition.images.push(logicalName);
    } else if (base === 'PointCloud' || base === 'PointCloudFrame') {
      composition.pointClouds.push(logicalName);
    } else if (base === 'SequenceFrame') {
      composition.sequences.push(logicalName);
    } else if (base === 'Text') {
      composition.texts.push(logicalName);
    }
  }

  return composition;
}
