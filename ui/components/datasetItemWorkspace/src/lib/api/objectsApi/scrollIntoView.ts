/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const scrollIntoView = (entity_id: string) => {
  const cardElement = document.querySelector(`#card-object-${entity_id}`);
  const scrollContainer = document.querySelector("#card-object-container") as HTMLElement;

  if (!cardElement || !scrollContainer) return;

  // Wait for layout to stabilize before scrolling
  let attempts = 0;
  const maxAttempts = 10;

  const tryScroll = () => {
    const cardRect = cardElement.getBoundingClientRect();
    const containerRect = scrollContainer.getBoundingClientRect();
    const scrollOffset = cardRect.top - containerRect.top;

    // Check if card is already aligned; if not, scroll
    if (Math.abs(scrollOffset) > 1 && attempts < maxAttempts) {
      scrollContainer.scrollBy({ top: scrollOffset, behavior: "smooth" });
      attempts++;
      requestAnimationFrame(tryScroll);
    }
  };
  requestAnimationFrame(tryScroll);

  const trackElement = document
    .querySelector(`#video-object-${entity_id}`)
    ?.getElementsByClassName("video-tracklet");
  if (trackElement) {
    if (trackElement.length > 0) {
      trackElement[0].scrollIntoView({ block: "center", inline: "center" });
    }
  }
};
