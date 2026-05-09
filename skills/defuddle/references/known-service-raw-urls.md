# Known-Service Raw URL Patterns

When defuddle fails on a known service, try the raw URL **before** escalating to browser tools.

## GitHub

| Target | Pattern | Example |
|--------|---------|---------|
| Repo README | `https://raw.githubusercontent.com/{owner}/{repo}/main/README.md` | `curl -sL https://raw.githubusercontent.com/VectifyAI/PageIndex/main/README.md` |
| Any file | `https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}` | `curl -sL https://raw.githubusercontent.com/torvalds/linux/master/MAINTAINERS` |
| Release asset | `https://github.com/{owner}/{repo}/releases/download/{tag}/{file}` | Direct download |

**Tip**: For repos not using `main`, try `master` as the branch name.

## GitLab

| Target | Pattern |
|--------|---------|
| Repo README | `https://gitlab.com/{owner}/{repo}/-/raw/main/README.md` |
| Any file | `https://gitlab.com/{owner}/{repo}/-/raw/{branch}/{path}` |

## NPM

| Target | Pattern |
|--------|---------|
| Package README | `https://unpkg.com/{package}/README.md` |
| Package metadata | `https://registry.npmjs.org/{package}` |

## PyPI

| Target | Pattern |
|--------|---------|
| Package JSON | `https://pypi.org/pypi/{package}/json` |

## Common Crawl / Archived

| Target | Command |
|--------|---------|
| Wayback Machine | `curl -sL "https://web.archive.org/web/20240101000000/{url}"` |

## Fallback Decision Tree

```
defuddle fails
    │
    ├── GitHub/GitLab URL? → construct raw URL, curl
    │   ├── success → use content
    │   └── fail → try alt branch name, then browser
    │
    ├── NPM/PyPI package? → use registry API
    │
    ├── Any docs/markdown site? → check for /llms.txt, /README.md at root
    │
    └── None of the above → browser_navigate as last resort
```
