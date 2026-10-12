FROM 3b/base
# VERIFY: workdir, copy layout, and the command that starts a TypeScript (Bun) step.
# The first line is the only confirmed image line. Nothing here names a registry.
WORKDIR /app
COPY index.ts /app/index.ts
CMD ["bun", "/app/index.ts"]
