import { describe, expect, it } from "vitest";
import { parseComputerActResult } from "../plugins/computer-use-contract.js";
import { computerActResultText } from "../agents/tools/computer-tool-result.js";

describe("bounds requiredness + model-visible size", () => {
  it("element WITHOUT bounds is rejected", () => {
    let msg = "ACCEPTED";
    try {
      parseComputerActResult({
        ok: true,
        observation: { kind: "window", elements: [{ elementRef: "@s8f3k2p9:e1", role: "AXButton", label: "Share" }] },
      });
    } catch (e) { msg = (e as Error).message; }
    console.log("no-bounds element ->", msg);
    expect(msg).not.toBe("ACCEPTED");
  });

  it("partial bounds rejected", () => {
    let msg = "ACCEPTED";
    try {
      parseComputerActResult({
        ok: true,
        observation: { kind: "window", elements: [{ elementRef: "@s8f3k2p9:e1", role: "AXButton", bounds: { x: 1, y: 2 } }] },
      });
    } catch (e) { msg = (e as Error).message; }
    console.log("partial-bounds element ->", msg);
    expect(msg).not.toBe("ACCEPTED");
  });

  it("measures model-visible chars for 150 filtered elements", () => {
    const roles = ["AXButton","AXStaticText","AXTextField","AXMenuItem","AXCheckBox","AXLink","AXRow","AXGroup","AXImage","AXPopUpButton"];
    const labels = ["Share","New page","Search","Untitled","Add a comment","Favorites","Settings & members","Trash","Templates","Import","OK","Cancel","Done","Back","Forward","Reload","Home","Table of contents","Comments","Updates"];
    const mk = (n: number) => ({
      elementRef: `@s8f3k2p9:e${n}`,
      role: roles[n % roles.length]!,
      label: labels[n % labels.length]!,
      bounds: { x: 100 + ((n * 7) % 1400), y: 40 + ((n * 13) % 800), width: 40 + ((n * 3) % 200), height: 20 + (n % 3) * 8 },
    });
    for (const count of [50, 150, 200]) {
      const result = parseComputerActResult({
        ok: true,
        effect: "confirmed",
        observation: {
          kind: "window",
          observationId: "s8f3k2p9",
          elements: Array.from({ length: count }, (_, i) => mk(i + 1)),
        },
      });
      const text = computerActResultText("get_window_state", result);
      console.log(`${count} elements -> ${text.length} chars | @4c/t ${Math.round(text.length / 4)} tok | @3.5c/t ${Math.round(text.length / 3.5)} tok`);
    }
    // floor: no labels, zero bounds
    const floor = parseComputerActResult({
      ok: true,
      observation: { kind: "window", elements: Array.from({ length: 150 }, (_, i) => ({ elementRef: `@s8f3k2p9:e${i + 1}`, role: "AXGroup", bounds: { x: 0, y: 0, width: 0, height: 0 } })) },
    });
    const floorText = computerActResultText("get_window_state", floor);
    console.log(`FLOOR 150 (no label, zero bounds) -> ${floorText.length} chars | @4c/t ${Math.round(floorText.length / 4)} tok`);
    expect(floorText.length).toBeGreaterThan(6000);
  });
});
