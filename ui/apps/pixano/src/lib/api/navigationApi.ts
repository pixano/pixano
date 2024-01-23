import type { DatasetItem } from "@pixano/core/src";

export const findSelectedItem = (
  direction: "previous" | "next",
  datasetItems: DatasetItem[],
  currentItemId: string,
) => {
  const currentIndex: number = datasetItems.findIndex((item) => item.id === currentItemId);
  let selectedId: string | undefined;
  if (currentIndex !== -1) {
    const nextIndex = direction === "previous" ? currentIndex - 1 : currentIndex + 1;
    if (nextIndex === -1) {
      selectedId = datasetItems[datasetItems.length - 1].id;
    }
    if (nextIndex === datasetItems.length) {
      selectedId = datasetItems[0].id;
    }
    if (nextIndex >= 0 && nextIndex < datasetItems.length) {
      const nextItemId = datasetItems[nextIndex].id;
      selectedId = nextItemId;
    }
  }
  return selectedId;
};
