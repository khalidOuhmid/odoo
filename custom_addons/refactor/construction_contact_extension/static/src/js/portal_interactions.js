/** @odoo-module **/

/**
 * Portal Interactions JavaScript
 * Gestion des interactions utilisateur avancées dans le portail
 */

(function() {
    'use strict';

    /**
     * Gestionnaire d'interactions du portail
     */
    class PortalInteractionManager {
        constructor() {
            this.activeInteractions = new Map();
            this.keyboardShortcuts = new Map();
            this.touchGestures = new Map();
            this.accessibility = {
                focusRing: true,
                highContrast: false,
                reducedMotion: false
            };

            this.init();
        }

        init() {
            this.setupKeyboardNavigation();
            this.setupTouchGestures();
            this.setupAccessibility();
            this.setupContextualHelp();
            this.setupSmartValidation();
            this.setupProgressPersistence();
            this.setupOfflineDetection();
        }

        /**
         * Navigation au clavier
         */
        setupKeyboardNavigation() {
            // Raccourcis clavier
            this.keyboardShortcuts.set('Escape', () => this.handleEscape());
            this.keyboardShortcuts.set('F1', () => this.showHelp());
            this.keyboardShortcuts.set('F5', () => this.refreshPage());
            this.keyboardShortcuts.set('Ctrl+Enter', () => this.submitForm());
            this.keyboardShortcuts.set('Ctrl+U', () => this.triggerUpload());

            document.addEventListener('keydown', (event) => {
                const key = this.getKeyCombo(event);
                const handler = this.keyboardShortcuts.get(key);

                if (handler) {
                    event.preventDefault();
                    handler();
                }

                // Navigation par Tab améliorée
                if (event.key === 'Tab') {
                    this.handleTabNavigation(event);
                }

                // Navigation par flèches
                if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) {
                    this.handleArrowNavigation(event);
                }
            });
        }

        getKeyCombo(event) {
            const parts = [];
            if (event.ctrlKey) parts.push('Ctrl');
            if (event.altKey) parts.push('Alt');
            if (event.shiftKey) parts.push('Shift');
            parts.push(event.key);
            return parts.join('+');
        }

        handleTabNavigation(event) {
            const focusableElements = this.getFocusableElements();
            const currentIndex = focusableElements.indexOf(document.activeElement);

            if (currentIndex === -1) return;

            let nextIndex;
            if (event.shiftKey) {
                nextIndex = currentIndex === 0 ? focusableElements.length - 1 : currentIndex - 1;
            } else {
                nextIndex = currentIndex === focusableElements.length - 1 ? 0 : currentIndex + 1;
            }

            if (focusableElements[nextIndex]) {
                event.preventDefault();
                focusableElements[nextIndex].focus();
                this.scrollIntoViewIfNeeded(focusableElements[nextIndex]);
            }
        }

        handleArrowNavigation(event) {
            const activeElement = document.activeElement;
            const container = activeElement.closest('.document-grid, .stats-row');

            if (container) {
                const items = Array.from(container.querySelectorAll('.document-card, .stat-item'));
                const currentIndex = items.indexOf(activeElement.closest('.document-card, .stat-item'));

                if (currentIndex === -1) return;

                let nextIndex;
                const cols = this.getGridColumns(container);

                switch (event.key) {
                    case 'ArrowUp':
                        nextIndex = currentIndex - cols;
                        break;
                    case 'ArrowDown':
                        nextIndex = currentIndex + cols;
                        break;
                    case 'ArrowLeft':
                        nextIndex = currentIndex - 1;
                        break;
                    case 'ArrowRight':
                        nextIndex = currentIndex + 1;
                        break;
                }

                if (nextIndex >= 0 && nextIndex < items.length && items[nextIndex]) {
                    event.preventDefault();
                    const focusTarget = items[nextIndex].querySelector('button, .upload-zone, a') || items[nextIndex];
                    focusTarget.focus();
                    this.scrollIntoViewIfNeeded(focusTarget);
                }
            }
        }

        getFocusableElements() {
            return Array.from(document.querySelectorAll(
                'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )).filter(el => {
                return el.offsetWidth > 0 && el.offsetHeight > 0 && !el.hidden;
            });
        }

        getGridColumns(container) {
            const computedStyle = window.getComputedStyle(container);
            const gridTemplateColumns = computedStyle.gridTemplateColumns;
            return gridTemplateColumns ? gridTemplateColumns.split(' ').length : 1;
        }

        scrollIntoViewIfNeeded(element) {
            const rect = element.getBoundingClientRect();
            const isVisible = (
                rect.top >= 0 &&
                rect.left >= 0 &&
                rect.bottom <= window.innerHeight &&
                rect.right <= window.innerWidth
            );

            if (!isVisible) {
                element.scrollIntoView({
                    behavior: this.accessibility.reducedMotion ? 'auto' : 'smooth',
                    block: 'center'
                });
            }
        }

        /**
         * Gestes tactiles
         */
        setupTouchGestures() {
            let touchStartX, touchStartY, touchTime;

            document.addEventListener('touchstart', (event) => {
                const touch = event.touches[0];
                touchStartX = touch.clientX;
                touchStartY = touch.clientY;
                touchTime = Date.now();
            }, { passive: true });

            document.addEventListener('touchend', (event) => {
                if (!touchStartX || !touchStartY) return;

                const touch = event.changedTouches[0];
                const touchEndX = touch.clientX;
                const touchEndY = touch.clientY;
                const touchDuration = Date.now() - touchTime;

                const deltaX = touchEndX - touchStartX;
                const deltaY = touchEndY - touchStartY;
                const absDeltaX = Math.abs(deltaX);
                const absDeltaY = Math.abs(deltaY);

                // Swipe detection
                if (absDeltaX > 50 || absDeltaY > 50) {
                    if (absDeltaX > absDeltaY) {
                        // Horizontal swipe
                        if (deltaX > 0) {
                            this.handleSwipeRight(event.target);
                        } else {
                            this.handleSwipeLeft(event.target);
                        }
                    } else {
                        // Vertical swipe
                        if (deltaY > 0) {
                            this.handleSwipeDown(event.target);
                        } else {
                            this.handleSwipeUp(event.target);
                        }
                    }
                }

                // Double tap detection
                if (touchDuration < 300 && absDeltaX < 20 && absDeltaY < 20) {
                    const now = Date.now();
                    const lastTap = event.target._lastTap || 0;

                    if (now - lastTap < 500) {
                        this.handleDoubleTap(event.target);
                    }

                    event.target._lastTap = now;
                }

                touchStartX = touchStartY = null;
            }, { passive: true });
        }

        handleSwipeLeft(target) {
            const card = target.closest('.document-card');
            if (card) {
                this.showDocumentActions(card);
            }
        }

        handleSwipeRight(target) {
            const card = target.closest('.document-card');
            if (card) {
                this.hideDocumentActions(card);
            }
        }

        handleSwipeUp(target) {
            // Scroll vers le haut plus rapidement
            window.scrollBy({ top: -window.innerHeight * 0.5, behavior: 'smooth' });
        }

        handleSwipeDown(target) {
            // Actualiser si on est en haut de page
            if (window.scrollY === 0) {
                this.showPullToRefresh();
            }
        }

        handleDoubleTap(target) {
            const uploadZone = target.closest('.upload-zone');
            if (uploadZone && !uploadZone.classList.contains('uploading')) {
                uploadZone.click();
            }
        }

        /**
         * Accessibilité
         */
        setupAccessibility() {
            // Détection des préférences système
            if (window.matchMedia) {
                // Mode sombre
                const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
                this.handleDarkMode(darkModeQuery.matches);
                darkModeQuery.addListener(e => this.handleDarkMode(e.matches));

                // Contraste élevé
                const highContrastQuery = window.matchMedia('(prefers-contrast: high)');
                this.accessibility.highContrast = highContrastQuery.matches;
                highContrastQuery.addListener(e => {
                    this.accessibility.highContrast = e.matches;
                    this.updateAccessibilityStyles();
                });

                // Mouvement réduit
                const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
                this.accessibility.reducedMotion = reducedMotionQuery.matches;
                reducedMotionQuery.addListener(e => {
                    this.accessibility.reducedMotion = e.matches;
                    this.updateAccessibilityStyles();
                });
            }

            // Annonces ARIA dynamiques
            this.createAriaLiveRegion();

            // Focus management
            this.setupFocusManagement();
        }

        handleDarkMode(isDark) {
            document.body.classList.toggle('dark-mode', isDark);
        }

        createAriaLiveRegion() {
            const liveRegion = document.createElement('div');
            liveRegion.id = 'aria-live-region';
            liveRegion.setAttribute('aria-live', 'polite');
            liveRegion.setAttribute('aria-atomic', 'true');
            liveRegion.style.cssText = 'position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden;';
            document.body.appendChild(liveRegion);
        }

        announce(message, priority = 'polite') {
            const liveRegion = document.getElementById('aria-live-region');
            if (liveRegion) {
                liveRegion.setAttribute('aria-live', priority);
                liveRegion.textContent = message;

                // Clear après 1 seconde pour permettre de nouveaux messages
                setTimeout(() => {
                    liveRegion.textContent = '';
                }, 1000);
            }
        }

        setupFocusManagement() {
            // Focus visible seulement au clavier
            document.addEventListener('mousedown', () => {
                document.body.classList.add('using-mouse');
            });

            document.addEventListener('keydown', (event) => {
                if (event.key === 'Tab') {
                    document.body.classList.remove('using-mouse');
                }
            });

            // Skip links
            this.createSkipLinks();
        }

        createSkipLinks() {
            const skipLinks = document.createElement('div');
            skipLinks.className = 'skip-links';
            skipLinks.innerHTML = `
                <a href="#main-content" class="skip-link">Aller au contenu principal</a>
                <a href="#document-section" class="skip-link">Aller aux documents</a>
                <a href="#help-section" class="skip-link">Aller à l'aide</a>
            `;
            document.body.insertBefore(skipLinks, document.body.firstChild);
        }

        /**
         * Aide contextuelle
         */
        setupContextualHelp() {
            this.helpData = {
                'upload-zone': {
                    title: 'Zone de téléversement',
                    content: 'Glissez votre fichier ici ou cliquez pour sélectionner. Formats acceptés : PDF, JPG, PNG. Taille max : 10MB.',
                    shortcuts: ['Ctrl+U pour ouvrir la sélection de fichier']
                },
                'document-card': {
                    title: 'Carte de document',
                    content: 'Affiche l\'état actuel de votre document. Vert = validé, Orange = expire bientôt, Rouge = expiré.',
                    shortcuts: ['Tab pour naviguer', 'Entrée pour interagir']
                },
                'stats-dashboard': {
                    title: 'Tableau de bord',
                    content: 'Vue d\'ensemble de vos documents. Suivez votre progression en temps réel.',
                    shortcuts: ['F5 pour actualiser']
                }
            };

            // Aide au survol/focus
            document.addEventListener('focusin', (event) => {
                this.showContextualHelp(event.target);
            });

            document.addEventListener('focusout', (event) => {
                this.hideContextualHelp();
            });

            // Bouton d'aide global
            this.createHelpButton();
        }

        showContextualHelp(element) {
            const helpKey = this.getHelpKey(element);
            const helpData = this.helpData[helpKey];

            if (helpData && !this.isHelpVisible()) {
                const helpTooltip = document.createElement('div');
                helpTooltip.id = 'contextual-help';
                helpTooltip.className = 'contextual-help';
                helpTooltip.innerHTML = `
                    <div class="help-header">
                        <h6>${helpData.title}</h6>
                        <button class="help-close" aria-label="Fermer l'aide">&times;</button>
                    </div>
                    <div class="help-content">
                        <p>${helpData.content}</p>
                        ${helpData.shortcuts ? `
                            <div class="help-shortcuts">
                                <strong>Raccourcis :</strong>
                                <ul>
                                    ${helpData.shortcuts.map(shortcut => `<li>${shortcut}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                `;

                document.body.appendChild(helpTooltip);
                this.positionHelp(helpTooltip, element);

                // Événement de fermeture
                helpTooltip.querySelector('.help-close').onclick = () => {
                    this.hideContextualHelp();
                };

                // Annonce ARIA
                this.announce(`Aide disponible : ${helpData.title}`);
            }
        }

        hideContextualHelp() {
            const help = document.getElementById('contextual-help');
            if (help) {
                help.remove();
            }
        }

        getHelpKey(element) {
            if (element.closest('.upload-zone')) return 'upload-zone';
            if (element.closest('.document-card')) return 'document-card';
            if (element.closest('.stats-dashboard')) return 'stats-dashboard';
            return null;
        }

        isHelpVisible() {
            return document.getElementById('contextual-help') !== null;
        }

        positionHelp(helpElement, targetElement) {
            const targetRect = targetElement.getBoundingClientRect();
            const helpRect = helpElement.getBoundingClientRect();

            let left = targetRect.left + (targetRect.width / 2) - (helpRect.width / 2);
            let top = targetRect.bottom + 10;

            // Ajustements pour rester dans la viewport
            if (left < 10) left = 10;
            if (left + helpRect.width > window.innerWidth - 10) {
                left = window.innerWidth - helpRect.width - 10;
            }

            if (top + helpRect.height > window.innerHeight - 10) {
                top = targetRect.top - helpRect.height - 10;
            }

            helpElement.style.left = left + 'px';
            helpElement.style.top = top + 'px';
        }

        createHelpButton() {
            const helpButton = document.createElement('button');
            helpButton.id = 'global-help-button';
            helpButton.className = 'help-button-floating';
            helpButton.innerHTML = '<i class="fa fa-question"></i>';
            helpButton.setAttribute('aria-label', 'Aide générale (F1)');
            helpButton.onclick = () => this.showHelp();

            document.body.appendChild(helpButton);
        }

        /**
         * Validation intelligente
         */
        setupSmartValidation() {
            document.addEventListener('change', (event) => {
                if (event.target.type === 'file') {
                    this.validateFile(event.target);
                }
            });

            // Validation en temps réel des formulaires
            document.addEventListener('input', this.debounce((event) => {
                this.validateInput(event.target);
            }, 300));
        }

        validateFile(input) {
            const file = input.files[0];
            if (!file) return;

            const errors = [];
            const maxSize = 10 * 1024 * 1024; // 10MB
            const allowedTypes = ['.pdf', '.jpg', '.jpeg', '.png'];

            // Validation de la taille
            if (file.size > maxSize) {
                errors.push(`Fichier trop volumineux (${this.formatFileSize(file.size)}). Maximum autorisé : ${this.formatFileSize(maxSize)}.`);
            }

            // Validation du type
            const extension = '.' + file.name.split('.').pop().toLowerCase();
            if (!allowedTypes.includes(extension)) {
                errors.push(`Type de fichier non autorisé (${extension}). Types acceptés : ${allowedTypes.join(', ')}.`);
            }

            // Validation du nom
            if (file.name.length > 100) {
                errors.push('Nom de fichier trop long (maximum 100 caractères).');
            }

            if (!/^[a-zA-Z0-9._-]+$/.test(file.name.replace(/\.[^/.]+$/, ""))) {
                errors.push('Le nom de fichier contient des caractères non autorisés.');
            }

            this.showValidationResults(input, errors);
        }

        validateInput(input) {
            const errors = [];

            if (input.required && !input.value.trim()) {
                errors.push('Ce champ est obligatoire.');
            }

            if (input.type === 'email' && input.value && !this.isValidEmail(input.value)) {
                errors.push('Format d\'email invalide.');
            }

            this.showValidationResults(input, errors);
        }

        showValidationResults(input, errors) {
            // Supprimer les anciens messages
            const existingError = input.parentNode.querySelector('.validation-error');
            if (existingError) {
                existingError.remove();
            }

            input.classList.remove('error', 'success');

            if (errors.length > 0) {
                input.classList.add('error');

                const errorElement = document.createElement('div');
                errorElement.className = 'validation-error';
                errorElement.innerHTML = errors.map(error => `<div class="error-message">${error}</div>`).join('');

                input.parentNode.appendChild(errorElement);

                // Annonce ARIA
                this.announce(`Erreur de validation : ${errors[0]}`, 'assertive');
            } else if (input.value) {
                input.classList.add('success');
            }
        }

        /**
         * Persistance de progression
         */
        setupProgressPersistence() {
            // Sauvegarde automatique des données de formulaire
            const formInputs = document.querySelectorAll('input, textarea, select');
            formInputs.forEach(input => {
                // Restaurer les valeurs sauvegardées
                const savedValue = localStorage.getItem(`form_${input.name || input.id}`);
                if (savedValue && !input.value) {
                    input.value = savedValue;
                }

                // Sauvegarder lors des changements
                input.addEventListener('input', this.debounce(() => {
                    if (input.name || input.id) {
                        localStorage.setItem(`form_${input.name || input.id}`, input.value);
                    }
                }, 1000));
            });

            // Nettoyage à la soumission réussie
            window.addEventListener('beforeunload', () => {
                if (this.isFormSubmittedSuccessfully()) {
                    this.clearSavedFormData();
                }
            });
        }

        clearSavedFormData() {
            const keys = Object.keys(localStorage).filter(key => key.startsWith('form_'));
            keys.forEach(key => localStorage.removeItem(key));
        }

        isFormSubmittedSuccessfully() {
            return document.querySelector('.success-message') !== null;
        }

        /**
         * Détection hors ligne
         */
        setupOfflineDetection() {
            window.addEventListener('online', () => {
                this.handleOnlineStatus(true);
            });

            window.addEventListener('offline', () => {
                this.handleOnlineStatus(false);
            });

            // État initial
            this.handleOnlineStatus(navigator.onLine);
        }

        handleOnlineStatus(isOnline) {
            const indicator = this.getOrCreateOfflineIndicator();

            if (isOnline) {
                indicator.classList.remove('offline');
                indicator.textContent = 'Connexion rétablie';
                this.announce('Connexion Internet rétablie');

                setTimeout(() => {
                    indicator.style.display = 'none';
                }, 3000);
            } else {
                indicator.classList.add('offline');
                indicator.textContent = 'Connexion perdue - Mode hors ligne';
                indicator.style.display = 'block';
                this.announce('Connexion Internet perdue', 'assertive');

                // Désactiver les zones d'upload
                document.querySelectorAll('.upload-zone').forEach(zone => {
                    zone.classList.add('disabled');
                });
            }
        }

        getOrCreateOfflineIndicator() {
            let indicator = document.getElementById('offline-indicator');
            if (!indicator) {
                indicator = document.createElement('div');
                indicator.id = 'offline-indicator';
                indicator.className = 'offline-indicator';
                document.body.appendChild(indicator);
            }
            return indicator;
        }

        /**
         * Méthodes utilitaires
         */
        debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }

        formatFileSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        isValidEmail(email) {
            return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
        }

        /**
         * Gestionnaires d'événements
         */
        handleEscape() {
            // Fermer les modales, aides, etc.
            this.hideContextualHelp();
            document.activeElement.blur();
        }

        showHelp() {
            const helpModal = document.createElement('div');
            helpModal.id = 'help-modal';
            helpModal.className = 'help-modal';
            helpModal.innerHTML = `
                <div class="help-modal-content">
                    <div class="help-modal-header">
                        <h3>Aide - Portail de documents</h3>
                        <button class="help-modal-close" aria-label="Fermer">&times;</button>
                    </div>
                    <div class="help-modal-body">
                        <div class="help-section">
                            <h4>Raccourcis clavier</h4>
                            <ul>
                                <li><kbd>F1</kbd> - Afficher cette aide</li>
                                <li><kbd>Ctrl+U</kbd> - Ouvrir la sélection de fichier</li>
                                <li><kbd>Ctrl+Enter</kbd> - Soumettre le formulaire</li>
                                <li><kbd>Tab</kbd> / <kbd>Shift+Tab</kbd> - Navigation</li>
                                <li><kbd>Échap</kbd> - Fermer les boîtes de dialogue</li>
                            </ul>
                        </div>
                        <div class="help-section">
                            <h4>Gestes tactiles</h4>
                            <ul>
                                <li>Glisser vers la gauche - Afficher les actions</li>
                                <li>Glisser vers la droite - Masquer les actions</li>
                                <li>Double-tap - Déclencher l'upload</li>
                                <li>Glisser vers le bas (en haut) - Actualiser</li>
                            </ul>
                        </div>
                        <div class="help-section">
                            <h4>Types de fichiers acceptés</h4>
                            <p>PDF, JPG, JPEG, PNG - Maximum 10MB par fichier</p>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(helpModal);

            // Focus sur la modal
            helpModal.querySelector('.help-modal-close').focus();

            // Événements de fermeture
            helpModal.querySelector('.help-modal-close').onclick = () => {
                this.closeHelpModal();
            };

            helpModal.addEventListener('click', (event) => {
                if (event.target === helpModal) {
                    this.closeHelpModal();
                }
            });
        }

        closeHelpModal() {
            const modal = document.getElementById('help-modal');
            if (modal) {
                modal.remove();
            }
        }

        refreshPage() {
            if (confirm('Actualiser la page ? Les données non sauvegardées seront perdues.')) {
                window.location.reload();
            }
        }

        submitForm() {
            const form = document.querySelector('form');
            if (form) {
                form.submit();
            }
        }

        triggerUpload() {
            const uploadZone = document.querySelector('.upload-zone:not(.uploading)');
            if (uploadZone) {
                uploadZone.click();
            }
        }

        showDocumentActions(card) {
            const existingActions = card.querySelector('.document-actions');
            if (existingActions) return;

            const actions = document.createElement('div');
            actions.className = 'document-actions';
            actions.innerHTML = `
                <button class="action-btn view-btn" title="Voir le document">
                    <i class="fa fa-eye"></i>
                </button>
                <button class="action-btn replace-btn" title="Remplacer le document">
                    <i class="fa fa-refresh"></i>
                </button>
                <button class="action-btn info-btn" title="Informations">
                    <i class="fa fa-info"></i>
                </button>
            `;

            card.appendChild(actions);

            // Animation d'apparition
            setTimeout(() => actions.classList.add('show'), 10);
        }

        hideDocumentActions(card) {
            const actions = card.querySelector('.document-actions');
            if (actions) {
                actions.classList.remove('show');
                setTimeout(() => actions.remove(), 300);
            }
        }

        showPullToRefresh() {
            const indicator = document.createElement('div');
            indicator.className = 'pull-to-refresh';
            indicator.innerHTML = '<i class="fa fa-refresh fa-spin"></i> Actualisation...';
            document.body.appendChild(indicator);

            setTimeout(() => {
                indicator.remove();
                window.location.reload();
            }, 1500);
        }

        updateAccessibilityStyles() {
            document.body.classList.toggle('high-contrast', this.accessibility.highContrast);
            document.body.classList.toggle('reduced-motion', this.accessibility.reducedMotion);
        }
    }

    // Initialisation au chargement
    document.addEventListener('DOMContentLoaded', () => {
        window.portalInteractionManager = new PortalInteractionManager();
    });

})();
