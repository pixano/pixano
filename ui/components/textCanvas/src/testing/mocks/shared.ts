/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { AnnotationType, Reference } from "@pixano/core";

export const mockRef: Reference = {
  id: "1",
  name: "abc",
};

export const mockAnnotationType: AnnotationType = {
  item_ref: mockRef,
  view_ref: mockRef,
  entity_ref: mockRef,
  source_ref: mockRef,
};
