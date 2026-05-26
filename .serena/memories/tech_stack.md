# Tech Stack

## Python (root-level scripts)
- Runtime: `uv run` (no pyproject.toml at root; uv manages env)
- No requirements.txt at root; uv lock handles deps
- `vendor/neuralhydrology/`: vendored NeuralHydrology upstream — do NOT pip install separately; referenced in-tree

## Dashboard (Next.js)
- Next.js `15.3.2`, React `19`, TypeScript `^5`, `lucide-react ^0.511.0`
- Package manager: **npm only** (`package-lock.json`). Never use yarn/pnpm.
- `@types/node ^20`, `@types/react ^19`, `@types/react-dom ^19`

## Remote GPU Server (Elice)
- OS: Ubuntu 22.04
- SSH: `ssh -i ~/.ssh/elice.pem elicer@central-02.tcp.tunnel.elice.io -p 15699`
- No Homebrew PATH on Ubuntu

## Local macOS
- Homebrew PATH required: `export PATH="/opt/homebrew/bin:$PATH"`
- Apply before `uv run` or `npm` commands
