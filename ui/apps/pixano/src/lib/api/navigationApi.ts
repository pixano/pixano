/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { DEFAULT_DATASET_TABLE_SIZE } from "$lib/constants/pixanoConstants";

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

export const getPageFromItemId = (itemsIds: string[], currentItemId: string): number => {
  // Find the position of the current item in the dataset
  const currentIndex: number = itemsIds.findIndex((item) => item === currentItemId);

  // Calculate the page number of that item (starts from 1)
  return Math.floor(currentIndex / DEFAULT_DATASET_TABLE_SIZE) + 1;
};
