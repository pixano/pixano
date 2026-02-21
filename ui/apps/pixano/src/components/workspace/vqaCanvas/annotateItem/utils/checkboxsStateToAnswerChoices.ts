/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

const A_ASCII_CODE = 65;

export const checkboxsStateToAnswerChoices = (checkboxsState: boolean[]) => {
  return checkboxsState
    .map((c, i) => (c === true ? String.fromCharCode(i + A_ASCII_CODE) : null))
    .filter((c) => c !== null);
};
