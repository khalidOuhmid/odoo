/** @odoo-module **/

/**
 * Portal Upload JavaScript
 * Gestion de l'upload côté portail public
 */

(function() {
    'use strict';

    // Configuration globale
    const CONFIG = {
        maxFileSize: 10 * 1024 * 1024, // 10MB
        allowedTypes: ['.pdf', '.jpg', '.jpeg', '.png'],
        uploadUrl: '/documents/portal/upload',
        progressUpdateInterval: 100,
        autoRetryCount: 3,
        autoRetryDelay: 1000
    };

    // État global de l'application
    const AppState = {
        uploads: new Map(),
        totalProgress: 0,
        isUploading: false,
        config: { ...CONFIG }
    };

    /**
     * Utilitaires
     */
    const Utils = {
        /**
         * Formatage de la taille de fichier
         */
        formatFileSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        },

        /**
         * Génération d'un ID unique
         */
        generateId() {
            return 'upload_' + Math.random().toString(36).substr(2, 9);
        },

        /**
         * Validation d'un fichier
         */
        validateFile(file) {
            const errors = [];

            // Vérification de la taille
            if (file.size > AppState.config.maxFileSize) {
                errors.push(`Fichier trop volumineux (max: ${Utils.formatFileSize(AppState.config.maxFileSize)})`);
            }

            // Vérification du type
            const extension = '.' + file.name.split('.').pop().toLowerCase();
            if (!AppState.config.allowedTypes.includes(extension)) {
                errors.push(`Type de fichier non autorisé (autorisés: ${AppState.config.allowedTypes.join(', ')})`);
            }

            return {
                valid: errors.length === 0,
                errors: errors
            };
        },

        /**
         * Débounce une fonction
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
        },

        /**
         * Animation fluide
         */
        animateValue(element, start, end, duration, callback) {
            let startTimestamp = null;
            const step = (timestamp) => {
                if (!startTimestamp) startTimestamp = timestamp;
                const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                const value = progress * (end - start) + start;
                if (callback) callback(value);
                if (progress < 1) {
                    window.requestAnimationFrame(step);
                }
            };
            window.requestAnimationFrame(step);
        }
    };

    /**
     * Gestionnaire de notifications
     */
    const NotificationManager = {
        show(message, type = 'info', duration = 5000) {
            const notification = document.createElement('div');
            notification.className = `notification notification-${type}`;
            notification.innerHTML = `
                <div class="notification-content">
                    <i class="fa fa-${this.getIcon(type)}"></i>
                    <span>${message}</span>
                    <button class="notification-close">&times;</button>
                </div>
            `;

            const container = this.getContainer();
            container.appendChild(notification);

            // Animation d'entrée
            setTimeout(() => notification.classList.add('show'), 10);

            // Auto-suppression
            if (duration > 0) {
                setTimeout(() => this.hide(notification), duration);
            }

            // Bouton de fermeture
            notification.querySelector('.notification-close').onclick = () => {
                this.hide(notification);
            };

            return notification;
        },

        hide(notification) {
            notification.classList.remove('show');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        },

        getContainer() {
            let container = document.getElementById('notification-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'notification-container';
                container.className = 'notification-container';
                document.body.appendChild(container);
            }
            return container;
        },

        getIcon(type) {
            const icons = {
                success: 'check-circle',
                error: 'exclamation-circle',
                warning: 'exclamation-triangle',
                info: 'info-circle'
            };
            return icons[type] || 'info-circle';
        }
    };

    /**
     * Gestionnaire d'upload
     */
    class UploadManager {
        constructor(documentTypeId, uploadUrl = CONFIG.uploadUrl) {
            this.documentTypeId = documentTypeId;
            this.uploadUrl = uploadUrl;
            this.retryCount = 0;
        }

        /**
         * Upload d'un fichier
         */
        async uploadFile(file, onProgress) {
            const uploadId = Utils.generateId();

            // Validation
            const validation = Utils.validateFile(file);
            if (!validation.valid) {
                throw new Error(validation.errors.join(', '));
            }

            AppState.uploads.set(uploadId, {
                file: file,
                progress: 0,
                status: 'uploading',
                uploadId: uploadId
            });

            return new Promise((resolve, reject) => {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('document_type_id', this.documentTypeId);
                formData.append('upload_id', uploadId);

                // Token CSRF
                const csrfToken = document.querySelector('meta[name="csrf-token"]');
                if (csrfToken) {
                    formData.append('csrf_token', csrfToken.getAttribute('content'));
                }

                const xhr = new XMLHttpRequest();

                // Gestion de la progression
                xhr.upload.onprogress = (event) => {
                    if (event.lengthComputable) {
                        const progress = Math.round((event.loaded / event.total) * 100);
                        const uploadData = AppState.uploads.get(uploadId);
                        if (uploadData) {
                            uploadData.progress = progress;
                            AppState.uploads.set(uploadId, uploadData);
                        }
                        if (onProgress) onProgress(progress);
                    }
                };

                // Gestion de la réponse
                xhr.onload = () => {
                    AppState.uploads.delete(uploadId);

                    if (xhr.status === 200) {
                        try {
                            const response = JSON.parse(xhr.responseText);
                            if (response.success) {
                                resolve(response);
                            } else {
                                reject(new Error(response.error || 'Erreur inconnue'));
                            }
                        } catch (e) {
                            reject(new Error('Réponse invalide du serveur'));
                        }
                    } else {
                        reject(new Error(`Erreur HTTP: ${xhr.status}`));
                    }
                };

                // Gestion des erreurs
                xhr.onerror = () => {
                    AppState.uploads.delete(uploadId);
                    reject(new Error('Erreur de connexion'));
                };

                xhr.ontimeout = () => {
                    AppState.uploads.delete(uploadId);
                    reject(new Error('Timeout de connexion'));
                };

                // Configuration et envoi
                xhr.open('POST', this.uploadUrl, true);
                xhr.timeout = 300000; // 5 minutes
                xhr.send(formData);
            });
        }

        /**
         * Upload avec retry automatique
         */
        async uploadWithRetry(file, onProgress, maxRetries = CONFIG.autoRetryCount) {
            let lastError;

            for (let attempt = 0; attempt <= maxRetries; attempt++) {
                try {
                    return await this.uploadFile(file, onProgress);
                } catch (error) {
                    lastError = error;

                    if (attempt < maxRetries) {
                        // Attendre avant le retry
                        await new Promise(resolve =>
                            setTimeout(resolve, CONFIG.autoRetryDelay * (attempt + 1))
                        );

                        NotificationManager.show(
                            `Tentative ${attempt + 2}/${maxRetries + 1}...`,
                            'warning',
                            2000
                        );
                    }
                }
            }

            throw lastError;
        }
    }

    /**
     * Gestionnaire de zone de drop
     */
    class DropZoneManager {
        constructor(element, documentTypeId) {
            this.element = element;
            this.documentTypeId = documentTypeId;
            this.uploadManager = new UploadManager(documentTypeId);
            this.fileInput = null;

            this.init();
        }

        init() {
            this.setupEventListeners();
            this.createFileInput();
            this.updateUI();
        }

        setupEventListeners() {
            // Events drag & drop
            this.element.addEventListener('dragover', this.onDragOver.bind(this));
            this.element.addEventListener('dragenter', this.onDragEnter.bind(this));
            this.element.addEventListener('dragleave', this.onDragLeave.bind(this));
            this.element.addEventListener('drop', this.onDrop.bind(this));

            // Event clic
            this.element.addEventListener('click', this.onClick.bind(this));
        }

        createFileInput() {
            this.fileInput = document.createElement('input');
            this.fileInput.type = 'file';
            this.fileInput.accept = AppState.config.allowedTypes.join(',');
            this.fileInput.style.display = 'none';
            this.fileInput.onchange = this.onFileSelect.bind(this);
            document.body.appendChild(this.fileInput);
        }

        onDragOver(event) {
            event.preventDefault();
            event.stopPropagation();
            this.element.classList.add('dragover');
        }

        onDragEnter(event) {
            event.preventDefault();
            event.stopPropagation();
            this.element.classList.add('dragover');
        }

        onDragLeave(event) {
            event.preventDefault();
            event.stopPropagation();

            // Vérifier si on quitte vraiment la zone
            const rect = this.element.getBoundingClientRect();
            const x = event.clientX;
            const y = event.clientY;

            if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
                this.element.classList.remove('dragover');
            }
        }

        onDrop(event) {
            event.preventDefault();
            event.stopPropagation();
            this.element.classList.remove('dragover');

            const files = Array.from(event.dataTransfer.files);
            this.handleFiles(files);
        }

        onClick(event) {
            if (!AppState.isUploading) {
                this.fileInput.click();
            }
        }

        onFileSelect(event) {
            const files = Array.from(event.target.files);
            this.handleFiles(files);
            event.target.value = ''; // Reset pour permettre le même fichier
        }

        async handleFiles(files) {
            if (files.length === 0) return;

            // On ne prend que le premier fichier pour simplicité
            const file = files[0];

            // Afficher les informations du fichier
            this.showFileInfo(file);

            try {
                AppState.isUploading = true;
                this.updateUI();

                const result = await this.uploadManager.uploadWithRetry(
                    file,
                    this.onUploadProgress.bind(this)
                );

                // Succès
                NotificationManager.show(
                    'Document téléversé avec succès !',
                    'success'
                );

                // Recharger la page après un délai
                setTimeout(() => {
                    window.location.reload();
                }, 2000);

            } catch (error) {
                console.error('Erreur upload:', error);
                NotificationManager.show(
                    `Erreur: ${error.message}`,
                    'error'
                );
                this.hideFileInfo();
            } finally {
                AppState.isUploading = false;
                this.updateUI();
            }
        }

        onUploadProgress(progress) {
            const progressBar = this.element.querySelector('.upload-progress-bar');
            const progressText = this.element.querySelector('.upload-progress-text');

            if (progressBar) {
                progressBar.style.width = progress + '%';
            }

            if (progressText) {
                progressText.textContent = progress + '%';
            }
        }

        showFileInfo(file) {
            const existingInfo = this.element.querySelector('.file-info');
            if (existingInfo) {
                existingInfo.remove();
            }

            const fileInfo = document.createElement('div');
            fileInfo.className = 'file-info animate-slide-up';
            fileInfo.innerHTML = `
                <div class="file-selected">
                    <i class="fa fa-file-${this.getFileIcon(file)}"></i>
                    <div class="filename">${file.name}</div>
                    <div class="file-size">${Utils.formatFileSize(file.size)}</div>
                </div>
                <div class="upload-progress">
                    <div class="upload-progress-bar" style="width: 0%"></div>
                    <div class="upload-progress-text">0%</div>
                </div>
            `;

            this.element.appendChild(fileInfo);
        }

        hideFileInfo() {
            const fileInfo = this.element.querySelector('.file-info');
            if (fileInfo) {
                fileInfo.classList.add('animate-fade-out');
                setTimeout(() => fileInfo.remove(), 300);
            }
        }

        getFileIcon(file) {
            const type = file.type.toLowerCase();
            if (type.includes('pdf')) return 'pdf-o';
            if (type.includes('image')) return 'image-o';
            return 'file-o';
        }

        updateUI() {
            const uploadContent = this.element.querySelector('.upload-content');
            if (uploadContent) {
                if (AppState.isUploading) {
                    uploadContent.innerHTML = `
                        <div class="loading-spinner"></div>
                        <div class="upload-text">
                            <strong>Téléversement en cours...</strong><br>
                            <small>Veuillez patienter</small>
                        </div>
                    `;
                    this.element.classList.add('uploading');
                } else {
                    this.element.classList.remove('uploading');
                }
            }
        }
    }

    /**
     * Initialisation au chargement de la page
     */
    document.addEventListener('DOMContentLoaded', function() {
        // Chargement de la configuration
        loadConfiguration();

        // Initialisation des zones de drop
        initializeDropZones();

        // Initialisation des fonctionnalités générales
        initializeGeneralFeatures();

        // Gestion du token d'expiration
        initializeTokenExpiration();
    });

    /**
     * Chargement de la configuration depuis les données de la page
     */
    function loadConfiguration() {
        const configElement = document.getElementById('upload-config');
        if (configElement) {
            try {
                const config = JSON.parse(configElement.textContent);
                AppState.config = { ...AppState.config, ...config };
            } catch (e) {
                console.warn('Erreur chargement configuration:', e);
            }
        }
    }

    /**
     * Initialisation des zones de drop
     */
    function initializeDropZones() {
        const dropZones = document.querySelectorAll('.upload-zone');
        dropZones.forEach(zone => {
            const documentTypeId = zone.getAttribute('data-document-type-id');
            if (documentTypeId) {
                new DropZoneManager(zone, documentTypeId);
            }
        });
    }

    /**
     * Initialisation des fonctionnalités générales
     */
    function initializeGeneralFeatures() {
        // Animation des statistiques
        animateStats();

        // Gestion des tooltips
        initializeTooltips();

        // Gestion du scroll fluide
        initializeSmoothScroll();

        // Optimisations de performance
        initializePerformanceOptimizations();
    }

    /**
     * Animation des statistiques
     */
    function animateStats() {
        const statValues = document.querySelectorAll('.stat-value');
        statValues.forEach(stat => {
            const finalValue = parseInt(stat.textContent) || 0;
            const suffix = stat.textContent.replace(/[0-9]/g, '');

            Utils.animateValue(stat, 0, finalValue, 1500, (value) => {
                stat.textContent = Math.round(value) + suffix;
            });
        });
    }

    /**
     * Initialisation des tooltips
     */
    function initializeTooltips() {
        const tooltipElements = document.querySelectorAll('[data-tooltip]');
        tooltipElements.forEach(element => {
            element.addEventListener('mouseenter', showTooltip);
            element.addEventListener('mouseleave', hideTooltip);
        });
    }

    function showTooltip(event) {
        const text = event.target.getAttribute('data-tooltip');
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
        tooltip.textContent = text;
        document.body.appendChild(tooltip);

        const rect = event.target.getBoundingClientRect();
        tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
        tooltip.style.top = rect.top - tooltip.offsetHeight - 10 + 'px';

        setTimeout(() => tooltip.classList.add('show'), 10);

        event.target._tooltip = tooltip;
    }

    function hideTooltip(event) {
        const tooltip = event.target._tooltip;
        if (tooltip) {
            tooltip.classList.remove('show');
            setTimeout(() => {
                if (tooltip.parentNode) {
                    tooltip.parentNode.removeChild(tooltip);
                }
            }, 200);
            delete event.target._tooltip;
        }
    }

    /**
     * Scroll fluide
     */
    function initializeSmoothScroll() {
        const links = document.querySelectorAll('a[href^="#"]');
        links.forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }

    /**
     * Optimisations de performance
     */
    function initializePerformanceOptimizations() {
        // Lazy loading des images
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        observer.unobserve(img);
                    }
                });
            });

            document.querySelectorAll('img[data-src]').forEach(img => {
                imageObserver.observe(img);
            });
        }
    }

    /**
     * Gestion de l'expiration du token
     */
    function initializeTokenExpiration() {
        const expiryElement = document.querySelector('[data-token-expiry]');
        if (expiryElement) {
            const expiryTime = new Date(expiryElement.getAttribute('data-token-expiry'));

            const updateCountdown = () => {
                const now = new Date();
                const timeLeft = expiryTime - now;

                if (timeLeft <= 0) {
                    // Token expiré
                    NotificationManager.show(
                        'Votre lien d\'accès a expiré. Veuillez contacter votre interlocuteur.',
                        'error',
                        0
                    );

                    // Désactiver les zones d'upload
                    document.querySelectorAll('.upload-zone').forEach(zone => {
                        zone.classList.add('disabled');
                        zone.onclick = null;
                    });

                    return;
                }

                // Mise à jour du countdown
                const days = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
                const hours = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));

                let countdownText = '';
                if (days > 0) countdownText += `${days}j `;
                if (hours > 0) countdownText += `${hours}h `;
                countdownText += `${minutes}min`;

                expiryElement.textContent = `Expire dans ${countdownText}`;

                // Alerte si moins de 2 heures
                if (timeLeft < 2 * 60 * 60 * 1000 && !expiryElement.classList.contains('urgent')) {
                    expiryElement.classList.add('urgent');
                    NotificationManager.show(
                        'Attention : votre lien d\'accès expire dans moins de 2 heures !',
                        'warning'
                    );
                }
            };

            // Mise à jour immédiate puis toutes les minutes
            updateCountdown();
            setInterval(updateCountdown, 60000);
        }
    }

    // Exposition des fonctionnalités globales
    window.PortalUpload = {
        NotificationManager,
        UploadManager,
        DropZoneManager,
        Utils,
        AppState
    };

})();
