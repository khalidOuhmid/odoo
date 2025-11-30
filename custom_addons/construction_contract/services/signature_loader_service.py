# -*- coding: utf-8 -*-
"""
Signature Loader Service
Centralizes signature loading logic with robust fallback mechanism
Single Responsibility: Load and validate signature images from multiple sources
"""

from odoo import models, api, _
from odoo.exceptions import UserError
import logging
import base64
import os

_logger = logging.getLogger(__name__)

# Maximum signature size in MB
MAX_SIGNATURE_SIZE_MB = 5


class SignatureLoaderService(models.AbstractModel):
    """
    Signature Loader Service

    Responsible for:
    - Loading company signature with multiple fallbacks
    - Loading subcontractor signature from signature records
    - Validating signature images (format, size, readability)
    - Providing clear error messages in French for users
    """

    _name = 'construction.contract.signature.loader'
    _description = 'Signature Loader Service'

    # ============================================================
    # COMPANY SIGNATURE LOADING
    # ============================================================

    @api.model
    def load_company_signature(self):
        """
        Load company signature with multiple fallbacks
        
        Fallback order:
        1. res.company.signature field
        2. res.users.signature field (current user)
        3. static/src/img/blg_signature.png file
        
        Returns:
            dict: {
                'image_data': str (base64 data URL),
                'signer_name': str
            }
            
        Raises:
            UserError: If no signature found after all fallbacks (with French message)
        """
        company = self.env.company
        
        # Fallback 1: Try res.company.signature
        if hasattr(company, 'signature') and company.signature:
            try:
                signature_data = self._load_signature_from_field(
                    company.signature,
                    company.name
                )
                if signature_data:
                    _logger.info(f"✓ Loaded company signature from res.company for {company.name}")
                    return signature_data
            except Exception as e:
                _logger.warning(f"Failed to load company signature from res.company: {e}")
        
        # Fallback 2: Try res.users.signature (current user)
        current_user = self.env.user
        if hasattr(current_user, 'signature') and current_user.signature:
            try:
                signature_data = self._load_signature_from_field(
                    current_user.signature,
                    current_user.name or company.name
                )
                if signature_data:
                    _logger.info(f"✓ Loaded company signature from res.users for {current_user.name}")
                    return signature_data
            except Exception as e:
                _logger.warning(f"Failed to load user signature from res.users: {e}")
        
        # Fallback 3: Load from static file
        try:
            signature_data = self._load_signature_from_static_file(company.name)
            if signature_data:
                _logger.info(f"✓ Loaded company signature from static file")
                return signature_data
        except Exception as e:
            _logger.error(f"Failed to load signature from static file: {e}", exc_info=True)
        
        # All fallbacks failed - raise clear error in French with detailed instructions
        error_message = _(
            "❌ Signature de l'entreprise introuvable\n\n"
            "La signature de votre entreprise n'a pas pu être chargée. "
            "Le contrat ne peut pas être généré sans signature.\n\n"
            "Solutions possibles :\n"
            "1. Ajoutez une signature dans Paramètres > Entreprises > Signature\n"
            "   • Allez dans Paramètres > Entreprises\n"
            "   • Sélectionnez votre entreprise\n"
            "   • Ajoutez une image de signature dans le champ 'Signature'\n\n"
            "2. Ajoutez une signature dans votre profil utilisateur\n"
            "   • Cliquez sur votre nom en haut à droite\n"
            "   • Sélectionnez 'Préférences'\n"
            "   • Ajoutez une image de signature\n\n"
            "3. Placez le fichier 'blg_signature.png' dans le dossier "
            "'static/src/img/' du module\n"
            "   • Le fichier doit être au format PNG ou JPEG\n"
            "   • Taille maximale : %d MB\n\n"
            "Contactez l'administrateur si le problème persiste."
        ) % MAX_SIGNATURE_SIZE_MB
        _logger.error(
            f"✗ All signature loading fallbacks failed for company {company.name}. "
            f"Attempted: res.company.signature, res.users.signature, static file"
        )
        raise UserError(error_message)

    def _load_signature_from_field(self, signature_field_data, signer_name):
        """
        Load signature from Odoo binary field (res.company.signature or res.users.signature)
        
        Args:
            signature_field_data: Binary field data (base64 encoded)
            signer_name: Name of the signer
            
        Returns:
            dict or None: Signature data if successful
        """
        try:
            # Decode to verify it's valid
            signature_bytes = base64.b64decode(signature_field_data)
            
            # Validate signature
            if not self.validate_signature_image(signature_bytes):
                _logger.warning(
                    f"Signature validation failed for {signer_name}: "
                    f"size={len(signature_bytes)} bytes, "
                    f"format check failed"
                )
                return None
            
            # Re-encode to base64 for data URL
            signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
            
            _logger.debug(
                f"Successfully loaded signature from field for {signer_name}: "
                f"{len(signature_bytes)} bytes"
            )
            
            return {
                'image_data': f'data:image/png;base64,{signature_b64}',
                'signer_name': signer_name,
            }
        except base64.binascii.Error as e:
            _logger.warning(
                f"Invalid base64 data in signature field for {signer_name}: {e}"
            )
            return None
        except Exception as e:
            _logger.warning(
                f"Unexpected error loading signature from field for {signer_name}: {e}",
                exc_info=True
            )
            return None

    def _load_signature_from_static_file(self, signer_name):
        """
        Load signature from static/src/img/blg_signature.png
        
        Args:
            signer_name: Name of the signer
            
        Returns:
            dict or None: Signature data if successful
        """
        signature_file_path = None
        
        # Method 1: Relative to current file
        try:
            current_file = os.path.abspath(__file__)
            services_dir = os.path.dirname(current_file)
            module_root = os.path.dirname(services_dir)
            path1 = os.path.normpath(
                os.path.join(module_root, 'static', 'src', 'img', 'blg_signature.png')
            )
            
            if os.path.exists(path1):
                signature_file_path = path1
                _logger.debug(f"Found signature file at: {path1}")
        except Exception as e:
            _logger.warning(f"Method 1 failed to locate signature file: {e}")
        
        # Method 2: Using Odoo's module path
        if not signature_file_path:
            try:
                from odoo.modules.module import get_module_path
                module_path = get_module_path('construction_contract')
                if module_path:
                    path2 = os.path.normpath(
                        os.path.join(module_path, 'static', 'src', 'img', 'blg_signature.png')
                    )
                    if os.path.exists(path2):
                        signature_file_path = path2
                        _logger.debug(f"Found signature file at: {path2}")
            except Exception as e:
                _logger.warning(f"Method 2 failed to locate signature file: {e}")
        
        # Load file if found
        if signature_file_path and os.path.exists(signature_file_path):
            try:
                with open(signature_file_path, 'rb') as f:
                    signature_bytes = f.read()
                
                # Validate signature
                if not self.validate_signature_image(signature_bytes):
                    _logger.error(f"Signature file validation failed: {signature_file_path}")
                    return None
                
                # Encode to base64
                signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
                
                _logger.info(
                    f"✓ Loaded signature from static file: {signature_file_path} "
                    f"({len(signature_bytes)} bytes)"
                )
                
                return {
                    'image_data': f'data:image/png;base64,{signature_b64}',
                    'signer_name': signer_name,
                }
            except Exception as e:
                _logger.error(f"Error reading signature file {signature_file_path}: {e}")
                return None
        
        # File not found
        _logger.error(f"✗ Signature file blg_signature.png not found")
        return None

    # ============================================================
    # SUBCONTRACTOR SIGNATURE LOADING
    # ============================================================

    @api.model
    def load_subcontractor_signature(self, signature_record):
        """
        Load subcontractor signature from signature record
        
        Args:
            signature_record: construction.contract.signature record
            
        Returns:
            dict: {
                'image_data': str (base64 data URL),
                'signature_date': str,
                'signer_name': str
            }
            
        Raises:
            UserError: If signature record is invalid (with French message)
        """
        if not signature_record:
            error_msg = _("Aucun enregistrement de signature fourni.")
            _logger.error(f"✗ Subcontractor signature loading failed: no signature record provided")
            raise UserError(error_msg)
        
        signature_record.ensure_one()
        
        try:
            # Check if signature data exists
            if not signature_record.signature_data:
                error_msg = _(
                    "❌ Données de signature manquantes\n\n"
                    "L'enregistrement de signature existe mais ne contient pas de données d'image.\n\n"
                    "Veuillez demander au sous-traitant de signer à nouveau le contrat."
                )
                _logger.error(
                    f"✗ Signature record {signature_record.id} has no signature_data field"
                )
                raise UserError(error_msg)
            
            # Decode signature data
            try:
                signature_bytes = base64.b64decode(signature_record.signature_data)
            except base64.binascii.Error as e:
                error_msg = _(
                    "❌ Signature corrompue\n\n"
                    "Les données de signature sont corrompues ou invalides.\n\n"
                    "Veuillez demander au sous-traitant de signer à nouveau le contrat."
                )
                _logger.error(
                    f"✗ Invalid base64 data in signature record {signature_record.id}: {e}"
                )
                raise UserError(error_msg)
            
            # Validate signature
            if not self.validate_signature_image(signature_bytes):
                error_msg = _(
                    "❌ Signature invalide\n\n"
                    "La signature du sous-traitant est invalide ou corrompue.\n\n"
                    "Raisons possibles :\n"
                    "• Format d'image non supporté (utilisez PNG ou JPEG)\n"
                    "• Fichier trop volumineux (max %d MB)\n"
                    "• Données d'image corrompues\n\n"
                    "Veuillez demander au sous-traitant de signer à nouveau."
                ) % MAX_SIGNATURE_SIZE_MB
                _logger.error(
                    f"✗ Signature validation failed for record {signature_record.id}: "
                    f"size={len(signature_bytes)} bytes"
                )
                raise UserError(error_msg)
            
            # Re-encode to base64 for data URL
            signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
            
            signature_data = {
                'image_data': f'data:image/png;base64,{signature_b64}',
                'signature_date': signature_record.signature_date.strftime('%d/%m/%Y') if signature_record.signature_date else '',
                'signer_name': signature_record.signer_name or '',
            }
            
            _logger.info(
                f"✓ Loaded subcontractor signature for {signature_record.signer_name} "
                f"(record_id={signature_record.id}, size={len(signature_bytes)} bytes, "
                f"date={signature_data['signature_date']})"
            )
            
            return signature_data
            
        except UserError:
            # Re-raise UserError as-is (already has French message)
            raise
        except Exception as e:
            # Unexpected error - log and raise with French message
            _logger.error(
                f"✗ Unexpected error loading subcontractor signature "
                f"(record_id={signature_record.id}): {e}",
                exc_info=True
            )
            raise UserError(_(
                "❌ Erreur inattendue lors du chargement de la signature\n\n"
                "Une erreur inattendue s'est produite lors du chargement "
                "de la signature du sous-traitant.\n\n"
                "Détails techniques : %s\n\n"
                "Veuillez contacter l'administrateur système."
            ) % str(e))

    # ============================================================
    # SIGNATURE VALIDATION
    # ============================================================

    @api.model
    def validate_signature_image(self, image_data, return_details=False):
        """
        Validate signature image (format, size, readability)
        
        Args:
            image_data: bytes or base64 string
            return_details: bool - if True, returns tuple (is_valid, error_details)
            
        Returns:
            bool: True if valid, False otherwise (when return_details=False)
            tuple: (bool, dict) - (is_valid, error_details) when return_details=True
                   error_details contains: {'error_code': str, 'error_message': str, 'details': dict}
        """
        error_details = None
        
        try:
            # Convert to bytes if base64 string
            if isinstance(image_data, str):
                try:
                    image_bytes = base64.b64decode(image_data)
                except base64.binascii.Error as e:
                    error_details = {
                        'error_code': 'INVALID_BASE64',
                        'error_message': _("Les données de l'image ne sont pas valides (encodage base64 incorrect)."),
                        'details': {'exception': str(e)}
                    }
                    _logger.warning(f"Invalid base64 data in signature: {e}")
                    return (False, error_details) if return_details else False
            else:
                image_bytes = image_data
            
            # Check if empty
            if not image_bytes:
                error_details = {
                    'error_code': 'EMPTY_IMAGE',
                    'error_message': _("L'image de signature est vide."),
                    'details': {'size': 0}
                }
                _logger.warning("Signature image is empty")
                return (False, error_details) if return_details else False
            
            # Check size - too large
            size_mb = len(image_bytes) / (1024 * 1024)
            if size_mb > MAX_SIGNATURE_SIZE_MB:
                error_details = {
                    'error_code': 'SIZE_TOO_LARGE',
                    'error_message': _("L'image de signature est trop volumineuse (%.2f MB). Maximum autorisé : %d MB.") % (size_mb, MAX_SIGNATURE_SIZE_MB),
                    'details': {'size_mb': size_mb, 'max_size_mb': MAX_SIGNATURE_SIZE_MB}
                }
                _logger.warning(
                    f"Signature image too large: {size_mb:.2f} MB "
                    f"(max: {MAX_SIGNATURE_SIZE_MB} MB)"
                )
                return (False, error_details) if return_details else False
            
            # Check minimum size (at least 100 bytes)
            if len(image_bytes) < 100:
                error_details = {
                    'error_code': 'SIZE_TOO_SMALL',
                    'error_message': _("L'image de signature est trop petite ou corrompue (%d octets).") % len(image_bytes),
                    'details': {'size_bytes': len(image_bytes), 'min_size_bytes': 100}
                }
                _logger.warning(f"Signature image too small: {len(image_bytes)} bytes")
                return (False, error_details) if return_details else False
            
            # Check image format (PNG or JPEG magic numbers)
            is_png = image_bytes[:8] == b'\x89PNG\r\n\x1a\n'
            is_jpeg = image_bytes[:2] == b'\xff\xd8'
            
            if not (is_png or is_jpeg):
                # Try to identify what format it is
                detected_format = 'unknown'
                if image_bytes[:4] == b'GIF8':
                    detected_format = 'GIF'
                elif image_bytes[:4] == b'RIFF':
                    detected_format = 'WEBP'
                elif image_bytes[:2] == b'BM':
                    detected_format = 'BMP'
                
                error_details = {
                    'error_code': 'INVALID_FORMAT',
                    'error_message': _("Format d'image non supporté. Utilisez PNG ou JPEG. Format détecté : %s") % detected_format,
                    'details': {
                        'detected_format': detected_format,
                        'supported_formats': ['PNG', 'JPEG']
                    }
                }
                _logger.warning(f"Signature image is not PNG or JPEG format (detected: {detected_format})")
                return (False, error_details) if return_details else False
            
            # Validation passed
            format_name = 'PNG' if is_png else 'JPEG'
            _logger.debug(
                f"Signature validation passed: {format_name}, {size_mb:.2f} MB"
            )
            
            if return_details:
                return (True, {
                    'error_code': None,
                    'error_message': None,
                    'details': {
                        'format': format_name,
                        'size_mb': size_mb,
                        'size_bytes': len(image_bytes)
                    }
                })
            return True
            
        except Exception as e:
            error_details = {
                'error_code': 'VALIDATION_ERROR',
                'error_message': _("Erreur lors de la validation de la signature : %s") % str(e),
                'details': {'exception': str(e)}
            }
            _logger.error(f"Signature validation error: {e}")
            return (False, error_details) if return_details else False
