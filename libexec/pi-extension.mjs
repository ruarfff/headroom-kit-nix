// Loaded only by pi-headroom; Pi keeps ownership of credentials and model catalogs.
export default function (pi) {
  for (const provider of ["openai", "anthropic"]) {
    const endpoint = process.env.HEADROOM_KIT_ENDPOINT;
    pi.registerProvider(provider, {
      baseUrl: provider === "anthropic" ? endpoint.replace(/\/v1$/, "") : endpoint,
    });
  }
}
