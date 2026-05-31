import worker from "../src/index";

const env = {
  AES_KEY: "abcdef0123456789",
  AES_IV: "abcdef0123456789",
  WORKER_KEY: "test-worker-key"
};

const ctx = {
  waitUntil() {},
  passThroughOnException() {}
} as ExecutionContext;

describe("shortcut worker", () => {
  const authHeaders = {
    "content-type": "application/json",
    "X-Worker-Key": "test-worker-key"
  };

  it("extracts token from tokenUrl", async () => {
    const request = new Request("https://example.com/extract-token", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({
        tokenUrl: "http://172.18.1.70:9090/pages/index/index?token=test-token-123"
      })
    });

    const response = await worker.fetch(request, env, ctx);
    expect(response.status).toBe(200);
    const data = (await response.json()) as { token: string };
    expect(data.token).toBe("test-token-123");
  });

  it("returns python parity ciphertext for doors query", async () => {
    const request = new Request("https://example.com/prepare-doors-query", {
      method: "POST",
      headers: {
        "X-Worker-Key": "test-worker-key"
      }
    });

    const response = await worker.fetch(request, env, ctx);
    expect(response.status).toBe(200);
    const data = (await response.json()) as { ciphertext: string; rawCiphertext: string; doorsUrl: string };
    const expectedRaw = "18WMUJuw05sl+ffFLGOVnfzjV9d6Cd30Rf2zLm7O/dLzL+bTdLq4XPrpII2BX2u0bp61Iqapnt6AVwzrHNIJrjGLZjkr/rquWR52dWya9SY=";
    const expectedEncoded = "18WMUJuw05sl%2BffFLGOVnfzjV9d6Cd30Rf2zLm7O%2FdLzL%2BbTdLq4XPrpII2BX2u0bp61Iqapnt6AVwzrHNIJrjGLZjkr%2FrquWR52dWya9SY%3D";
    expect(data.ciphertext).toBe(expectedEncoded);
    expect(data.rawCiphertext).toBe(expectedRaw);
    expect(data.doorsUrl).toBe(`http://172.18.1.70:18080/api/mobile/doors?str=${expectedEncoded}`);
  });

  it("decrypts encrypted doors response payload", async () => {
    const request = new Request("https://example.com/decrypt-doors-response", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({
        ciphertext: "cSCk61ucMxIM+qRKPCvHl+OEH1p2yHr7lj6D5YI9DVWbpy0V/8V+XTMSYe0c/W2G/K7K+jUWrM1RQ1BRbH+CKdmNuDJirL7uUwkPY6mnq9pb7SrpgWyB0eZWuPFlSr40"
      })
    });

    const response = await worker.fetch(request, env, ctx);
    expect(response.status).toBe(200);
    const data = (await response.json()) as { payload: { result: number; data: Array<{ code: string; name: string }>; message: string } };
    expect(data.payload.result).toBe(0);
    expect(data.payload.data[0]?.code).toBe("01000016000100000003");
    expect(data.payload.data[0]?.name).toBe("103");
  });

  it("returns python parity ciphertext for default open body", async () => {
    const request = new Request("https://example.com/prepare-open-body", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({})
    });

    const response = await worker.fetch(request, env, ctx);
    expect(response.status).toBe(200);
    const data = (await response.json()) as { ciphertext: string; rawCiphertext: string };
    const expectedRaw = "TRsZHHVe/oEc1rSsuaLid/1+j51y7Uc58/lBNwwCoaU2hGCK9SObtjeHkt4471my";
    expect(data.rawCiphertext).toBe(expectedRaw);
    expect(data.ciphertext).toBe("TRsZHHVe%2FoEc1rSsuaLid%2F1%2Bj51y7Uc58%2FlBNwwCoaU2hGCK9SObtjeHkt4471my");
  });

  it("allows overriding doorCode for open body", async () => {
    const request = new Request("https://example.com/prepare-open-body", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ doorCode: "01000016000100000003" })
    });

    const response = await worker.fetch(request, env, ctx);
    expect(response.status).toBe(200);
    const data = (await response.json()) as { ciphertext: string; rawCiphertext: string };
    expect(data.rawCiphertext).not.toBe("TRsZHHVe/oEc1rSsuaLid/1+j51y7Uc58/lBNwwCoaU2hGCK9SObtjeHkt4471my");
    expect(data.ciphertext).toBe(encodeURIComponent(data.rawCiphertext));
  });

  it("rejects tokenUrl without token", async () => {
    const request = new Request("https://example.com/extract-token", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ tokenUrl: "http://172.18.1.70:9090/pages/index/index" })
    });

    const response = await worker.fetch(request, env, ctx);
    expect(response.status).toBe(400);
  });

  it("rejects invalid ciphertext", async () => {
    const request = new Request("https://example.com/decrypt-doors-response", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ ciphertext: "bad-data" })
    });

    const response = await worker.fetch(request, env, ctx);
    expect(response.status).toBe(400);
  });

  it("returns 405 for wrong method", async () => {
    const request = new Request("https://example.com/prepare-open-body", {
      method: "GET",
      headers: {
        "X-Worker-Key": "test-worker-key"
      }
    });

    const response = await worker.fetch(request, env, ctx);
    expect(response.status).toBe(405);
  });

  it("returns 401 when worker key is missing", async () => {
    const request = new Request("https://example.com/extract-token", {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        tokenUrl: "http://172.18.1.70:9090/pages/index/index?token=test-token-123"
      })
    });

    const response = await worker.fetch(request, env, ctx);
    expect(response.status).toBe(401);
  });
});
