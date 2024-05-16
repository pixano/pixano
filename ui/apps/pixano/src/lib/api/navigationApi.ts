/**
 * @copyright CEA
 * @author CEA
 * @license CECILL
 *
 * This software is a collaborative computer program whose purpose is to
 * generate and explore labeled data for computer vision applications.
 * This software is governed by the CeCILL-C license under French law and
 * abiding by the rules of distribution of free software. You can use,
 * modify and/ or redistribute the software under the terms of the CeCILL-C
 * license as circulated by CEA, CNRS and INRIA at the following URL
 *
 * http://www.cecill.info
 */

// Find the id of the neighbor item
export const findNeighborItemId = (
  itemsIds: string[],
  direction: "previous" | "next",
  currentItemId: string,
): string | undefined => {
  // Find the position of the current item in the dataset
  const currentIndex: number = itemsIds.findIndex((item) => item === currentItemId);

  // If the current item's position has been found
  if (currentIndex !== -1) {
    // Determine next index following the proper direction
    const nextIndex = direction === "previous" ? currentIndex - 1 : currentIndex + 1;

    // If there is no previous item, loop back to the last item
    if (nextIndex === -1) return itemsIds[itemsIds.length - 1];

    // If there is no next item, loop back to the first item
    if (nextIndex === itemsIds.length) return itemsIds[0];

    // Else return the item id
    return itemsIds[nextIndex];
  }
};
