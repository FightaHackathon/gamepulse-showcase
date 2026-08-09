export function installHydrationAttributeSanitizer(root: Document): () => void {
  const isInjectedAttribute = (name: string) =>
    name === "bis_skin_checked" ||
    name === "bis_register" ||
    /^__processed_.*__$/.test(name);

  const cleanElement = (element: Element) => {
    for (const name of element.getAttributeNames()) {
      if (isInjectedAttribute(name)) {
        element.removeAttribute(name);
      }
    }
  };

  const cleanTree = (element: Element) => {
    cleanElement(element);
    element.querySelectorAll("*").forEach(cleanElement);
  };

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === "attributes" && mutation.target instanceof Element) {
        cleanElement(mutation.target);
      }

      for (const node of mutation.addedNodes) {
        if (node instanceof Element) {
          cleanTree(node);
        }
      }
    }
  });

  observer.observe(root, { attributes: true, childList: true, subtree: true });
  root.querySelectorAll("*").forEach(cleanElement);

  return () => observer.disconnect();
}

export const HYDRATION_ATTRIBUTE_SANITIZER_SCRIPT = `(${installHydrationAttributeSanitizer.toString()})(document);`;
