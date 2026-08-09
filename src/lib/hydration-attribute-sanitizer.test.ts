// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { describe, expect, it } from "vitest";

import { installHydrationAttributeSanitizer } from "./hydration-attribute-sanitizer";

describe("installHydrationAttributeSanitizer", () => {
  it("removes only known injected attributes from existing markup", () => {
    document.body.innerHTML = `
      <main id="content" data-testid="main" bis_skin_checked="1" bis_register="1" __processed_123__="1">
        <p class="copy">GamePulse</p>
      </main>
    `;

    const stop = installHydrationAttributeSanitizer(document);
    const main = document.querySelector("main");

    expect(main).not.toBeNull();
    expect(main).not.toHaveAttribute("bis_skin_checked");
    expect(main).not.toHaveAttribute("bis_register");
    expect(main).not.toHaveAttribute("__processed_123__");
    expect(main).toHaveAttribute("id", "content");
    expect(main).toHaveAttribute("data-testid", "main");
    expect(main).toHaveTextContent("GamePulse");

    stop();
  });

  it("removes known attributes added during the hydration window", async () => {
    document.body.innerHTML = `<main id="content"></main>`;
    const stop = installHydrationAttributeSanitizer(document);
    const main = document.querySelector("main");
    const added = document.createElement("section");

    main?.setAttribute("__processed_later__", "1");
    main?.setAttribute("aria-label", "Game content");
    added.setAttribute("bis_skin_checked", "1");
    added.textContent = "More GamePulse";
    document.body.append(added);

    await new Promise<void>((resolve) => setTimeout(resolve, 0));

    expect(main).not.toHaveAttribute("__processed_later__");
    expect(main).toHaveAttribute("aria-label", "Game content");
    expect(added).not.toHaveAttribute("bis_skin_checked");
    expect(added).toHaveTextContent("More GamePulse");

    stop();
  });
});
