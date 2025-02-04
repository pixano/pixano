/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const answerChoicesToCheckboxsState = (answerChoices: string[]) => {
  const checked = Array.from({ length: answerChoices.length }).map(() => false);
  answerChoices.forEach((c) => {
    checked[c.charCodeAt(0) - 65] = true;
  });
  return checked;
};
