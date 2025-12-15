# utils/helpers.py
"""
Fonctions utilitaires pour l'ensemble des modules construction.
Centralise les opérations communes et utilitaires.
"""

import base64
import hashlib
import secrets
import string
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Optional, Any, Union
import logging
import re

_logger = logging.getLogger(__name__)


# =============== HELPERS POUR FICHIERS ===============

class FileHelper:
    """Utilitaires pour la gestion des fichiers"""

    @staticmethod
    def generate_safe_filename(original_name: str, prefix: str = "", suffix: str = "") -> str:
        """
        Génère un nom de fichier sécurisé.

        Args:
            original_name: Nom original du fichier
            prefix: Préfixe à ajouter
            suffix: Suffixe à ajouter (avant l'extension)
        """
        # Nettoyer le nom de fichier
        clean_name = re.sub(r'[^\w\-_.]', '_', original_name)
        clean_name = re.sub(r'_+', '_', clean_name)  # Réduire les underscores multiples

        # Séparer nom et extension
        if '.' in clean_name:
            name_part, extension = clean_name.rsplit('.', 1)
        else:
            name_part, extension = clean_name, ''

        # Construire le nouveau nom
        parts = []
        if prefix:
            parts.append(prefix)
        parts.append(name_part)
        if suffix:
            parts.append(suffix)

        new_name = '_'.join(parts)

        if extension:
            new_name = f"{new_name}.{extension}"

        return new_name

    @staticmethod
    def calculate_file_hash(file_content: bytes, algorithm: str = 'sha256') -> str:
        """
        Calcule le hash d'un fichier.

        Args:
            file_content: Contenu du fichier en bytes
            algorithm: Algorithme de hash (md5, sha1, sha256)
        """
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(file_content)
        return hash_obj.hexdigest()

    @staticmethod
    def encode_file_to_base64(file_content: bytes) -> str:
        """Encode un fichier en base64"""
        return base64.b64encode(file_content).decode('utf-8')

    @staticmethod
    def decode_base64_to_file(base64_content: str) -> bytes:
        """Décode un contenu base64 en bytes"""
        return base64.b64decode(base64_content)

    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Récupère l'extension d'un fichier"""
        return filename.split('.')[-1].lower() if '.' in filename else ''

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Formate une taille de fichier de manière lisible.

        Args:
            size_bytes: Taille en octets

        Returns:
            Taille formatée (ex: "2.5 MB")
        """
        if size_bytes == 0:
            return "0 B"

        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0

        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1

        return f"{size_bytes:.1f} {size_names[i]}"


# =============== HELPERS POUR DATES ===============

class DateHelper:
    """Utilitaires pour la gestion des dates"""

    @staticmethod
    def format_date_fr(date_obj: Union[date, datetime], include_time: bool = False) -> str:
        """
        Formate une date au format français.

        Args:
            date_obj: Date à formater
            include_time: Inclure l'heure
        """
        if not date_obj:
            return ""

        if include_time and isinstance(date_obj, datetime):
            return date_obj.strftime("%d/%m/%Y à %H:%M")
        else:
            return date_obj.strftime("%d/%m/%Y")

    @staticmethod
    def parse_date_fr(date_str: str) -> Optional[date]:
        """
        Parse une date au format français (DD/MM/YYYY).

        Args:
            date_str: Date en format string français

        Returns:
            Date parsée ou None si erreur
        """
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            try:
                return datetime.strptime(date_str, "%d-%m-%Y").date()
            except ValueError:
                return None

    @staticmethod
    def get_days_until(target_date: date) -> int:
        """
        Calcule le nombre de jours jusqu'à une date cible.

        Args:
            target_date: Date cible

        Returns:
            Nombre de jours (négatif si dans le passé)
        """
        if not target_date:
            return 0

        return (target_date - date.today()).days

    @staticmethod
    def is_working_day(check_date: date) -> bool:
        """
        Vérifie si une date est un jour ouvrable (lundi-vendredi).

        Args:
            check_date: Date à vérifier

        Returns:
            True si jour ouvrable
        """
        return check_date.weekday() < 5  # 0-4 = Lundi-Vendredi

    @staticmethod
    def add_working_days(start_date: date, days: int) -> date:
        """
        Ajoute des jours ouvrables à une date.

        Args:
            start_date: Date de départ
            days: Nombre de jours ouvrables à ajouter

        Returns:
            Date finale
        """
        current_date = start_date
        days_added = 0

        while days_added < days:
            current_date += timedelta(days=1)
            if DateHelper.is_working_day(current_date):
                days_added += 1

        return current_date

    @staticmethod
    def get_quarter(date_obj: date) -> int:
        """
        Retourne le trimestre d'une date (1-4).

        Args:
            date_obj: Date

        Returns:
            Numéro du trimestre
        """
        return (date_obj.month - 1) // 3 + 1

    @staticmethod
    def get_age_in_months(birth_date: date, reference_date: date = None) -> int:
        """
        Calcule l'âge en mois entre deux dates.

        Args:
            birth_date: Date de naissance/début
            reference_date: Date de référence (aujourd'hui par défaut)

        Returns:
            Âge en mois
        """
        if not reference_date:
            reference_date = date.today()

        return (reference_date.year - birth_date.year) * 12 + (reference_date.month - birth_date.month)

    @staticmethod
    def get_date_range_description(start_date: date, end_date: date) -> str:
        """
        Génère une description textuelle d'une période.

        Args:
            start_date: Date de début
            end_date: Date de fin

        Returns:
            Description de la période
        """
        if not start_date or not end_date:
            return "Période non définie"

        duration = (end_date - start_date).days

        if duration == 0:
            return f"Le {DateHelper.format_date_fr(start_date)}"
        elif duration == 1:
            return f"Du {DateHelper.format_date_fr(start_date)} au {DateHelper.format_date_fr(end_date)} (2 jours)"
        else:
            return f"Du {DateHelper.format_date_fr(start_date)} au {DateHelper.format_date_fr(end_date)} ({duration + 1} jours)"


# =============== HELPERS POUR TOKENS ET SÉCURITÉ ===============

class SecurityHelper:
    """Utilitaires pour la sécurité et les tokens"""

    @staticmethod
    def generate_token(length: int = 32, include_special: bool = False) -> str:
        """
        Génère un token sécurisé.

        Args:
            length: Longueur du token
            include_special: Inclure des caractères spéciaux

        Returns:
            Token généré
        """
        alphabet = string.ascii_letters + string.digits
        if include_special:
            alphabet += "!@#$%^&*"

        return ''.join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def generate_upload_token(partner_id: int, validity_days: int = 7) -> Dict[str, Any]:
        """
        Génère un token d'upload avec expiration.

        Args:
            partner_id: ID du partenaire
            validity_days: Nombre de jours de validité

        Returns:
            Dictionnaire avec token et expiration
        """
        token = SecurityHelper.generate_token(32)
        expiration = datetime.now() + timedelta(days=validity_days)

        return {
            'token': token,
            'expiration': expiration,
            'partner_id': partner_id,
            'created_at': datetime.now()
        }

    @staticmethod
    def hash_password(password: str, salt: str = None) -> Dict[str, str]:
        """
        Hash un mot de passe avec sel.

        Args:
            password: Mot de passe en clair
            salt: Sel (généré automatiquement si non fourni)

        Returns:
            Dictionnaire avec hash et sel
        """
        if not salt:
            salt = secrets.token_hex(16)

        # Utiliser PBKDF2 pour le hash
        password_hash = hashlib.pbkdf2_hmac('sha256',
                                            password.encode('utf-8'),
                                            salt.encode('utf-8'),
                                            100000)  # 100k itérations

        return {
            'hash': password_hash.hex(),
            'salt': salt
        }

    @staticmethod
    def verify_password(password: str, stored_hash: str, salt: str) -> bool:
        """
        Vérifie un mot de passe contre son hash.

        Args:
            password: Mot de passe en clair
            stored_hash: Hash stocké
            salt: Sel utilisé

        Returns:
            True si le mot de passe correspond
        """
        password_hash = hashlib.pbkdf2_hmac('sha256',
                                            password.encode('utf-8'),
                                            salt.encode('utf-8'),
                                            100000)

        return password_hash.hex() == stored_hash

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sécurise un nom de fichier en supprimant les caractères dangereux.

        Args:
            filename: Nom de fichier à sécuriser

        Returns:
            Nom de fichier sécurisé
        """
        # Supprimer les caractères dangereux
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

        # Supprimer les points en début/fin
        safe_filename = safe_filename.strip('.')

        # Limiter la longueur
        if len(safe_filename) > 255:
            name, ext = safe_filename.rsplit('.', 1) if '.' in safe_filename else (safe_filename, '')
            max_name_length = 255 - len(ext) - 1 if ext else 255
            safe_filename = name[:max_name_length] + ('.' + ext if ext else '')

        return safe_filename or 'fichier'


# =============== HELPERS POUR DONNÉES ===============

class DataHelper:
    """Utilitaires pour la manipulation de données"""

    @staticmethod
    def safe_get(data: dict, key: str, default: Any = None, type_cast: type = None) -> Any:
        """
        Récupère une valeur d'un dictionnaire de manière sécurisée.

        Args:
            data: Dictionnaire source
            key: Clé à récupérer
            default: Valeur par défaut
            type_cast: Type pour casting automatique

        Returns:
            Valeur récupérée et éventuellement castée
        """
        value = data.get(key, default)

        if type_cast and value is not None:
            try:
                return type_cast(value)
            except (ValueError, TypeError):
                return default

        return value

    @staticmethod
    def clean_text(text: str, max_length: int = None) -> str:
        """
        Nettoie un texte en supprimant espaces superflus et caractères indésirables.

        Args:
            text: Texte à nettoyer
            max_length: Longueur maximum

        Returns:
            Texte nettoyé
        """
        if not text:
            return ""

        # Nettoyer les espaces
        cleaned = re.sub(r'\s+', ' ', text.strip())

        # Supprimer les caractères de contrôle
        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)

        # Tronquer si nécessaire
        if max_length and len(cleaned) > max_length:
            cleaned = cleaned[:max_length].strip()

        return cleaned

    @staticmethod
    def merge_dicts(*dicts: dict, deep: bool = False) -> dict:
        """
        Fusionne plusieurs dictionnaires.

        Args:
            *dicts: Dictionnaires à fusionner
            deep: Fusion profonde (récursive)

        Returns:
            Dictionnaire fusionné
        """
        if not deep:
            result = {}
            for d in dicts:
                result.update(d)
            return result

        # Fusion profonde
        result = {}
        for d in dicts:
            DataHelper._deep_merge(result, d)
        return result

    @staticmethod
    def _deep_merge(base: dict, update: dict) -> None:
        """Fusion profonde de dictionnaires (modifie base)"""
        for key, value in update.items():
            if (key in base and
                    isinstance(base[key], dict) and
                    isinstance(value, dict)):
                DataHelper._deep_merge(base[key], value)
            else:
                base[key] = value

    @staticmethod
    def flatten_dict(data: dict, separator: str = '.', prefix: str = '') -> dict:
        """
        Aplatit un dictionnaire imbriqué.

        Args:
            data: Dictionnaire à aplatir
            separator: Séparateur pour les clés
            prefix: Préfixe pour les clés

        Returns:
            Dictionnaire aplati
        """
        result = {}

        for key, value in data.items():
            new_key = f"{prefix}{separator}{key}" if prefix else key

            if isinstance(value, dict):
                result.update(DataHelper.flatten_dict(value, separator, new_key))
            else:
                result[new_key] = value

        return result

    @staticmethod
    def chunk_list(data_list: List[Any], chunk_size: int) -> List[List[Any]]:
        """
        Divise une liste en chunks de taille donnée.

        Args:
            data_list: Liste à diviser
            chunk_size: Taille des chunks

        Returns:
            Liste de chunks
        """
        return [data_list[i:i + chunk_size] for i in range(0, len(data_list), chunk_size)]

    @staticmethod
    def remove_duplicates(data_list: List[Any], key_func: callable = None) -> List[Any]:
        """
        Supprime les doublons d'une liste.

        Args:
            data_list: Liste avec doublons
            key_func: Fonction pour extraire la clé de comparaison

        Returns:
            Liste sans doublons
        """
        if not key_func:
            return list(dict.fromkeys(data_list))  # Préserve l'ordre

        seen = set()
        result = []

        for item in data_list:
            key = key_func(item)
            if key not in seen:
                seen.add(key)
                result.append(item)

        return result


# =============== HELPERS POUR NOTIFICATIONS ===============

class NotificationHelper:
    """Utilitaires pour les notifications"""

    @staticmethod
    def create_odoo_notification(message: str,
                                 notification_type: str = 'info',
                                 title: str = None,
                                 sticky: bool = None) -> dict:
        """
        Crée une notification Odoo standardisée.

        Args:
            message: Message de la notification
            notification_type: Type (success, warning, danger, info)
            title: Titre optionnel
            sticky: Notification persistante

        Returns:
            Action de notification Odoo
        """
        type_config = {
            'success': {'icon': '✅', 'color': 'success', 'default_sticky': False},
            'warning': {'icon': '⚠️', 'color': 'warning', 'default_sticky': False},
            'danger': {'icon': '❌', 'color': 'danger', 'default_sticky': True},
            'error': {'icon': '❌', 'color': 'danger', 'default_sticky': True},
            'info': {'icon': 'ℹ️', 'color': 'info', 'default_sticky': False}
        }

        config = type_config.get(notification_type, type_config['info'])

        if sticky is None:
            sticky = config['default_sticky']

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title or notification_type.title(),
                'message': f"{config['icon']} {message}",
                'type': config['color'],
                'sticky': sticky
            }
        }

    @staticmethod
    def format_notification_message(template: str, **kwargs) -> str:
        """
        Formate un message de notification avec des variables.

        Args:
            template: Template du message avec placeholders
            **kwargs: Variables à substituer

        Returns:
            Message formaté
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            _logger.warning(f"Missing variable in notification template: {e}")
            return template

    @staticmethod
    def create_bulk_notification(success_count: int,
                                 error_count: int,
                                 operation_name: str) -> dict:
        """
        Crée une notification pour les opérations en lot.

        Args:
            success_count: Nombre de succès
            error_count: Nombre d'erreurs
            operation_name: Nom de l'opération

        Returns:
            Notification appropriée
        """
        total = success_count + error_count

        if error_count == 0:
            return NotificationHelper.create_odoo_notification(
                f"✅ {operation_name} : {success_count}/{total} réussi(s)",
                'success'
            )
        elif success_count == 0:
            return NotificationHelper.create_odoo_notification(
                f"❌ {operation_name} : {error_count}/{total} échec(s)",
                'danger'
            )
        else:
            return NotificationHelper.create_odoo_notification(
                f"⚠️ {operation_name} : {success_count} réussi(s), {error_count} échec(s)",
                'warning'
            )


# =============== HELPERS POUR URLS ===============

class UrlHelper:
    """Utilitaires pour la gestion des URLs"""

    @staticmethod
    def build_portal_url(base_url: str, route: str, token: str, **params) -> str:
        """
        Construit une URL de portail avec token et paramètres.

        Args:
            base_url: URL de base du site
            route: Route du portail
            token: Token d'authentification
            **params: Paramètres additionnels

        Returns:
            URL complète
        """
        # Nettoyer l'URL de base
        base_url = base_url.rstrip('/')
        route = route.lstrip('/')

        # Construire l'URL de base
        url = f"{base_url}/{route}/{token}"

        # Ajouter les paramètres
        if params:
            param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            url = f"{url}?{param_string}"

        return url

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """
        Vérifie qu'une URL est valide.

        Args:
            url: URL à vérifier

        Returns:
            True si l'URL est valide
        """
        pattern = re.compile(
            r'^https?://'  # http:// ou https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domaine
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # port optionnel
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        return pattern.match(url) is not None


# =============== HELPERS POUR LOGS ===============

class LogHelper:
    """Utilitaires pour les logs"""

    @staticmethod
    def log_operation(operation_name: str,
                      success: bool,
                      details: Dict[str, Any] = None,
                      user_id: int = None) -> None:
        """
        Log une opération avec détails standardisés.

        Args:
            operation_name: Nom de l'opération
            success: Succès ou échec
            details: Détails additionnels
            user_id: ID de l'utilisateur
        """
        level = logging.INFO if success else logging.ERROR
        status = "SUCCESS" if success else "FAILED"

        log_message = f"[{status}] {operation_name}"

        if user_id:
            log_message += f" (User: {user_id})"

        if details:
            detail_str = ', '.join([f"{k}={v}" for k, v in details.items()])
            log_message += f" - {detail_str}"

        _logger.log(level, log_message)

    @staticmethod
    def log_performance(operation_name: str,
                        duration_seconds: float,
                        record_count: int = None) -> None:
        """
        Log les performances d'une opération.

        Args:
            operation_name: Nom de l'opération
            duration_seconds: Durée en secondes
            record_count: Nombre d'enregistrements traités
        """
        message = f"[PERF] {operation_name}: {duration_seconds:.3f}s"

        if record_count:
            rate = record_count / duration_seconds if duration_seconds > 0 else 0
            message += f" ({record_count} records, {rate:.1f} rec/s)"

        _logger.info(message)


# =============== HELPERS POUR FORMATS ===============

class FormatHelper:
    """Utilitaires pour le formatage de données"""

    @staticmethod
    def format_currency(amount: float, currency_symbol: str = '€') -> str:
        """
        Formate un montant monétaire.

        Args:
            amount: Montant à formater
            currency_symbol: Symbole de devise

        Returns:
            Montant formaté
        """
        return f"{amount:,.2f} {currency_symbol}".replace(',', ' ')

    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """
        Formate un pourcentage.

        Args:
            value: Valeur à formater
            decimals: Nombre de décimales

        Returns:
            Pourcentage formaté
        """
        return f"{value:.{decimals}f}%"

    @staticmethod
    def format_duration(seconds: int) -> str:
        """
        Formate une durée en secondes en format lisible.

        Args:
            seconds: Durée en secondes

        Returns:
            Durée formatée (ex: "2h 30m 15s")
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            remaining_seconds = seconds % 60
            return f"{hours}h {minutes}m {remaining_seconds}s"

    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """
        Tronque un texte à une longueur donnée.

        Args:
            text: Texte à tronquer
            max_length: Longueur maximum
            suffix: Suffixe à ajouter si tronqué

        Returns:
            Texte tronqué
        """
        if not text or len(text) <= max_length:
            return text

        return text[:max_length - len(suffix)] + suffix
