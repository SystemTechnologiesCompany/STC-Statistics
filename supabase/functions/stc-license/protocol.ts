// No npm dependencies. Shared by the Deno handler and local Node interoperability tests.
export const encoder = new TextEncoder();

export function canonical(payload: Record<string, unknown>): string {
  // Protocol fields are ASCII scalars; sorted keys match the Python client.
  return JSON.stringify(Object.fromEntries(Object.keys(payload).sort().map(k => [k, payload[k]])));
}

export function base64(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes));
}

export async function sha256(value: string | Uint8Array): Promise<string> {
  const raw = typeof value === 'string' ? encoder.encode(value) : value;
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256',raw));
  return Array.from(digest, b => b.toString(16).padStart(2,'0')).join('');
}

export function newToken(): string {
  return base64(crypto.getRandomValues(new Uint8Array(32))).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');
}

export async function loadSigner(privatePem: string) {
  const compact = privatePem.replace(/-----[^-]+-----/g,'').replace(/\s/g,'');
  const der = Uint8Array.from(atob(compact),c => c.charCodeAt(0));
  const key = await crypto.subtle.importKey('pkcs8',der,{name:'RSA-PSS',hash:'SHA-256'},true,['sign']);
  const jwk = await crypto.subtle.exportKey('jwk',key);
  const n = jwk.n!;
  const publicKey = await crypto.subtle.importKey('jwk',
    {kty:'RSA',n,e:jwk.e,alg:'PS256',ext:true}, {name:'RSA-PSS',hash:'SHA-256'},true,['verify']);
  const details = key.algorithm as RsaHashedKeyAlgorithm;
  if (details.modulusLength!==3072 || jwk.e!=='AQAB') throw new Error('Invalid signing key');
  const keyId = (await sha256(new Uint8Array(await crypto.subtle.exportKey('spki',publicKey)))).slice(0,24);
  return async (payload: Record<string, unknown>) => {
    const signature = await crypto.subtle.sign({name:'RSA-PSS',saltLength:32},key,encoder.encode(canonical(payload)));
    return {payload,signature:base64(new Uint8Array(signature)),key_id:keyId};
  };
}
