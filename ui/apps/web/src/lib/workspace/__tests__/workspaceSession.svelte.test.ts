/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { WorkspaceSession } from "../workspaceSession.svelte.js";

describe("WorkspaceSession", () => {
  it("starts with null datasetId and recordId", () => {
    const session = new WorkspaceSession();
    expect(session.datasetId).toBeNull();
    expect(session.recordId).toBeNull();
  });

  it("stores assigned datasetId and recordId", () => {
    const session = new WorkspaceSession();
    session.datasetId = "ds-1";
    session.recordId = "rec-42";

    expect(session.datasetId).toBe("ds-1");
    expect(session.recordId).toBe("rec-42");
  });

  it("reset() clears both fields back to null", () => {
    const session = new WorkspaceSession();
    session.datasetId = "ds-1";
    session.recordId = "rec-42";

    session.reset();

    expect(session.datasetId).toBeNull();
    expect(session.recordId).toBeNull();
  });

  it("reset() is idempotent on an already-empty session", () => {
    const session = new WorkspaceSession();
    session.reset();
    expect(session.datasetId).toBeNull();
    expect(session.recordId).toBeNull();
  });

  it("multiple sessions are independent", () => {
    const a = new WorkspaceSession();
    const b = new WorkspaceSession();
    a.datasetId = "ds-a";

    expect(b.datasetId).toBeNull();
  });
});
