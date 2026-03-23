# -*- coding: utf-8 -*-
"""
Migration 18.0.2.2.0 — Migrate generic attachment_ids to typed media fields.

Transfers records from construction_visit_generic_attach_rel into the typed
relation tables (photo/video/document) based on ir.attachment mimetype.
This preserves all attachments before the "Pièces Jointes" tab is removed.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Fetch all generic attachments linked to visits
    cr.execute("""
        SELECT rel.visit_id, rel.attachment_id, att.mimetype
        FROM construction_visit_generic_attach_rel rel
        JOIN ir_attachment att ON att.id = rel.attachment_id
        ORDER BY rel.visit_id, rel.attachment_id
    """)
    rows = cr.fetchall()

    if not rows:
        _logger.info("[BLG][VISIT][MIGRATE] No generic attachments to migrate.")
        return

    photos, videos, documents = [], [], []
    for visit_id, att_id, mimetype in rows:
        mimetype = (mimetype or '').lower()
        if mimetype.startswith('image/'):
            photos.append((visit_id, att_id))
        elif mimetype.startswith('video/'):
            videos.append((visit_id, att_id))
        else:
            documents.append((visit_id, att_id))

    def _insert_unique(table, pairs):
        if not pairs:
            return 0
        # Use ON CONFLICT DO NOTHING to avoid duplicates on re-run
        cr.executemany(
            f"INSERT INTO {table} (visit_id, ir_attachment_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            pairs,
        )
        return len(pairs)

    n_photos = _insert_unique('construction_visit_photo_v2_rel', photos)
    n_videos = _insert_unique('construction_visit_video_v2_rel', videos)
    n_docs = _insert_unique('construction_visit_doc_v2_rel', documents)

    _logger.info(
        "[BLG][VISIT][MIGRATE] Migrated %d photos, %d videos, %d documents "
        "from generic attachment_ids.",
        n_photos, n_videos, n_docs,
    )
