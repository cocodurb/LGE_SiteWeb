#!/bin/bash
# Script de déploiement : fusionne dev dans main et déclenche le déploiement automatique

echo "🔄 Déploiement en cours..."

# S'assurer qu'on est sur dev et que tout est commité
git checkout dev
git add -A
git commit -m "Deploy: $(date '+%Y-%m-%d %H:%M')" 2>/dev/null || echo "Rien à committer."

# Fusionner dev dans main
git checkout main
git merge dev --no-edit

# Pousser main → déclenche GitHub Actions → déploie sur Infomaniak
git push origin main

# Revenir sur dev pour continuer à travailler
git checkout dev

echo "✅ Déploiement envoyé ! GitHub Actions va mettre à jour le serveur automatiquement."
echo "📊 Suivez l'avancement ici : https://github.com/cocodurb/LGE_SiteWeb/actions"
