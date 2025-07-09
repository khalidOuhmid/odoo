# Script PowerShell pour mettre à jour les modules Odoo

Write-Host "🔄 Démarrage du processus de mise à jour des modules Odoo..." -ForegroundColor Blue

# Démarrer les conteneurs
Write-Host "📦 Démarrage des conteneurs..." -ForegroundColor Yellow
docker compose up -d db

# Attendre que la base de données soit prête
Write-Host "⏳ Attente que la base de données soit prête..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Lancer Odoo en mode mise à jour pour nettoyer les références
Write-Host "🧹 Nettoyage des modules et mise à jour..." -ForegroundColor Green
docker compose run --rm web odoo -d blgtest --update=all --stop-after-init

# Démarrer Odoo normalement
Write-Host "🚀 Redémarrage d'Odoo en mode normal..." -ForegroundColor Green
docker compose up -d

Write-Host "✅ Processus terminé ! Odoo devrait maintenant fonctionner correctement." -ForegroundColor Green
Write-Host "🌐 Accédez à http://localhost:8069 pour vérifier." -ForegroundColor Blue 