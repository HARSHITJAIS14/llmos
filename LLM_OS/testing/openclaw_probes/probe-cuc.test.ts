import { describe, expect, it } from "vitest";
import { parseComputerActResult } from "../plugins/computer-use-contract.js";

const el = { elementRef: "e1", role: "button", bounds: { x: 0, y: 0, width: 1, height: 1 } };

describe("closedness probe", () => {
  it("baseline valid", () => {
    expect(parseComputerActResult({ ok: true, observation: { kind: "window", elements: [el] } })).toMatchObject({ ok: true });
  });
  it("extra key on RESULT", () => {
    let msg = "ACCEPTED";
    try { parseComputerActResult({ ok: true, anchor: "Notion - 150 elements" }); } catch (e) { msg = (e as Error).message; }
    console.log("RESULT-level extra key ->", msg);
    expect(msg).not.toBe("ACCEPTED");
  });
  it("extra key on OBSERVATION", () => {
    let msg = "ACCEPTED";
    try { parseComputerActResult({ ok: true, observation: { kind: "window", truncated: "150 of 402", elements: [el] } }); } catch (e) { msg = (e as Error).message; }
    console.log("OBSERVATION-level extra key ->", msg);
    expect(msg).not.toBe("ACCEPTED");
  });
  it("extra key on ELEMENT item (diff annotation)", () => {
    let msg = "ACCEPTED";
    try { parseComputerActResult({ ok: true, observation: { kind: "window", elements: [{ ...el, change: "appeared" }] } }); } catch (e) { msg = (e as Error).message; }
    console.log("ELEMENT-level extra key ->", msg);
    expect(msg).not.toBe("ACCEPTED");
  });
  it("details accepts arbitrary values but bounded keys", () => {
    expect(parseComputerActResult({ ok: true, details: { anchor: "Notion · 150 elements · obs-1", diff: { appeared: [el] } } })).toMatchObject({ ok: true });
    let msg = "ACCEPTED";
    try { parseComputerActResult({ ok: true, details: { ["k".repeat(129)]: 1 } }); } catch (e) { msg = (e as Error).message; }
    console.log("details key >128 chars ->", msg);
    expect(msg).not.toBe("ACCEPTED");
  });
});
