/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Annotation } from "@pixano/core";

import type { ObjectProperties } from "../../types/datasetItemWorkspaceTypes";

export const mapObjectWithNewStatus = (
  allObjects: Annotation[],
  objectsToAnnotate: Annotation[],
  status: "accepted" | "rejected",
  features: ObjectProperties = {}, // eslint-disable-line @typescript-eslint/no-unused-vars
): Annotation[] => {
  //TODO (preAnnotation)
  return allObjects;

  // const nextObjectId = objectsToAnnotate[1]?.id;
  // return allObjects.map((object) => {
  //   if (object.id === nextObjectId) {
  //     object.ui.displayControl.highlighted = "self";
  //   } else {
  //     object.ui.displayControl.highlighted = "none";
  //   }
  //   if (object.id === objectsToAnnotate[0]?.id) {
  //     object.review_state = status;
  //     Object.keys(features || {}).forEach((key) => {
  //       if (object[features[key]]) {
  //         object[features[key]] = features[key];
  //       }
  //     });
  //   }
  //   return object;
  // });
};
