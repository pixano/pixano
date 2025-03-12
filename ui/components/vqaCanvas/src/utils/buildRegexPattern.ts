/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const buildRegexPattern = (userRegex: string): string => {
  // Trim any leading/trailing spaces
  userRegex = userRegex.trim();

  // Validate that the user regex contains exactly one capturing group
  const capturingGroups = userRegex.match(/\((?!\?:)/g) || [];
  if (capturingGroups.length !== 1) {
    throw new Error("The user regex must contain exactly one capturing group.");
  }

  // Ensure the regex is valid
  try {
    new RegExp(userRegex);
  } catch (e) {
    throw new Error("Invalid regex: " + (e as Error).message);
  }

  // Insert the user regex into the full pattern
  return `.*${userRegex}.*`;
};
