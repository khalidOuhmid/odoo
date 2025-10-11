/* Enhanced Document Preview JavaScript */

odoo.define('blg_contacts_extension.enhanced_document_preview', function (require) {
    "use strict";
    
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var framework = require('web.framework');
    var session = require('web.session');
    
    var _t = core._t;
    
    /**
     * Enhanced Document Preview Manager
     */
    var DocumentPreviewManager = {
        
        /**
         * Ouvre une prévisualisation modale du document
         */
        openModalPreview: function(partnerId, docType, options) {
            options = options || {};
            
            var self = this;
            var previewUrl = '/blg_contacts/document/preview/' + partnerId + '/' + docType + '?direct=1';
            var downloadUrl = '/blg_contacts/document/download/' + partnerId + '/' + docType;
            
            // Créer le contenu de la modal
            var $content = $('<div class="o_document_preview_modal_content">');
            var $loading = $('<div class="o_document_preview_loading"><i class="fa fa-spinner fa-spin"></i> Chargement du document...</div>');
            $content.append($loading);
            
            // Créer la modal
            var dialog = new Dialog(null, {
                title: options.title || 'Prévisualisation du document',
                size: 'extra-large',
                $content: $content,
                buttons: [
                    {
                        text: _t('Télécharger'),
                        classes: 'btn-secondary',
                        icon: 'fa-download',
                        click: function() {
                            window.open(downloadUrl, '_blank');
                        }
                    },
                    {
                        text: _t('Fermer'),
                        close: true
                    }
                ]
            });
            
            dialog.open().then(function() {
                // Ajouter la classe CSS pour le style
                dialog.$modal.addClass('o_document_preview_modal');
                
                // Charger le document
                self._loadDocumentInContainer($content, previewUrl, options);
            });
            
            return dialog;
        },
        
        /**
         * Crée une prévisualisation inline dans un conteneur
         */
        createInlinePreview: function($container, partnerId, docType, options) {
            options = options || {};
            
            var previewUrl = '/blg_contacts/document/preview/' + partnerId + '/' + docType + '?direct=1';
            var downloadUrl = '/blg_contacts/document/download/' + partnerId + '/' + docType;
            
            // Structure HTML de la prévisualisation inline
            var $preview = $(`
                <div class="o_document_preview_inline o_document_preview_fade_in">
                    <div class="o_document_preview_inline_header">
                        <span><i class="fa fa-eye"></i> Aperçu du document</span>
                        <div>
                            <a href="${downloadUrl}" target="_blank" class="btn btn-sm btn-outline-secondary">
                                <i class="fa fa-download"></i>
                            </a>
                            <button type="button" class="btn btn-sm btn-outline-secondary o_close_preview">
                                <i class="fa fa-times"></i>
                            </button>
                        </div>
                    </div>
                    <div class="o_document_preview_inline_content">
                        <div class="o_document_preview_loading">
                            <i class="fa fa-spinner fa-spin"></i> Chargement...
                        </div>
                    </div>
                </div>
            `);
            
            // Ajouter les événements
            $preview.find('.o_close_preview').on('click', function() {
                $preview.remove();
            });
            
            // Insérer dans le conteneur
            $container.append($preview);
            
            // Charger le document
            this._loadDocumentInContainer($preview.find('.o_document_preview_inline_content'), previewUrl, options);
            
            return $preview;
        },
        
        /**
         * Crée une miniature cliquable
         */
        createThumbnail: function($container, partnerId, docType, options) {
            options = options || {};
            
            var self = this;
            var previewUrl = '/blg_contacts/document/preview/' + partnerId + '/' + docType + '?direct=1';
            
            // Détecter le type de fichier
            this._getDocumentInfo(partnerId, docType).then(function(info) {
                var $thumbnail = $('<div class="o_document_thumbnail_preview">');
                
                if (info.is_image) {
                    var $img = $('<img>').attr('src', previewUrl);
                    $thumbnail.append($img);
                } else if (info.is_pdf) {
                    $thumbnail.append('<i class="fa fa-file-pdf-o"></i>');
                } else {
                    $thumbnail.append('<i class="fa fa-file-o"></i>');
                }
                
                // Événement clic pour ouvrir la modal
                $thumbnail.on('click', function() {
                    self.openModalPreview(partnerId, docType, {
                        title: options.title || info.filename
                    });
                });
                
                $container.append($thumbnail);
            });
        },
        
        /**
         * Charge un document dans un conteneur
         */
        _loadDocumentInContainer: function($container, previewUrl, options) {
            var $loading = $container.find('.o_document_preview_loading');
            
            // Créer l'iframe pour le document
            var $iframe = $('<iframe>').attr({
                'src': previewUrl,
                'style': 'width: 100%; height: 100%; border: none;'
            });
            
            // Gérer le chargement
            $iframe.on('load', function() {
                $loading.fadeOut(300, function() {
                    $container.append($iframe);
                    $iframe.hide().fadeIn(300);
                });
            });
            
            // Gérer les erreurs
            $iframe.on('error', function() {
                $loading.fadeOut(300, function() {
                    var $error = $(`
                        <div class="o_document_preview_error">
                            <i class="fa fa-exclamation-triangle"></i>
                            <div>Erreur lors du chargement du document</div>
                            <small class="text-muted">Veuillez réessayer ou télécharger le fichier</small>
                        </div>
                    `);
                    $container.append($error);
                });
            });
        },
        
        /**
         * Récupère les informations d'un document
         */
        _getDocumentInfo: function(partnerId, docType) {
            return $.ajax({
                url: '/blg_contacts/document/info/' + partnerId + '/' + docType,
                type: 'GET',
                dataType: 'json'
            });
        }
    };
    
    /**
     * Widget pour les boutons de prévisualisation améliorés
     */
    var EnhancedPreviewWidget = core.Class.extend({
        
        init: function(parent, options) {
            this.parent = parent;
            this.options = options || {};
            this.partnerId = options.partnerId;
            this.docType = options.docType;
        },
        
        start: function() {
            this._renderButtons();
            this._bindEvents();
        },
        
        _renderButtons: function() {
            var self = this;
            
            this.$buttons = $(`
                <div class="o_document_preview_buttons">
                    <div class="btn-group" role="group">
                        <button type="button" class="btn btn-primary btn-sm o_preview_modal">
                            <i class="fa fa-eye"></i> Aperçu
                        </button>
                        <button type="button" class="btn btn-outline-primary btn-sm o_preview_inline">
                            <i class="fa fa-expand"></i>
                        </button>
                        <button type="button" class="btn btn-secondary btn-sm o_download">
                            <i class="fa fa-download"></i> Télécharger
                        </button>
                    </div>
                </div>
            `);
            
            this.parent.$el.append(this.$buttons);
        },
        
        _bindEvents: function() {
            var self = this;
            
            // Bouton modal
            this.$buttons.find('.o_preview_modal').on('click', function() {
                DocumentPreviewManager.openModalPreview(
                    self.partnerId, 
                    self.docType, 
                    self.options
                );
            });
            
            // Bouton inline
            this.$buttons.find('.o_preview_inline').on('click', function() {
                var $existing = self.parent.$el.find('.o_document_preview_inline');
                if ($existing.length) {
                    $existing.remove();
                } else {
                    DocumentPreviewManager.createInlinePreview(
                        self.parent.$el, 
                        self.partnerId, 
                        self.docType, 
                        self.options
                    );
                }
            });
            
            // Bouton téléchargement
            this.$buttons.find('.o_download').on('click', function() {
                var downloadUrl = '/blg_contacts/document/download/' + self.partnerId + '/' + self.docType;
                window.open(downloadUrl, '_blank');
            });
        }
    });
    
    // Initialisation automatique des widgets sur les formulaires
    $(document).ready(function() {
        // Attacher aux boutons de prévisualisation existants
        $('.o_document_preview_buttons button[name="action_preview_document"]').each(function() {
            var $btn = $(this);
            var context = $btn.data('context') || {};
            var docType = context.doc_type;
            
            if (docType) {
                // Remplacer par le widget amélioré
                var $container = $btn.closest('.o_document_preview_buttons');
                var widget = new EnhancedPreviewWidget($container, {
                    partnerId: $('input[name="id"]').val(),
                    docType: docType
                });
                
                $container.empty();
                widget.start();
            }
        });
    });
    
    // Exposer les classes globalement
    return {
        DocumentPreviewManager: DocumentPreviewManager,
        EnhancedPreviewWidget: EnhancedPreviewWidget
    };
    
});
