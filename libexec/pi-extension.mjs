// Loaded only by pi-headroom; Pi keeps ownership of credentials and model catalogs.
export default function (pi) {
  const endpoint = process.env.HEADROOM_KIT_ENDPOINT;
  for (const provider of ["openai", "openai-codex", "anthropic"]) {
    pi.registerProvider(provider, {
      baseUrl: provider === "anthropic" ? endpoint.replace(/\/v1$/, "") : endpoint,
    });
  }
  const copilot = process.env.HEADROOM_KIT_COPILOT_ENDPOINT;
  if (copilot) {
    pi.registerProvider("github-copilot", {
      baseUrl: copilot,
      apiKey: "headroom-kit",
    });
  }
}
