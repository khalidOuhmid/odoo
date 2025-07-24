#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour générer des données de test complètes pour le module construction_base
Compatible avec Odoo 18
"""

import logging
import random
from datetime import datetime, timedelta
from odoo import api, fields, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def create_test_data(env):
    """Fonction principale pour créer toutes les données de test"""
    _logger.info("🔨 Création des données de test pour construction_base...")
    
    # 1. Créer des contacts (clients et sous-traitants)
    clients = create_test_clients(env)
    subcontractors = create_test_subcontractors(env)
    
    # 2. Créer des chantiers à différentes étapes
    chantiers = create_test_chantiers(env, clients, subcontractors)
    
    # 3. Attribuer des plannings
    create_test_plannings(env, chantiers, subcontractors)
    
    # 4. Créer des documents
    create_test_documents(env, chantiers)
    
    # 5. Configurer des cycles de facturation
    create_test_invoice_schedules(env, chantiers)
    
    # 6. Simuler des visiteurs
    create_test_visits(env, chantiers)
    
    _logger.info("✅ Création des données de test terminée avec succès")
    return {
        'clients': clients,
        'subcontractors': subcontractors,
        'chantiers': chantiers
    }


def create_test_clients(env):
    """Créer plusieurs clients de test"""
    _logger.info("👤 Création des clients de test...")
    Partner = env['res.partner']
    
    clients_data = [
        {
            'name': 'Martin Dupont',
            'street': '25 Avenue de la République',
            'city': 'Paris',
            'zip': '75011',
            'phone': '0612345678',
            'email': 'martin.dupont@example.com',
            'customer_rank': 1,
        },
        {
            'name': 'Sophie Moreau',
            'street': '8 Rue de la Paix',
            'city': 'Lyon',
            'zip': '69002',
            'phone': '0623456789',
            'email': 'sophie.moreau@example.com',
            'customer_rank': 1,
        },
        {
            'name': 'Pierre Durand',
            'street': '15 Boulevard des Fleurs',
            'city': 'Marseille',
            'zip': '13008',
            'phone': '0634567890',
            'email': 'pierre.durand@example.com',
            'customer_rank': 1,
        },
        {
            'name': 'Julie Lefebvre',
            'street': '42 Rue du Commerce',
            'city': 'Bordeaux',
            'zip': '33000',
            'phone': '0645678901',
            'email': 'julie.lefebvre@example.com',
            'customer_rank': 1,
        },
        {
            'name': 'Thomas Bernard',
            'street': '3 Place de la Mairie',
            'city': 'Lille',
            'zip': '59000',
            'phone': '0656789012',
            'email': 'thomas.bernard@example.com',
            'customer_rank': 1,
        }
    ]
    
    clients = []
    for data in clients_data:
        # Vérifier si le client existe déjà
        existing = Partner.search([('email', '=', data['email'])], limit=1)
        if existing:
            _logger.info(f"Le client {data['name']} existe déjà, mise à jour...")
            existing.write(data)
            clients.append(existing)
        else:
            _logger.info(f"Création du client {data['name']}...")
            client = Partner.create(data)
            clients.append(client)
    
    return clients


def create_test_subcontractors(env):
    """Créer plusieurs sous-traitants de test"""
    _logger.info("🛠️ Création des sous-traitants de test...")
    Partner = env['res.partner']
    
    subcontractors_data = [
        {
            'name': 'Electricité Pro',
            'street': '10 Rue des Artisans',
            'city': 'Paris',
            'zip': '75020',
            'phone': '0123456789',
            'email': 'contact@electricite-pro.example.com',
            'supplier_rank': 1,
        },
        {
            'name': 'Plomberie Martin',
            'street': '5 Avenue des Métiers',
            'city': 'Lyon',
            'zip': '69003',
            'phone': '0234567890',
            'email': 'contact@plomberie-martin.example.com',
            'supplier_rank': 1,
        },
        {
            'name': 'Maçonnerie Générale',
            'street': '15 Rue du Bâtiment',
            'city': 'Marseille',
            'zip': '13010',
            'phone': '0345678901',
            'email': 'contact@maconnerie-generale.example.com',
            'supplier_rank': 1,
        },
        {
            'name': 'Menuiserie Durand',
            'street': '8 Boulevard de l\'Industrie',
            'city': 'Nantes',
            'zip': '44000',
            'phone': '0456789012',
            'email': 'contact@menuiserie-durand.example.com',
            'supplier_rank': 1,
        },
        {
            'name': 'Peinture Déco',
            'street': '12 Rue des Peintres',
            'city': 'Toulouse',
            'zip': '31000',
            'phone': '0567890123',
            'email': 'contact@peinture-deco.example.com',
            'supplier_rank': 1,
        }
    ]
    
    subcontractors = []
    for data in subcontractors_data:
        # Vérifier si le sous-traitant existe déjà
        existing = Partner.search([('email', '=', data['email'])], limit=1)
        if existing:
            _logger.info(f"Le sous-traitant {data['name']} existe déjà, mise à jour...")
            existing.write(data)
            subcontractors.append(existing)
        else:
            _logger.info(f"Création du sous-traitant {data['name']}...")
            subcontractor = Partner.create(data)
            # Générer un token pour l'upload de documents
            subcontractor._generate_upload_token()
            subcontractors.append(subcontractor)
    
    return subcontractors


def create_test_chantiers(env, clients, subcontractors):
    """Créer plusieurs chantiers à différentes étapes"""
    _logger.info("🏗️ Création des chantiers de test...")
    Chantier = env['construction.chantier']
    Lot = env['construction.lot']
    
    # Créer des objets lot s'ils n'existent pas
    lot_names = ['Gros œuvre', 'Électricité', 'Plomberie', 'Menuiserie', 'Peinture']
    lots = []
    
    for name in lot_names:
        lot = Lot.search([('name', '=', name)], limit=1)
        if not lot:
            lot = Lot.create({
                'name': name,
                'description': f'Lot {name}',
                'price': random.randint(5000, 25000),
            })
        lots.append(lot)
    
    # Obtenir les chapitres et les étapes
    chapters = env['construction.chapter'].search([])
    chapter_stages = {}
    for chapter in chapters:
        chapter_stages[chapter.id] = env['construction.stage'].search([('chapter_id', '=', chapter.id)])
    
    # Obtenir les cycles de facturation
    invoice_types = env['construction.invoice_type'].search([])
    
    # Créer des chantiers à différentes étapes
    chantiers_data = [
        # Chantier 1: Appel d'offre - Réception
        {
            'name': 'Rénovation Appartement Paris',
            'client': clients[0].id,
            'chapter_id': chapters[0].id,  # Appel d'offre
            'stage_id': chapter_stages[chapters[0].id][0].id,  # Réception
            'description': 'Rénovation complète d\'un appartement de 80m²',
            'total_cost': 85000,
            'progress': 0,
            'lots_ids': [(6, 0, [lots[1].id, lots[2].id, lots[4].id])],  # Électricité, Plomberie, Peinture
            'invoice_type_id': invoice_types[0].id,  # Général
        },
        # Chantier 2: Appel d'offre - Devis envoyé
        {
            'name': 'Extension Maison Lyon',
            'client': clients[1].id,
            'chapter_id': chapters[0].id,  # Appel d'offre
            'stage_id': chapter_stages[chapters[0].id][2].id,  # Devis envoyé
            'description': 'Extension de 30m² pour créer une pièce supplémentaire',
            'total_cost': 45000,
            'progress': 0,
            'lots_ids': [(6, 0, [lots[0].id, lots[3].id])],  # Gros œuvre, Menuiserie
            'invoice_type_id': invoice_types[1].id,  # Little Worker
        },
        # Chantier 3: Préparation - Devis accepté
        {
            'name': 'Rénovation Cuisine Marseille',
            'client': clients[2].id,
            'chapter_id': chapters[1].id,  # Préparation
            'stage_id': chapter_stages[chapters[1].id][0].id,  # Devis accepté
            'description': 'Rénovation complète d\'une cuisine avec îlot central',
            'total_cost': 25000,
            'progress': 0,
            'lots_ids': [(6, 0, [lots[1].id, lots[2].id, lots[3].id])],  # Électricité, Plomberie, Menuiserie
            'invoice_type_id': invoice_types[0].id,  # Général
            'subcontractor_ids': [(6, 0, [subcontractors[0].id, subcontractors[1].id, subcontractors[3].id])],
        },
        # Chantier 4: Travaux - 0-25%
        {
            'name': 'Construction Maison Bordeaux',
            'client': clients[3].id,
            'chapter_id': chapters[2].id,  # Travaux
            'stage_id': chapter_stages[chapters[2].id][0].id,  # Travaux 0-25%
            'description': 'Construction d\'une maison individuelle de 120m²',
            'total_cost': 200000,
            'progress': 15,
            'date_start_contract': fields.Date.today() - timedelta(days=30),
            'date_end_contract': fields.Date.today() + timedelta(days=240),
            'lots_ids': [(6, 0, [lot.id for lot in lots])],  # Tous les lots
            'invoice_type_id': invoice_types[2].id,  # Colocataire
            'subcontractor_ids': [(6, 0, [subcontractors[0].id, subcontractors[1].id, subcontractors[2].id])],
        },
        # Chantier 5: Travaux - 50-75%
        {
            'name': 'Rénovation Appartement Lille',
            'client': clients[4].id,
            'chapter_id': chapters[2].id,  # Travaux
            'stage_id': chapter_stages[chapters[2].id][2].id,  # Travaux 50-75%
            'description': 'Rénovation d\'un appartement haussmannien de 110m²',
            'total_cost': 120000,
            'progress': 65,
            'date_start_contract': fields.Date.today() - timedelta(days=90),
            'date_end_contract': fields.Date.today() + timedelta(days=60),
            'lots_ids': [(6, 0, [lot.id for lot in lots])],  # Tous les lots
            'invoice_type_id': invoice_types[0].id,  # Général
            'subcontractor_ids': [(6, 0, [subcontractor.id for subcontractor in subcontractors])],
        }
    ]
    
    chantiers = []
    for data in chantiers_data:
        existing = Chantier.search([('name', '=', data['name'])], limit=1)
        if existing:
            _logger.info(f"Le chantier {data['name']} existe déjà, mise à jour...")
            existing.write(data)
            chantiers.append(existing)
        else:
            _logger.info(f"Création du chantier {data['name']}...")
            chantier = Chantier.create(data)
            chantiers.append(chantier)
    
    return chantiers


def create_test_plannings(env, chantiers, subcontractors):
    """Créer des tâches de planning pour les chantiers"""
    _logger.info("📅 Création des plannings de test...")
    Task = env['construction.planning.task']
    
    # Ne créer des plannings que pour les chantiers en phase de travaux
    for chantier in chantiers:
        if chantier.chapter_id.code not in ['TRAV', 'PREP']:
            continue
        
        # Obtenir les lots associés à ce chantier
        lots = chantier.lots_ids
        if not lots:
            continue
        
        # Déterminer la période du chantier
        start_date = chantier.date_start_contract or fields.Date.today()
        end_date = chantier.date_end_contract or fields.Date.today() + timedelta(days=180)
        duration = (end_date - start_date).days
        
        # Créer plusieurs tâches de planning pour ce chantier
        tasks_data = []
        current_date = start_date
        
        for i, lot in enumerate(lots):
            # Déterminer le sous-traitant pour ce lot (s'il y en a)
            subcontractor_id = False
            if chantier.subcontractor_ids and i < len(chantier.subcontractor_ids):
                subcontractor_id = chantier.subcontractor_ids[i].id
            
            # Calculer la durée de cette tâche (entre 10% et 30% de la durée totale)
            task_duration = int(duration * random.uniform(0.1, 0.3))
            task_end_date = current_date + timedelta(days=task_duration)
            
            # Créer la tâche
            task_data = {
                'name': f"Travaux {lot.name}",
                'chantier_id': chantier.id,
                'lot_id': lot.id,
                'subcontractor_id': subcontractor_id,
                'date_start': datetime.combine(current_date, datetime.min.time()),
                'date_stop': datetime.combine(task_end_date, datetime.min.time()),
                'state': 'planned',
                'description': f"Réalisation des travaux de {lot.name}",
            }
            tasks_data.append(task_data)
            
            # Mettre à jour la date pour la prochaine tâche (avec un peu de chevauchement)
            current_date = current_date + timedelta(days=int(task_duration * 0.7))
        
        # Créer les tâches
        for task_data in tasks_data:
            existing = Task.search([
                ('name', '=', task_data['name']),
                ('chantier_id', '=', task_data['chantier_id']),
                ('lot_id', '=', task_data['lot_id'])
            ], limit=1)
            
            if existing:
                _logger.info(f"La tâche {task_data['name']} existe déjà, mise à jour...")
                existing.write(task_data)
            else:
                _logger.info(f"Création de la tâche {task_data['name']}...")
                Task.create(task_data)


def create_test_documents(env, chantiers):
    """Créer des documents pour les chantiers"""
    _logger.info("📄 Création des documents de test...")
    Document = env['construction.document']
    
    for chantier in chantiers:
        # Déterminer le nombre de documents à créer selon l'étape du chantier
        if chantier.chapter_id.code == 'AO':
            doc_count = 1  # Seulement un devis en phase d'appel d'offre
        elif chantier.chapter_id.code == 'PREP':
            doc_count = 3  # Devis + contrat + spécifications
        else:
            doc_count = 5  # Tous les types
        
        # Types de documents possibles
        doc_types = ['quote', 'contract', 'subcontract', 'specs', 'plan', 'schedule', 'permit', 'other']
        
        for i in range(doc_count):
            doc_type = doc_types[i % len(doc_types)]
            
            document_data = {
                'name': f"{doc_type.capitalize()} - {chantier.name}",
                'chantier_id': chantier.id,
                'document_type': doc_type,
                'description': f"Document {doc_type} pour le chantier {chantier.name}",
                'filename': f"{doc_type}_{chantier.id}.pdf",
                # Simuler un fichier binaire - en pratique, il faudrait un vrai fichier
                'file_data': 'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
                'file_size': random.randint(100, 5000),
            }
            
            existing = Document.search([
                ('name', '=', document_data['name']),
                ('chantier_id', '=', document_data['chantier_id'])
            ], limit=1)
            
            if existing:
                _logger.info(f"Le document {document_data['name']} existe déjà, mise à jour...")
                existing.write(document_data)
            else:
                _logger.info(f"Création du document {document_data['name']}...")
                Document.create(document_data)


def create_test_invoice_schedules(env, chantiers):
    """Créer des planifications de facturation pour les chantiers"""
    _logger.info("💰 Création des planifications de facturation...")
    
    for chantier in chantiers:
        # Obtenir le cycle de facturation du chantier
        invoice_type = chantier.invoice_type_id
        if not invoice_type:
            continue
        
        # Vérifier si les planifications existent déjà
        existing_schedules = env['construction.invoice.schedule'].search([
            ('chantier_id', '=', chantier.id)
        ])
        
        if existing_schedules:
            _logger.info(f"Le chantier {chantier.name} a déjà des planifications de facturation")
            continue
        
        # Créer les planifications selon le cycle
        _logger.info(f"Création des planifications pour le chantier {chantier.name}...")
        
        # Simuler la méthode qui est normalement appelée au changement de cycle
        for line in invoice_type.line_ids:
            schedule_data = {
                'chantier_id': chantier.id,
                'invoice_type_line_id': line.id,
                'name': line.name,
                'sequence': line.sequence,
                'trigger_percentage': line.trigger_percentage,
                'amount_percentage': line.percentage,
                'is_advance_payment': line.is_advance_payment,
                'state': 'planned',
            }
            
            # Si c'est un acompte de signature et que le chantier est déjà en préparation ou plus,
            # marquer comme déclenché et facturé
            if line.is_advance_payment and chantier.chapter_id.code in ['PREP', 'TRAV', 'LEVEE', 'RET']:
                schedule_data.update({
                    'state': 'invoiced',
                    'is_triggered': True,
                    'invoice_date': fields.Date.today() - timedelta(days=random.randint(30, 90))
                })
            
            # Si le chantier a progressé au-delà du seuil de déclenchement,
            # marquer comme déclenché
            elif chantier.progress >= line.trigger_percentage:
                if chantier.progress >= line.trigger_percentage + 20:
                    # Si bien au-delà, marquer comme facturé
                    schedule_data.update({
                        'state': 'invoiced',
                        'is_triggered': True,
                        'invoice_date': fields.Date.today() - timedelta(days=random.randint(7, 30))
                    })
                else:
                    # Sinon, juste déclenché
                    schedule_data.update({
                        'state': 'ready',
                        'is_triggered': True
                    })
            
            env['construction.invoice.schedule'].create(schedule_data)


def create_test_visits(env, chantiers):
    """Créer des visites pour les chantiers"""
    _logger.info("👁️ Création des visites de test...")
    Visit = env['construction.visit']
    
    for chantier in chantiers:
        # Déterminer le nombre de visites selon l'étape du chantier
        if chantier.chapter_id.code == 'AO':
            visit_count = 1  # Une visite initiale
        elif chantier.chapter_id.code == 'PREP':
            visit_count = 2  # Visites de préparation
        elif chantier.chapter_id.code == 'TRAV':
            visit_count = 4  # Visites régulières pendant les travaux
        else:
            visit_count = 6  # Toutes les visites y compris finales
        
        # Types de visites
        visit_types = ['initial', 'progress', 'quality', 'final']
        
        # États possibles selon l'avancement
        if chantier.chapter_id.code == 'TRAV' and chantier.progress > 50:
            states = ['completed', 'completed', 'in_progress', 'planned']
        elif chantier.chapter_id.code in ['PREP', 'TRAV']:
            states = ['completed', 'in_progress', 'planned', 'planned']
        else:
            states = ['draft', 'planned', 'planned', 'planned']
        
        for i in range(visit_count):
            # Déterminer le type de visite
            visit_type = visit_types[i % len(visit_types)]
            
            # Déterminer l'état de la visite
            state = states[i % len(states)]
            
            # Déterminer la date de la visite
            if state == 'completed':
                visit_date = datetime.now() - timedelta(days=random.randint(1, 30))
            elif state == 'in_progress':
                visit_date = datetime.now()
            else:
                visit_date = datetime.now() + timedelta(days=random.randint(1, 30))
            
            visit_data = {
                'name': f"Visite {visit_type} - {chantier.name}",
                'chantier_id': chantier.id,
                'visit_type': visit_type,
                'state': state,
                'date': visit_date,
                'duration': random.uniform(1.0, 3.0),
                'description': f"<p>Visite {visit_type} pour le chantier {chantier.name}</p>",
            }
            
            # Ajouter des notes et un rapport pour les visites terminées
            if state == 'completed':
                visit_data.update({
                    'notes': f"<p>Notes de la visite du {visit_date.strftime('%d/%m/%Y')}</p><ul><li>Point 1</li><li>Point 2</li></ul>",
                    'report': f"<p>Rapport de visite:</p><p>Le chantier avance conformément au planning.</p>"
                })
            
            # Ajouter des participants (utilisateurs et partenaires)
            if chantier.user_ids:
                visit_data['user_ids'] = [(6, 0, chantier.user_ids.ids[:2])]
            
            if chantier.subcontractor_ids and visit_type in ['progress', 'quality']:
                visit_data['partner_ids'] = [(6, 0, chantier.subcontractor_ids.ids[:2])]
            
            existing = Visit.search([
                ('name', '=', visit_data['name']),
                ('chantier_id', '=', visit_data['chantier_id']),
                ('date', '=', visit_data['date'])
            ], limit=1)
            
            if existing:
                _logger.info(f"La visite {visit_data['name']} existe déjà, mise à jour...")
                existing.write(visit_data)
            else:
                _logger.info(f"Création de la visite {visit_data['name']}...")
                Visit.create(visit_data)


def main(env):
    """Point d'entrée principal"""
    return create_test_data(env)


if __name__ == "__main__":
    # Ce script est destiné à être exécuté dans un contexte Odoo
    # Il peut être appelé depuis le shell Odoo:
    # env['ir.module.module'].search([('name', '=', 'construction_base')]).latest_version
    # exec(open('/path/to/create_test_data.py').read())
    _logger.warning("Ce script doit être exécuté depuis le shell Odoo")
