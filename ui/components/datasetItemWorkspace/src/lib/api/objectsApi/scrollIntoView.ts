/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const scrollIntoView = (entity_id: string) => {
  const cardElement = document.querySelector(`#card-object-${entity_id}`);
  if (cardElement) {
    cardElement.scrollIntoView({ block: "center" });
  }
  const trackElement = document.querySelector(`#video-object-${entity_id}`);
  if (trackElement) {
    trackElement.scrollIntoView({ block: "center" });
  }
};
