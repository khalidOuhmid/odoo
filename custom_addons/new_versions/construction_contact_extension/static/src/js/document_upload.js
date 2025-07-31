/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Document Upload Component
 * Gère l'upload de documents avec drag & drop, validation et preview
 */
export class DocumentUpload extends Component {
    static template = "construction_contact_extension.DocumentUploadTemplate";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.state = useState({
            isDragOver: false,
            isUploading: false,
            uploadProgress: 0,
            selectedFiles: [],
            validationErrors: [],
            maxFileSize: 10 * 1024 * 1024, // 10MB
            allowedTypes: ['.pdf', '.jpg', '.jpeg', '.png']
        });

        onMounted(() => {
            this._setupDragAndDrop();
            this._loadConfiguration();
        });

        onWillUnmount(() => {
            this._cleanupDragAndDrop();
        });
    }

    /**
     * Configuration du drag & drop
     */
    _setupDragAndDrop() {
        const dropZone = this.el.querySelector('.o_document_upload_zone');
        if (!dropZone) return;

        // Événements drag & drop
        dropZone.addEventListener('dragover', this._onDragOver.bind(this));
        dropZone.addEventListener('dragenter', this._onDragEnter.bind(this));
        dropZone.addEventListener('dragleave', this._onDragLeave.bind(this));
        dropZone.addEventListener('drop', this._onDrop.bind(this));

        // Événement de clic pour sélection de fichier
        dropZone.addEventListener('click', this._onClickUpload.bind(this));
    }

    /**
     * Nettoyage des événements
     */
    _cleanupDragAndDrop() {
        const dropZone = this.el.querySelector('.o_document_upload_zone');
        if (!dropZone) return;

        dropZone.removeEventListener('dragover', this._onDragOver.bind(this));
        dropZone.removeEventListener('dragenter', this._onDragEnter.bind(this));
        dropZone.removeEventListener('dragleave', this._onDragLeave.bind(this));
        dropZone.removeEventListener('drop', this._onDrop.bind(this));
        dropZone.removeEventListener('click', this._onClickUpload.bind(this));
    }

    /**
     * Chargement de la configuration
     */
    async _loadConfiguration() {
        try {
            const config = await this.orm.call(
                "ir.config_parameter",
                "get_param",
                ["construction_contact_extension.document_max_file_size_mb", "10"]
            );
            this.state.maxFileSize = parseFloat(config) * 1024 * 1024;

            const allowedTypes = await this.orm.call(
                "ir.config_parameter",
                "get_param",
                ["construction_contact_extension.document_allowed_file_types", ".pdf,.jpg,.jpeg,.png"]
            );
            this.state.allowedTypes = allowedTypes.split(',').map(type => type.trim());
        } catch (error) {
            console.error("Erreur chargement configuration:", error);
        }
    }

    /**
     * Gestion du drag over
     */
    _onDragOver(event) {
        event.preventDefault();
        event.stopPropagation();
        this.state.isDragOver = true;
    }

    /**
     * Gestion du drag enter
     */
    _onDragEnter(event) {
        event.preventDefault();
        event.stopPropagation();
        this.state.isDragOver = true;
    }

    /**
     * Gestion du drag leave
     */
    _onDragLeave(event) {
        event.preventDefault();
        event.stopPropagation();

        // Vérifier si on quitte vraiment la zone
        const rect = event.currentTarget.getBoundingClientRect();
        const x = event.clientX;
        const y = event.clientY;

        if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
            this.state.isDragOver = false;
        }
    }

    /**
     * Gestion du drop
     */
    _onDrop(event) {
        event.preventDefault();
        event.stopPropagation();
        this.state.isDragOver = false;

        const files = Array.from(event.dataTransfer.files);
        this._handleFiles(files);
    }

    /**
     * Gestion du clic pour sélection
     */
    _onClickUpload() {
        const input = document.createElement('input');
        input.type = 'file';
        input.multiple = true;
        input.accept = this.state.allowedTypes.join(',');

        input.onchange = (event) => {
            const files = Array.from(event.target.files);
            this._handleFiles(files);
        };

        input.click();
    }

    /**
     * Traitement des fichiers sélectionnés
     */
    async _handleFiles(files) {
        if (files.length === 0) return;

        // Validation des fichiers
        const validFiles = [];
        const errors = [];

        for (const file of files) {
            const validation = this._validateFile(file);
            if (validation.valid) {
                validFiles.push(file);
            } else {
                errors.push(...validation.errors);
            }
        }

        if (errors.length > 0) {
            this.state.validationErrors = errors;
            this.notification.add(
                _t("Certains fichiers ne respectent pas les contraintes"),
                { type: "warning" }
            );
            return;
        }

        this.state.selectedFiles = validFiles;
        this.state.validationErrors = [];

        // Upload automatique si configuré
        if (this.props.autoUpload !== false) {
            await this._uploadFiles(validFiles);
        }
    }

    /**
     * Validation d'un fichier
     */
    _validateFile(file) {
        const errors = [];

        // Vérification de la taille
        if (file.size > this.state.maxFileSize) {
            errors.push(_t(`${file.name}: Fichier trop volumineux (max: ${this.state.maxFileSize / 1024 / 1024}MB)`));
        }

        // Vérification du type
        const extension = '.' + file.name.split('.').pop().toLowerCase();
        if (!this.state.allowedTypes.includes(extension)) {
            errors.push(_t(`${file.name}: Type de fichier non autorisé`));
        }

        return {
            valid: errors.length === 0,
            errors: errors
        };
    }

    /**
     * Upload des fichiers
     */
    async _uploadFiles(files) {
        this.state.isUploading = true;
        this.state.uploadProgress = 0;

        try {
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                await this._uploadSingleFile(file, i + 1, files.length);
            }

            this.notification.add(
                _t("Documents téléversés avec succès"),
                { type: "success" }
            );

            // Callback de succès
            if (this.props.onUploadSuccess) {
                this.props.onUploadSuccess(files);
            }

        } catch (error) {
            console.error("Erreur upload:", error);
            this.notification.add(
                _t("Erreur lors du téléversement"),
                { type: "danger" }
            );
        } finally {
            this.state.isUploading = false;
            this.state.uploadProgress = 0;
            this.state.selectedFiles = [];
        }
    }

    /**
     * Upload d'un fichier unique
     */
    async _uploadSingleFile(file, index, total) {
        return new Promise((resolve, reject) => {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('document_type_id', this.props.documentTypeId || '');
            formData.append('partner_id', this.props.partnerId || '');

            const xhr = new XMLHttpRequest();

            // Gestion de la progression
            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable) {
                    const fileProgress = (event.loaded / event.total) * 100;
                    const totalProgress = ((index - 1) / total) * 100 + (fileProgress / total);
                    this.state.uploadProgress = Math.round(totalProgress);
                }
            };

            // Gestion de la réponse
            xhr.onload = () => {
                if (xhr.status === 200) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        if (response.success) {
                            resolve(response);
                        } else {
                            reject(new Error(response.error || "Erreur inconnue"));
                        }
                    } catch (e) {
                        reject(new Error("Réponse invalide du serveur"));
                    }
                } else {
                    reject(new Error(`Erreur HTTP: ${xhr.status}`));
                }
            };

            xhr.onerror = () => {
                reject(new Error("Erreur de connexion"));
            };

            // Configuration et envoi
            const uploadUrl = this.props.uploadUrl || '/documents/upload';
            xhr.open('POST', uploadUrl, true);

            // Headers CSRF si nécessaire
            const csrfToken = document.querySelector('meta[name="csrf-token"]');
            if (csrfToken) {
                xhr.setRequestHeader('X-CSRFToken', csrfToken.getAttribute('content'));
            }

            xhr.send(formData);
        });
    }

    /**
     * Suppression d'un fichier sélectionné
     */
    _removeFile(index) {
        this.state.selectedFiles.splice(index, 1);
        this.state.selectedFiles = [...this.state.selectedFiles];
    }

    /**
     * Preview d'un fichier
     */
    _previewFile(file) {
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                this.dialog.add("construction_contact_extension.ImagePreviewDialog", {
                    imageUrl: e.target.result,
                    fileName: file.name
                });
            };
            reader.readAsDataURL(file);
        } else {
            this.notification.add(
                _t("Preview disponible uniquement pour les images"),
                { type: "info" }
            );
        }
    }

    /**
     * Upload manuel (bouton)
     */
    async onManualUpload() {
        if (this.state.selectedFiles.length === 0) {
            this.notification.add(
                _t("Aucun fichier sélectionné"),
                { type: "warning" }
            );
            return;
        }

        await this._uploadFiles(this.state.selectedFiles);
    }

    /**
     * Formatage de la taille de fichier
     */
    _formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Getters pour le template
     */
    get dragOverClass() {
        return this.state.isDragOver ? 'o_drag_over' : '';
    }

    get uploadingClass() {
        return this.state.isUploading ? 'o_uploading' : '';
    }

    get hasFiles() {
        return this.state.selectedFiles.length > 0;
    }

    get hasErrors() {
        return this.state.validationErrors.length > 0;
    }
}

// Enregistrement du composant
export const documentUpload = {
    component: DocumentUpload,
};
