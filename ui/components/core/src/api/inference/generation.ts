/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { CondititionalGenerationTextImageInput, Message } from "../../lib/types";

export async function conditional_generation_text_image(
  input: CondititionalGenerationTextImageInput,
): Promise<Message | null> {
  try {
    const response = await fetch("/inference/tasks/conditional_generation/text-image", {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(input),
    });

    if (!response.ok) {
      // console.log(
      //   "api.conditional_generation_text_image -",
      //   response.status,
      //   response.statusText,
      //   await response.text(),
      // );
      return null;
    }

    return (await response.json()) as Message;
  } catch (e) {
    console.error("api.conditional_generation_text_image -", e);
    return null;
  }
}
