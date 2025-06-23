#!/bin/bash
# Script to delete obsolete remote branches
# Run this script after reviewing the branches to confirm deletion

echo "🗑️  Deleting obsolete remote branches..."

# Delete the branches that are now obsolete
git push origin --delete codex/add-pydantic,-networkx-and-orm-models
git push origin --delete codex/add-ruff-and-black-hooks-to-pre-commit-config  
git push origin --delete codex/add-uuid-based-chapter-storage-and-cli-commands
git push origin --delete codex/assimilar-mudanças-sem-erros-de-merge
git push origin --delete codex/criar-workflow-diário-com-placeholder
git push origin --delete codex/propor-estrutura-de-pastas-para-capítulos
git push origin --delete codex/refatorar-código-e-documentação-com-estilo-borges
git push origin --delete codex/set-up-project-with-pyproject.toml-and-ci
git push origin --delete codex/substituir-sqlite3-por-sqlalchemy
git push origin --delete feat/initial-repo-structure
git push origin --delete initial-setup-and-seed-chapter
git push origin --delete repomix-integration

echo "✅ All obsolete branches deleted!"
echo "📊 Remaining branches:"
git branch -r