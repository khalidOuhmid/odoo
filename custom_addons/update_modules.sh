#!/bin/bash

echo "🔄 Démarrage du processus de mise à jour des modules Odoo..."

# Démarrer les conteneurs
echo "📦 Démarrage des conteneurs..."
docker compose up -d db

# Attendre que la base de données soit prête
echo "⏳ Attente que la base de données soit prête..."
sleep 10

# Lancer Odoo en mode mise à jour pour nettoyer les références
echo "🧹 Nettoyage des modules et mise à jour..."
docker compose run --rm web odoo -d blgtest --update=all --stop-after-init

# Démarrer Odoo normalement
echo "🚀 Redémarrage d'Odoo en mode normal..."
docker compose up -d

echo "✅ Processus terminé ! Odoo devrait maintenant fonctionner correctement."
echo "🌐 Accédez à http://localhost:8069 pour vérifier." 