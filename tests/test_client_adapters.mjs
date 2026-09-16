import assert from "node:assert/strict";
import test from "node:test";
import pi from "../libexec/pi-extension.mjs";
import opencode from "../libexec/opencode-plugin/index.js";

test("Pi uses each API's base path without replacing credentials or models", () => {
  const previous = process.env.HEADROOM_KIT_ENDPOINT;
  process.env.HEADROOM_KIT_ENDPOINT = "http://127.0.0.1:8790/v1";
  try {
    const overrides = {};
    pi({ registerProvider: (id, config) => (overrides[id] = config) });
    assert.deepEqual(overrides, {
      openai: { baseUrl: "http://127.0.0.1:8790/v1" },
      anthropic: { baseUrl: "http://127.0.0.1:8790" },
    });
  } finally {
    if (previous === undefined) delete process.env.HEADROOM_KIT_ENDPOINT;
    else process.env.HEADROOM_KIT_ENDPOINT = previous;
  }
});

test("OpenCode overrides final endpoints and disables model WebSockets", async () => {
  const endpoint = "http://127.0.0.1:8791/v1";
  const records = ["openai", "anthropic", "other"].map((id) => ({
    provider: { id },
    models: new Map([["model", { id: "model", websocket: true }]]),
  }));
  let request;
  await opencode.setup({
    options: { endpoint },
    catalog: {
      transform: (change) =>
        change({
          provider: { list: () => records },
          model: {
            update: (provider, model, edit) =>
              edit(records.find((item) => item.provider.id === provider).models.get(model)),
          },
        }),
    },
    session: {
      hook: (name, handler) => {
        assert.equal(name, "model.request");
        request = handler;
      },
    },
  });
  for (const { provider, models } of records) {
    const supported = provider.id !== "other";
    assert.equal(models.get("model").websocket, !supported);
    for (const kind of ["primary", "title", "compaction", "generate"]) {
      const event = {
        model: { providerID: provider.id },
        kind,
        baseURL: "http://other.example.invalid",
        headers: { authorization: "Bearer fake-test-key" },
      };
      request(event);
      assert.equal(event.baseURL, supported ? endpoint : "http://other.example.invalid");
      assert.deepEqual(event.headers, { authorization: "Bearer fake-test-key" });
    }
  }
});
