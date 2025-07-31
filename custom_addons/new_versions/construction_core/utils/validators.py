# utils/validators.py
"""
Validateurs utilitaires pour l'ensemble des modules construction.
Centralise toutes les validations communes.
"""

import re
import mimetypes
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any
import logging

_logger = logging.getLogger(__name__)


class BaseValidator:
    """Classe de base pour tous les validateurs"""

    @staticmethod
    def create_result(is_valid: bool, message: str = "", details: dict = None) -> dict:
        """Crée un résultat de validation standardisé"""
        return {
            'valid': is_valid,
            'message': message,
            'details': details or {}
        }


class FileValidator(BaseValidator):
    """Validateur pour les fichiers"""

    @staticmethod
    def validate_file_type(filename: str, allowed_extensions: List[str]) -> dict:
        """
        Valide l'extension d'un fichier.

        Args:
            filename: Nom du fichier
            allowed_extensions: Extensions autorisées (ex: ['.pdf', '.jpg'])
        """
        if not filename:
            return FileValidator.create_result(False, "Nom de fichier manquant")

        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''

        # Normaliser les extensions (avec ou sans point)
        normalized_allowed = []
        for ext in allowed_extensions:
            normalized_allowed.append(ext.lower().lstrip('.'))

        if file_ext not in normalized_allowed:
            allowed_str = ', '.join(allowed_extensions)
            return FileValidator.create_result(
                False,
                f"Extension non autorisée. Extensions acceptées : {allowed_str}",
                {'file_extension': file_ext, 'allowed': allowed_extensions}
            )

        return FileValidator.create_result(True, "Extension valide")

    @staticmethod
    def validate_file_size(file_size: int, max_size_mb: float) -> dict:
        """
        Valide la taille d'un fichier.

        Args:
            file_size: Taille en octets
            max_size_mb: Taille maximum en MB
        """
        max_size_bytes = max_size_mb * 1024 * 1024

        if file_size > max_size_bytes:
            return FileValidator.create_result(
                False,
                f"Fichier trop volumineux ({file_size / 1024 / 1024:.1f}MB). Maximum autorisé : {max_size_mb}MB",
                {'file_size_mb': file_size / 1024 / 1024, 'max_size_mb': max_size_mb}
            )

        if file_size == 0:
            return FileValidator.create_result(False, "Le fichier est vide")

        return FileValidator.create_result(True, "Taille de fichier valide")

    @staticmethod
    def validate_mime_type(file_content: bytes, allowed_types: List[str]) -> dict:
        """
        Valide le type MIME d'un fichier basé sur son contenu.

        Args:
            file_content: Contenu du fichier en bytes
            allowed_types: Types MIME autorisés
        """
        if not file_content:
            return FileValidator.create_result(False, "Contenu de fichier vide")

        # Détection basique par signature
        mime_type = FileValidator._detect_mime_type(file_content)

        if mime_type not in allowed_types:
            return FileValidator.create_result(
                False,
                f"Type de fichier non autorisé ({mime_type})",
                {'detected_type': mime_type, 'allowed_types': allowed_types}
            )

        return FileValidator.create_result(True, "Type de fichier valide")

    @staticmethod
    def _detect_mime_type(file_content: bytes) -> str:
        """Détecte le type MIME par signature de fichier"""
        # Signatures de fichiers communes
        signatures = {
            b'%PDF': 'application/pdf',
            b'\xFF\xD8\xFF': 'image/jpeg',
            b'\x89PNG\r\n\x1a\n': 'image/png',
            b'GIF87a': 'image/gif',
            b'GIF89a': 'image/gif',
        }

        for signature, mime_type in signatures.items():
            if file_content.startswith(signature):
                return mime_type

        return 'application/octet-stream'  # Type par défaut


class DateValidator(BaseValidator):
    """Validateur pour les dates"""

    @staticmethod
    def validate_date_format(date_str: str, date_format: str = '%Y-%m-%d') -> dict:
        """
        Valide le format d'une date.

        Args:
            date_str: Date en format string
            date_format: Format attendu
        """
        try:
            parsed_date = datetime.strptime(date_str, date_format).date()
            return DateValidator.create_result(
                True,
                "Format de date valide",
                {'parsed_date': parsed_date}
            )
        except ValueError:
            return DateValidator.create_result(
                False,
                f"Format de date invalide. Format attendu : {date_format}"
            )

    @staticmethod
    def validate_expiry_date(expiry_date: date, min_validity_days: int = 0) -> dict:
        """
        Valide qu'une date d'expiration est dans le futur.

        Args:
            expiry_date: Date d'expiration
            min_validity_days: Nombre minimum de jours de validité
        """
        if not expiry_date:
            return DateValidator.create_result(False, "Date d'expiration manquante")

        today = date.today()
        days_until_expiry = (expiry_date - today).days

        if days_until_expiry < min_validity_days:
            if days_until_expiry < 0:
                return DateValidator.create_result(
                    False,
                    f"Date d'expiration dépassée depuis {abs(days_until_expiry)} jour(s)"
                )
            else:
                return DateValidator.create_result(
                    False,
                    f"Date d'expiration trop proche ({days_until_expiry} jour(s)). "
                    f"Minimum requis : {min_validity_days} jour(s)"
                )

        return DateValidator.create_result(
            True,
            f"Date d'expiration valide ({days_until_expiry} jour(s) de validité)"
        )

    @staticmethod
    def validate_date_range(start_date: date, end_date: date, max_duration_days: int = None) -> dict:
        """
        Valide une plage de dates.

        Args:
            start_date: Date de début
            end_date: Date de fin
            max_duration_days: Durée maximum autorisée
        """
        if not start_date or not end_date:
            return DateValidator.create_result(False, "Dates de début et fin requises")

        if end_date <= start_date:
            return DateValidator.create_result(
                False,
                "La date de fin doit être postérieure à la date de début"
            )

        duration_days = (end_date - start_date).days

        if max_duration_days and duration_days > max_duration_days:
            return DateValidator.create_result(
                False,
                f"Durée trop longue ({duration_days} jours). Maximum : {max_duration_days} jours"
            )

        return DateValidator.create_result(
            True,
            f"Plage de dates valide ({duration_days} jours)"
        )


class TextValidator(BaseValidator):
    """Validateur pour les chaînes de caractères"""

    @staticmethod
    def validate_required_text(text: str, field_name: str = "champ") -> dict:
        """Valide qu'un texte n'est pas vide"""
        if not text or not text.strip():
            return TextValidator.create_result(False, f"{field_name} requis")

        return TextValidator.create_result(True, "Texte valide")

    @staticmethod
    def validate_text_length(text: str, min_length: int = 0, max_length: int = None) -> dict:
        """
        Valide la longueur d'un texte.

        Args:
            text: Texte à valider
            min_length: Longueur minimum
            max_length: Longueur maximum
        """
        if not text:
            text = ""

        length = len(text)

        if length < min_length:
            return TextValidator.create_result(
                False,
                f"Texte trop court ({length} caractères). Minimum : {min_length}"
            )

        if max_length and length > max_length:
            return TextValidator.create_result(
                False,
                f"Texte trop long ({length} caractères). Maximum : {max_length}"
            )

        return TextValidator.create_result(True, f"Longueur valide ({length} caractères)")

    @staticmethod
    def validate_email(email: str) -> dict:
        """Valide un format d'email"""
        if not email:
            return TextValidator.create_result(False, "Adresse email requise")

        # Pattern de validation email simple mais robuste
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not re.match(pattern, email):
            return TextValidator.create_result(False, "Format d'email invalide")

        return TextValidator.create_result(True, "Format d'email valide")

    @staticmethod
    def validate_phone(phone: str, country_code: str = 'FR') -> dict:
        """
        Valide un numéro de téléphone.

        Args:
            phone: Numéro de téléphone
            country_code: Code pays (pour validation spécifique)
        """
        if not phone:
            return TextValidator.create_result(False, "Numéro de téléphone requis")

        # Nettoyer le numéro
        clean_phone = re.sub(r'[^\d+]', '', phone)

        if country_code == 'FR':
            # Validation pour numéros français
            if clean_phone.startswith('+33'):
                clean_phone = '0' + clean_phone[3:]

            if not (clean_phone.startswith('0') and len(clean_phone) == 10):
                return TextValidator.create_result(
                    False,
                    "Format de téléphone français invalide (ex: 01.23.45.67.89)"
                )

        return TextValidator.create_result(True, "Numéro de téléphone valide")


class BusinessValidator(BaseValidator):
    """Validateur pour les règles métier spécifiques"""

    @staticmethod
    def validate_siret(siret: str) -> dict:
        """Valide un numéro SIRET français"""
        if not siret:
            return BusinessValidator.create_result(False, "Numéro SIRET requis")

        # Nettoyer le SIRET
        clean_siret = re.sub(r'[^\d]', '', siret)

        if len(clean_siret) != 14:
            return BusinessValidator.create_result(
                False,
                "Le SIRET doit contenir 14 chiffres"
            )

        # Validation Luhn pour SIRET
        if not BusinessValidator._validate_luhn(clean_siret):
            return BusinessValidator.create_result(False, "Numéro SIRET invalide")

        return BusinessValidator.create_result(True, "SIRET valide")

    @staticmethod
    def validate_iban(iban: str) -> dict:
        """Valide un code IBAN"""
        if not iban:
            return BusinessValidator.create_result(False, "Code IBAN requis")

        # Nettoyer l'IBAN
        clean_iban = re.sub(r'[^\dA-Z]', '', iban.upper())

        if len(clean_iban) < 15 or len(clean_iban) > 34:
            return BusinessValidator.create_result(
                False,
                "Longueur IBAN invalide (15-34 caractères)"
            )

        # Validation modulo 97
        if not BusinessValidator._validate_iban_checksum(clean_iban):
            return BusinessValidator.create_result(False, "Code IBAN invalide")

        return BusinessValidator.create_result(True, "IBAN valide")

    @staticmethod
    def validate_amount(amount: float, min_amount: float = 0, max_amount: float = None) -> dict:
        """
        Valide un montant financier.

        Args:
            amount: Montant à valider
            min_amount: Montant minimum
            max_amount: Montant maximum
        """
        if amount < min_amount:
            return BusinessValidator.create_result(
                False,
                f"Montant trop faible ({amount}). Minimum : {min_amount}"
            )

        if max_amount and amount > max_amount:
            return BusinessValidator.create_result(
                False,
                f"Montant trop élevé ({amount}). Maximum : {max_amount}"
            )

        return BusinessValidator.create_result(True, f"Montant valide : {amount}")

    @staticmethod
    def _validate_luhn(number: str) -> bool:
        """Algorithme de Luhn pour validation de numéros"""

        def luhn_checksum(card_num):
            def digits_of(n):
                return [int(d) for d in str(n)]

            digits = digits_of(card_num)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d * 2))
            return checksum % 10

        return luhn_checksum(number) == 0

    @staticmethod
    def _validate_iban_checksum(iban: str) -> bool:
        """Validation du checksum IBAN avec modulo 97"""
        # Déplacer les 4 premiers caractères à la fin
        rearranged = iban[4:] + iban[:4]

        # Remplacer les lettres par leurs valeurs numériques
        numeric = ''
        for char in rearranged:
            if char.isdigit():
                numeric += char
            else:
                numeric += str(ord(char) - ord('A') + 10)

        # Calcul modulo 97
        return int(numeric) % 97 == 1


class CompoundValidator(BaseValidator):
    """Validateur pour combiner plusieurs validations"""

    @staticmethod
    def validate_all(validators: List[Tuple[callable, tuple, dict]]) -> dict:
        """
        Applique plusieurs validateurs et retourne le premier échec ou succès global.

        Args:
            validators: Liste de tuples (fonction_validation, args, kwargs)
        """
        results = []

        for validator_func, args, kwargs in validators:
            try:
                result = validator_func(*args, **kwargs)
                results.append(result)

                if not result['valid']:
                    return CompoundValidator.create_result(
                        False,
                        result['message'],
                        {'failed_validation': validator_func.__name__, 'all_results': results}
                    )
            except Exception as e:
                return CompoundValidator.create_result(
                    False,
                    f"Erreur dans la validation {validator_func.__name__}: {str(e)}"
                )

        return CompoundValidator.create_result(
            True,
            f"Toutes les validations réussies ({len(results)})",
            {'all_results': results}
        )

    @staticmethod
    def validate_any(validators: List[Tuple[callable, tuple, dict]]) -> dict:
        """
        Applique plusieurs validateurs et réussit si au moins un passe.

        Args:
            validators: Liste de tuples (fonction_validation, args, kwargs)
        """
        results = []

        for validator_func, args, kwargs in validators:
            try:
                result = validator_func(*args, **kwargs)
                results.append(result)

                if result['valid']:
                    return CompoundValidator.create_result(
                        True,
                        f"Validation réussie avec {validator_func.__name__}",
                        {'successful_validation': validator_func.__name__, 'all_results': results}
                    )
            except Exception as e:
                results.append({
                    'valid': False,
                    'message': f"Erreur dans {validator_func.__name__}: {str(e)}"
                })

        return CompoundValidator.create_result(
            False,
            "Aucune validation n'a réussi",
            {'all_results': results}
        )
