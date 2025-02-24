/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Annotation } from "../../lib/types"
import type {
  CondititionalGenerationTextImageInput,
} from "../../lib/types";

export async function conditional_generation_text_image(
  input: CondititionalGenerationTextImageInput,
): Promise<Annotation | null> {
  let output: Annotation | null = null;

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
      console.log(
        "api.conditional_generation_text_image -",
        response.status,
        response.statusText,
        await response.text(),
      );
    } else {
      output = (await response.json()) as Annotation;
    }
  } catch (e) {
    console.log("api.conditional_generation_text_image -", e);
  }
  return output;
}
