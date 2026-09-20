// The final request hook also covers per-model endpoints and auxiliary requests.
export default {
  id: "headroom-kit",
  async setup(ctx) {
    const providers = new Set(["openai", "anthropic", "opencode"]);
    if (ctx.options.copilot) providers.add("github-copilot");
    await ctx.catalog.transform((catalog) => {
      for (const { provider, models } of catalog.provider.list()) {
        if (!providers.has(provider.id)) continue;
        for (const model of models.values()) {
          catalog.model.update(provider.id, model.id, (draft) => {
            draft.websocket = false;
          });
        }
      }
    });
    await ctx.session.hook("model.request", (event) => {
      if (event.model.providerID === "github-copilot" && ctx.options.copilot) {
        event.baseURL = ctx.options.copilot;
        if (event.headers) event.headers.authorization = "Bearer headroom-kit";
        return;
      }
      if (providers.has(event.model.providerID)) event.baseURL = ctx.options.endpoint;
    });
  },
};
