# -*- coding: utf-8 -*-
"""
Migration 18.0.1.1 — Post-migrate : import des ir.attachment existants dans la GED.

Objectif : migrer tous les ir.attachment liés à construction.chantier
           vers construction.document avec le tag "Import initial".

Règles :
- Idempotente : relancer deux fois ne crée pas de doublons
- Ne supprime aucun attachment existant
- Ne duplique pas les binaires (construction.document pointe vers ir.attachment)
"""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Post-migration : crée un construction.document pour chaque ir.attachment
    lié à un construction.chantier qui n'a pas encore été indexé.
    """
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. S'assurer que le modèle est disponible
    if 'construction.document' not in env:
        _logger.warning('[GED Migration] Modèle construction.document introuvable — migration ignorée')
        return

    # 2. Récupérer ou créer le tag "Import initial"
    tag_model = env['construction.document.tag']
    tag = tag_model.search([('name', '=', 'Import initial')], limit=1)
    if not tag:
        tag = tag_model.create({'name': 'Import initial', 'color': 5})
    tag_cmd = [(4, tag.id)]

    # 3. Trouver tous les attachments liés à des chantiers NON encore indexés
    #    La sous-requête garantit l'idempotence.
    cr.execute("""
        SELECT a.id        AS attachment_id,
               a.res_id   AS chantier_id
        FROM ir_attachment a
        WHERE a.res_model = 'construction.chantier'
          AND a.res_id    IS NOT NULL
          AND a.res_id     > 0
          AND NOT EXISTS (
              SELECT 1
              FROM construction_document d
              WHERE d.attachment_id = a.id
          )
        ORDER BY a.id
    """)
    rows = cr.fetchall()

    if not rows:
        _logger.info('[GED Migration] Aucun attachment à migrer.')
        return

    _logger.info('[GED Migration] %d attachment(s) à migrer vers construction.document', len(rows))

    # 4. Vérifier quels chantiers existent réellement (intégrité référentielle)
    chantier_ids = list({r[1] for r in rows})
    cr.execute(
        'SELECT id FROM construction_chantier WHERE id = ANY(%s)',
        (chantier_ids,)
    )
    valid_chantier_ids = {r[0] for r in cr.fetchall()}

    # 5. Créer les enregistrements GED en batch
    doc_model = env['construction.document']
    created = 0
    skipped = 0

    for att_id, chantier_id in rows:
        if chantier_id not in valid_chantier_ids:
            _logger.warning(
                '[GED Migration] Chantier %d introuvable pour attachment %d — ignoré',
                chantier_id, att_id,
            )
            skipped += 1
            continue

        doc_model.create({
            'chantier_id': chantier_id,
            'attachment_id': att_id,
            'tag_ids': tag_cmd,
            'source_model': 'ir.attachment',
            'source_id': att_id,
        })
        created += 1

    _logger.info(
        '[GED Migration] Terminé : %d document(s) créés, %d ignorés.',
        created, skipped,
    )
