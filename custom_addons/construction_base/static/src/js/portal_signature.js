/**
 * JavaScript pour le portail de signature électronique
 * Gestion des interactions et validations
 */

(function() {
    'use strict';

    // Configuration globale
    const CONFIG = {
        MIN_INITIALS_LENGTH: 2,
        MAX_INITIALS_LENGTH: 10,
        CANVAS_WIDTH: 400,
        CANVAS_HEIGHT: 200
    };

    // Classe principale pour la gestion de la signature
    class SignaturePortal {
        constructor() {
            this.initializeEventListeners();
            this.setupCanvas();
        }

        /**
         * Initialise les écouteurs d'événements
         */
        initializeEventListeners() {
            // Gestion des initiales
            const initialsInput = document.getElementById('initials');
            if (initialsInput) {
                initialsInput.addEventListener('input', this.handleInitialsInput.bind(this));
                initialsInput.addEventListener('keypress', this.handleInitialsKeypress.bind(this));
            }

            // Gestion du canvas de signature
            const canvas = document.getElementById('signature-canvas');
            if (canvas) {
                this.setupCanvasEventListeners(canvas);
            }

            // Gestion des formulaires
            const initialsForm = document.querySelector('.initials-form');
            if (initialsForm) {
                initialsForm.addEventListener('submit', this.handleInitialsSubmit.bind(this));
            }

            const finalSignatureForm = document.querySelector('.final-signature-form');
            if (finalSignatureForm) {
                finalSignatureForm.addEventListener('submit', this.handleFinalSignatureSubmit.bind(this));
            }

            // Gestion des miniatures de pages
            this.setupPageThumbnails();
        }

        /**
         * Gère la saisie des initiales
         */
        handleInitialsInput(event) {
            const input = event.target;
            const value = input.value.toUpperCase();
            const preview = document.getElementById('initials-preview');
            
            // Limiter la longueur
            if (value.length > CONFIG.MAX_INITIALS_LENGTH) {
                input.value = value.substring(0, CONFIG.MAX_INITIALS_LENGTH);
            }
            
            // Mettre à jour l'aperçu
            if (preview) {
                preview.textContent = value || '-';
                preview.style.color = value.length >= CONFIG.MIN_INITIALS_LENGTH ? '#28a745' : '#dc3545';
            }

            // Validation en temps réel
            this.validateInitials(value);
        }

        /**
         * Gère les touches pressées dans le champ initiales
         */
        handleInitialsKeypress(event) {
            // Autoriser seulement les lettres et espaces
            const allowedChars = /[A-Za-z\s]/;
            if (!allowedChars.test(event.key)) {
                event.preventDefault();
            }
        }

        /**
         * Valide les initiales
         */
        validateInitials(initials) {
            const submitButton = document.querySelector('.initials-form button[type="submit"]');
            const isValid = initials.length >= CONFIG.MIN_INITIALS_LENGTH;
            
            if (submitButton) {
                submitButton.disabled = !isValid;
                submitButton.classList.toggle('btn-primary', isValid);
                submitButton.classList.toggle('btn-secondary', !isValid);
            }

            return isValid;
        }

        /**
         * Gère la soumission du formulaire d'initiales
         */
        handleInitialsSubmit(event) {
            const input = document.getElementById('initials');
            const initials = input.value.trim();

            if (!this.validateInitials(initials)) {
                event.preventDefault();
                this.showError('Veuillez saisir vos initiales (au moins 2 caractères).');
                return false;
            }

            // Ajouter un indicateur de chargement
            this.showLoading(event.target);
        }

        /**
         * Configure le canvas de signature
         */
        setupCanvas() {
            const canvas = document.getElementById('signature-canvas');
            if (!canvas) return;

            const ctx = canvas.getContext('2d');
            
            // Configuration du canvas
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 2;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';

            // Variables pour le dessin
            let isDrawing = false;
            let hasSignature = false;
            let lastX = 0;
            let lastY = 0;

            // Fonctions de dessin
            const startDrawing = (e) => {
                isDrawing = true;
                hasSignature = true;
                const pos = this.getCanvasPosition(e, canvas);
                lastX = pos.x;
                lastY = pos.y;
                this.updateSubmitButton();
            };

            const draw = (e) => {
                if (!isDrawing) return;
                
                e.preventDefault();
                const pos = this.getCanvasPosition(e, canvas);
                
                ctx.beginPath();
                ctx.moveTo(lastX, lastY);
                ctx.lineTo(pos.x, pos.y);
                ctx.stroke();
                
                lastX = pos.x;
                lastY = pos.y;
            };

            const stopDrawing = () => {
                isDrawing = false;
            };

            // Écouteurs d'événements pour le canvas
            canvas.addEventListener('mousedown', startDrawing);
            canvas.addEventListener('mousemove', draw);
            canvas.addEventListener('mouseup', stopDrawing);
            canvas.addEventListener('mouseout', stopDrawing);

            // Support tactile
            canvas.addEventListener('touchstart', (e) => {
                e.preventDefault();
                startDrawing(e.touches[0]);
            });
            canvas.addEventListener('touchmove', (e) => {
                e.preventDefault();
                draw(e.touches[0]);
            });
            canvas.addEventListener('touchend', stopDrawing);

            // Bouton d'effacement
            const clearButton = document.getElementById('clear-signature');
            if (clearButton) {
                clearButton.addEventListener('click', () => {
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    hasSignature = false;
                    this.updateSubmitButton();
                });
            }
        }

        /**
         * Obtient la position relative dans le canvas
         */
        getCanvasPosition(e, canvas) {
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            
            return {
                x: (e.clientX - rect.left) * scaleX,
                y: (e.clientY - rect.top) * scaleY
            };
        }

        /**
         * Met à jour le bouton de soumission
         */
        updateSubmitButton() {
            const submitBtn = document.getElementById('submit-signature');
            if (submitBtn) {
                const canvas = document.getElementById('signature-canvas');
                const ctx = canvas.getContext('2d');
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const hasSignature = imageData.data.some(pixel => pixel !== 0);
                
                submitBtn.disabled = !hasSignature;
            }
        }

        /**
         * Gère la soumission de la signature finale
         */
        handleFinalSignatureSubmit(event) {
            const canvas = document.getElementById('signature-canvas');
            const ctx = canvas.getContext('2d');
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const hasSignature = imageData.data.some(pixel => pixel !== 0);

            if (!hasSignature) {
                event.preventDefault();
                this.showError('Veuillez apposer votre signature avant de continuer.');
                return false;
            }

            // Convertir le canvas en base64
            const signatureData = canvas.toDataURL();
            const hiddenInput = document.getElementById('signature-data');
            if (hiddenInput) {
                hiddenInput.value = signatureData;
            }

            // Ajouter un indicateur de chargement
            this.showLoading(event.target);
        }

        /**
         * Configure les miniatures de pages
         */
        setupPageThumbnails() {
            const thumbnails = document.querySelectorAll('.page-thumbnail');
            thumbnails.forEach(thumbnail => {
                thumbnail.addEventListener('click', () => {
                    const pageNumber = thumbnail.querySelector('.thumbnail-number').textContent;
                    const currentUrl = new URL(window.location);
                    currentUrl.searchParams.set('page_number', pageNumber);
                    window.location.href = currentUrl.toString();
                });
            });
        }

        /**
         * Affiche un message d'erreur
         */
        showError(message) {
            // Supprimer les messages d'erreur existants
            const existingError = document.querySelector('.error-message');
            if (existingError) {
                existingError.remove();
            }

            // Créer le message d'erreur
            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger error-message';
            errorDiv.innerHTML = `
                <i class="fa fa-exclamation-triangle"></i>
                <strong>Erreur :</strong> ${message}
            `;

            // Insérer le message
            const container = document.querySelector('.signature-zone') || document.querySelector('.final-signature-zone');
            if (container) {
                container.insertBefore(errorDiv, container.firstChild);
            }

            // Auto-suppression après 5 secondes
            setTimeout(() => {
                if (errorDiv.parentNode) {
                    errorDiv.remove();
                }
            }, 5000);
        }

        /**
         * Affiche un indicateur de chargement
         */
        showLoading(form) {
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                const originalText = submitButton.innerHTML;
                submitButton.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Traitement...';
                submitButton.disabled = true;
                
                // Restaurer après un délai (en cas d'erreur)
                setTimeout(() => {
                    submitButton.innerHTML = originalText;
                    submitButton.disabled = false;
                }, 10000);
            }
        }

        /**
         * Sauvegarde les initiales via AJAX
         */
        saveInitials(pageNumber, initials) {
            return fetch(`/portal/contract/${contractId}/save_initials`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    page_number: pageNumber,
                    initials_data: initials,
                    access_token: accessToken
                })
            })
            .then(response => response.json())
            .catch(error => {
                console.error('Erreur sauvegarde initiales:', error);
                throw error;
            });
        }
    }

    // Initialisation quand le DOM est prêt
    document.addEventListener('DOMContentLoaded', function() {
        new SignaturePortal();
    });

    // Fonctions utilitaires globales
    window.SignaturePortal = {
        // Validation des initiales
        validateInitials: function(initials) {
            return initials && initials.length >= CONFIG.MIN_INITIALS_LENGTH;
        },

        // Formatage des initiales
        formatInitials: function(initials) {
            return initials.toUpperCase().trim();
        },

        // Vérification de la signature
        hasSignature: function(canvas) {
            if (!canvas) return false;
            const ctx = canvas.getContext('2d');
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            return imageData.data.some(pixel => pixel !== 0);
        }
    };

})();
