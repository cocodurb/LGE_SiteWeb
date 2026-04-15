#!/bin/bash
# ─── Script de déploiement LGE Shotgun ────────────────────────────────────────
# Usage : bash deploy.sh
# Ce script prépare et envoie le code sur GitHub.
# Il vous rappelle ensuite les 2 étapes manuelles sur Infomaniak.

echo ""
echo "🔄 Étape 1/3 — Sauvegarde des modifications sur dev..."
git checkout dev
git add -A
git commit -m "Deploy: $(date '+%Y-%m-%d %H:%M')" 2>/dev/null || echo "   Rien à committer."

echo ""
echo "🔀 Étape 2/3 — Fusion dev → main et envoi sur GitHub..."
git checkout main
git merge dev --no-edit
git push origin main
git checkout dev

echo ""
echo "✅ Code envoyé sur GitHub !"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Étape 3/3 — Mise à jour du serveur Infomaniak (2 min)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "   1. Ouvrez : https://manager.infomaniak.com"
echo "   2. Hébergement → new.la-grappe-escalade.fr → Console SSH"
echo "   3. Tapez dans la console SSH :"
echo ""
echo "      cd ~/sites/new.la-grappe-escalade.fr && git pull origin main && mkdir -p tmp && touch tmp/restart.txt"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   📧 Email de confirmation (si pas encore configuré) :"
echo "   4. Manager → Hébergement → new.la-grappe-escalade.fr"
echo "      → Node.js → Variables d'environnement"
echo "      Ajoutez : EMAIL_PASS = [mot de passe de contact@la-grappe-escalade.fr]"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "   🎉 Fini ! Le site va redémarrer tout seul à la prochaine visite !"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
