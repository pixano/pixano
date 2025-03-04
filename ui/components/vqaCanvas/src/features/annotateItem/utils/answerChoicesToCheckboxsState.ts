/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

const A_ASCII_CODE = 65;

export const answerChoicesToCheckboxsState = (answerChoices: string[]) => {
  const checked = Array.from({ length: answerChoices.length }).map(() => false);
  answerChoices.forEach((c) => {
    checked[c.charCodeAt(0) - A_ASCII_CODE] = true;
  });
  return checked;
};
