---
paths:
- frontend/coverage/**
- .gitignore
---
# [dec-0002-frontend-coverage-stays-untracked] frontend/coverage stays untracked

frontend/coverage/ is jest build output: gitignored, never committed

Never git add frontend/coverage back and never widen .gitignore past that path; regenerate it locally with npm test instead.
