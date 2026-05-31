const encoder = new TextEncoder();
const decoder = new TextDecoder();

const jsonHeaders = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store"
};

const DEFAULT_DOOR_CODE = "01000016000200000020";
const DOORS_API_URL = "http://172.18.1.70:18080/api/mobile/doors";
const DOORS_QUERY_PAYLOAD = {
  campusId: "",
  buildingId: "",
  floorId: "",
  pageNum: 1,
  pageSize: 20
};

type TokenUrlRequest = {
  tokenUrl: string;
};

type CiphertextRequest = {
  ciphertext: string;
};

type DoorCodeRequest = {
  doorCode?: string;
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: jsonHeaders
  });
}

function requireWorkerKey(request: Request, env: Env): Response | null {
  const provided = request.headers.get("X-Worker-Key");
  if (!env.WORKER_KEY) {
    return jsonResponse({ error: "WORKER_KEY is not configured" }, 500);
  }
  if (provided !== env.WORKER_KEY) {
    return jsonResponse({ error: "unauthorized" }, 401);
  }
  return null;
}

function base64Encode(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function base64Decode(value: string): Uint8Array {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function extractTokenFromUrl(tokenUrl: string): string | null {
  try {
    const url = new URL(tokenUrl);
    return url.searchParams.get("token");
  } catch {
    return null;
  }
}

async function importAesKey(keyText: string, usage: KeyUsage): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(keyText),
    { name: "AES-CBC" },
    false,
    [usage]
  );
}

async function encryptPayload(payload: unknown, env: Env): Promise<string> {
  const plainText = JSON.stringify(payload);
  const key = await importAesKey(env.AES_KEY, "encrypt");
  const iv = encoder.encode(env.AES_IV);
  const encrypted = await crypto.subtle.encrypt({ name: "AES-CBC", iv }, key, encoder.encode(plainText));
  return base64Encode(new Uint8Array(encrypted));
}

async function decryptCiphertext(ciphertext: string, env: Env): Promise<unknown> {
  const key = await importAesKey(env.AES_KEY, "decrypt");
  const iv = encoder.encode(env.AES_IV);
  const encryptedBytes = base64Decode(ciphertext);
  const plainBuffer = await crypto.subtle.decrypt({ name: "AES-CBC", iv }, key, encryptedBytes);
  const plainBytes = new Uint8Array(plainBuffer);
  return JSON.parse(decoder.decode(plainBytes));
}

async function parseJson<T>(request: Request): Promise<Partial<T> | Response> {
  try {
    return (await request.json()) as Partial<T>;
  } catch {
    return jsonResponse({ error: "invalid json body" }, 400);
  }
}

async function handleExtractToken(request: Request): Promise<Response> {
  const parsed = await parseJson<TokenUrlRequest>(request);
  if (parsed instanceof Response) {
    return parsed;
  }
  if (typeof parsed.tokenUrl !== "string" || !parsed.tokenUrl) {
    return jsonResponse({ error: "tokenUrl is required" }, 400);
  }
  const token = extractTokenFromUrl(parsed.tokenUrl);
  if (!token) {
    return jsonResponse({ error: "token not found in tokenUrl" }, 400);
  }
  return jsonResponse({ token });
}

async function handlePrepareDoorsQuery(env: Env): Promise<Response> {
  const rawCiphertext = await encryptPayload(DOORS_QUERY_PAYLOAD, env);
  const ciphertext = encodeURIComponent(rawCiphertext);
  const doorsUrl = `${DOORS_API_URL}?str=${ciphertext}`;
  return jsonResponse({ ciphertext, rawCiphertext, doorsUrl });
}

async function handleDecryptDoorsResponse(request: Request, env: Env): Promise<Response> {
  const parsed = await parseJson<CiphertextRequest>(request);
  if (parsed instanceof Response) {
    return parsed;
  }
  if (typeof parsed.ciphertext !== "string" || !parsed.ciphertext) {
    return jsonResponse({ error: "ciphertext is required" }, 400);
  }
  try {
    const payload = await decryptCiphertext(parsed.ciphertext, env);
    return jsonResponse({ payload });
  } catch {
    return jsonResponse({ error: "failed to decrypt ciphertext" }, 400);
  }
}

async function handlePrepareOpenBody(request: Request, env: Env): Promise<Response> {
  const parsed = await parseJson<DoorCodeRequest>(request);
  if (parsed instanceof Response) {
    return parsed;
  }
  const doorCode = typeof parsed.doorCode === "string" && parsed.doorCode ? parsed.doorCode : DEFAULT_DOOR_CODE;
  const rawCiphertext = await encryptPayload({ doorCode }, env);
  const ciphertext = encodeURIComponent(rawCiphertext);
  return jsonResponse({ ciphertext, rawCiphertext });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (env.AES_KEY.length !== 16 || env.AES_IV.length !== 16) {
      return jsonResponse({ error: "AES_KEY and AES_IV must be 16-byte strings" }, 500);
    }
    const authError = requireWorkerKey(request, env);
    if (authError) {
      return authError;
    }

    const url = new URL(request.url);

    if (url.pathname === "/extract-token") {
      if (request.method !== "POST") {
        return jsonResponse({ error: "method not allowed" }, 405);
      }
      return handleExtractToken(request);
    }

    if (url.pathname === "/prepare-doors-query") {
      if (request.method !== "POST") {
        return jsonResponse({ error: "method not allowed" }, 405);
      }
      return handlePrepareDoorsQuery(env);
    }

    if (url.pathname === "/decrypt-doors-response") {
      if (request.method !== "POST") {
        return jsonResponse({ error: "method not allowed" }, 405);
      }
      return handleDecryptDoorsResponse(request, env);
    }

    if (url.pathname === "/prepare-open-body") {
      if (request.method !== "POST") {
        return jsonResponse({ error: "method not allowed" }, 405);
      }
      return handlePrepareOpenBody(request, env);
    }

    return jsonResponse({ error: "not found" }, 404);
  }
};
