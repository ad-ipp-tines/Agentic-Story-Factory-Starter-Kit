// Template step. Reads JSON on stdin and writes one JSON object on stdout.
// Empty stdout would stop every step listed in links. A nonzero exit is the failure.
// How the TypeScript (Bun) template exposes stdin is VERIFY until a step test pins it.

const chunks: Uint8Array[] = []
for await (const chunk of Bun.stdin.stream()) {
  chunks.push(chunk)
}

let length = 0
for (const chunk of chunks) length += chunk.length
const rawBytes = new Uint8Array(length)
let offset = 0
for (const chunk of chunks) {
  rawBytes.set(chunk, offset)
  offset += chunk.length
}

const raw = new TextDecoder().decode(rawBytes)
let echoed: unknown = null
if (raw.trim() !== "") {
  try {
    echoed = JSON.parse(raw)
  } catch {
    console.error("stdin was not JSON")
    process.exit(1)
  }
}

console.log(JSON.stringify({ status: "ok", echoed }))
