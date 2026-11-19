/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { ApiError, serverDetail } from "../apiClient";

function failure(status: number, body: unknown): ApiError {
  return new ApiError("failed", status, typeof body === "string" ? body : JSON.stringify(body));
}

describe("serverDetail", () => {
  it("reads a sentence, or the first of a list of refusals", () => {
    const sentence = failure(409, { detail: "It cannot change." });
    const refusals = failure(422, { detail: [{ msg: "Field required" }, { msg: "Too long" }] });

    expect([serverDetail(sentence), serverDetail(refusals)]).toEqual([
      "It cannot change.",
      "Field required",
    ]);
  });

  it("reads the message of a coded error, as a dataset busy being written answers", () => {
    const busy = failure(409, {
      detail: {
        code: "dataset_busy",
        message: "Dataset is being modified; retry when it is done.",
      },
    });

    expect(serverDetail(busy)).toBe("Dataset is being modified; retry when it is done.");
  });

  it("is null for an error without the server's words", () => {
    expect(serverDetail(failure(502, "<html>Bad gateway</html>"))).toBeNull();
    expect(serverDetail(failure(500, { detail: "" }))).toBeNull();
    expect(serverDetail(failure(409, { detail: { code: "dataset_busy" } }))).toBeNull();
    expect(serverDetail(new Error("offline"))).toBeNull();
  });
});
