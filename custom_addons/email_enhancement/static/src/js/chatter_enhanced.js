/** @odoo-module **/

// Module Email Enhancement pour Odoo 18
// Améliore le chatter avec des fonctionnalités Gmail-like

console.log("Email Enhancement: Module chargé");

// Fonction pour ouvrir l'éditeur avancé
function openAdvancedMailEditor(context = {}) {
    console.log('Email Enhancement: Ouverture de l\'éditeur avancé');
    
    // Essayer d'accéder au service d'action d'Odoo
    let actionService = null;
    try {
        if (window.odoo && window.odoo.__WOWL_DEBUG__ && window.odoo.__WOWL_DEBUG__.env) {
            actionService = window.odoo.__WOWL_DEBUG__.env.services.action;
        }
    } catch (error) {
        console.log("Email Enhancement: Impossible d'accéder au service d'action");
    }
    
    if (actionService) {
        // Utiliser exactement la même approche que le bouton Full composer
        const action = {
            name: "Composer de mail avancé",
            type: "ir.actions.act_window",
            res_model: "mail.compose.message",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_composition_mode: 'comment',
                mail_post_autofollow: true,
                ...context
            }
        };
        
        actionService.doAction(action);
    } else {
        // Fallback : URL directe dans la même page
        const baseUrl = window.location.origin;
        let url = `${baseUrl}/web#action=mail.action_email_compose_message_wizard&model=mail.compose.message&view_type=form`;
        
        // Ajouter les paramètres de contexte
        const params = new URLSearchParams();
        Object.keys(context).forEach(key => {
            if (context[key]) {
                params.append(key, context[key]);
            }
        });
        
        if (params.toString()) {
            url += '&' + params.toString();
        }
        
        // Ouvrir dans la même page (comme target: "current")
        window.location.href = url;
    }
}

// Fonction pour faire un vrai reply à un message
function replyToMessage(messageElement) {
    console.log('Email Enhancement: Reply au message');
    
    // Extraire les informations du message
    const messageId = messageElement.getAttribute('data-message-id') || 
                     messageElement.querySelector('[data-message-id]')?.getAttribute('data-message-id');
    const messageSubject = messageElement.querySelector('.o-mail-Message-subject')?.textContent || '';
    const messageAuthor = messageElement.querySelector('.o-mail-Message-author')?.textContent || '';
    
    // Préparer le contexte pour la réponse
    const context = {
        default_composition_mode: 'comment',
        default_parent_id: messageId,
        mail_post_autofollow: 'true',
    };
    
    // Préparer le sujet avec "Re:"
    if (messageSubject && !messageSubject.startsWith('Re:')) {
        context.default_subject = `Re: ${messageSubject}`;
    }
    
    // Préparer le destinataire (auteur du message original)
    if (messageAuthor) {
        context.default_partner_ids = messageAuthor;
    }
    
    // Ouvrir l'éditeur avancé avec le contexte de réponse
    openAdvancedMailEditor(context);
}

// Fonction pour intercepter le bouton "Send message"
function interceptSendMessageButton() {
    console.log("Email Enhancement: Recherche du bouton 'Send message'...");
    
    // Sélecteurs pour le bouton "Send message" dans Odoo 18
    const sendMessageButtons = document.querySelectorAll('.o-mail-Chatter-sendMessage');
    
    sendMessageButtons.forEach(function(button) {
        if (!button.hasAttribute('data-enhanced-intercepted')) {
            button.setAttribute('data-enhanced-intercepted', 'true');
            
            // Remplacer le comportement par défaut
            button.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                console.log('Email Enhancement: Bouton "Send message" cliqué - Ouverture de l\'éditeur avancé');
                
                // Récupérer les informations du chatter actuel
                const chatter = document.querySelector('.o-mail-Chatter');
                if (chatter) {
                    // Extraire les informations du thread depuis les attributs data
                    const threadId = chatter.getAttribute('data-thread-id') || 
                                   chatter.querySelector('[data-thread-id]')?.getAttribute('data-thread-id');
                    const threadModel = chatter.getAttribute('data-thread-model') || 
                                      chatter.querySelector('[data-thread-model]')?.getAttribute('data-thread-model');
                    
                    const context = {
                        default_res_id: threadId,
                        default_model: threadModel,
                    };
                    
                    openAdvancedMailEditor(context);
                } else {
                    openAdvancedMailEditor();
                }
            });
            
            console.log("Email Enhancement: Bouton 'Send message' intercepté avec succès");
        }
    });
}

// Fonction pour ajouter les boutons Reply
function addReplyButtons() {
    console.log("Email Enhancement: Recherche des messages pour ajouter les boutons Reply...");
    
    // Sélecteurs pour les messages dans Odoo 18
    const messages = document.querySelectorAll('.o-mail-Message, .o_Message');
    console.log("Email Enhancement: Nombre de messages trouvés:", messages.length);

    messages.forEach(function(message, index) {
        // Vérifier si le bouton n'existe pas déjà
        if (!message.querySelector('.reply-btn-enhanced')) {
            const messageActions = message.querySelector('.o-mail-Message-actions, .o_Message_actions');
            
            if (messageActions) {
                // Créer le bouton Reply
                const replyBtn = document.createElement('button');
                replyBtn.className = 'btn btn-sm btn-link reply-btn-enhanced';
                replyBtn.innerHTML = '<i class="fa fa-reply me-1"></i>Répondre';
                replyBtn.style.color = '#017e84';
                replyBtn.title = 'Répondre à ce message';

                // Action du bouton
                replyBtn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('Email Enhancement: Bouton Reply cliqué');
                    replyToMessage(message);
                });

                messageActions.appendChild(replyBtn);
                console.log(`Email Enhancement: Bouton Reply ajouté au message ${index}`);
            }
        }
    });
}

// Fonction pour intercepter les boutons d'envoi et ajouter la confirmation
function interceptSendButtons() {
    console.log("Email Enhancement: Interception des boutons d'envoi...");
    
    // Sélecteurs pour les boutons d'envoi dans Odoo 18
    const sendButtons = document.querySelectorAll('.o-mail-Composer-send, .o-Chatter_buttonSendMessage, button[title*="Send"], button[title*="Envoyer"]');
    
    sendButtons.forEach(function(button) {
        if (!button.hasAttribute('data-enhanced-send-intercepted')) {
            button.setAttribute('data-enhanced-send-intercepted', 'true');
            
            // Ajouter la confirmation avant envoi
            button.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                // Confirmation native
                if (confirm("Voulez-vous vraiment envoyer le message ?")) {
                    // Continuer avec l'envoi normal
                    button.click();
                } else {
                    console.log('Email Enhancement: Envoi annulé par l\'utilisateur');
                }
            });
            
            console.log("Email Enhancement: Bouton d'envoi intercepté avec confirmation");
        }
    });
}

// Fonction principale d'initialisation
function setupEmailEnhancement() {
    console.log("Email Enhancement: Initialisation du module...");
    
    // Observer les changements dans le DOM
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes.length > 0) {
                setTimeout(function() {
                    addReplyButtons();
                    interceptSendMessageButton();
                    interceptSendButtons();
                }, 100);
            }
        });
    });

    // Démarrer l'observation
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    // Initialisation immédiate
    setTimeout(function() {
        addReplyButtons();
        interceptSendMessageButton();
        interceptSendButtons();
    }, 1000);
}

// Setup de l'amélioration
document.addEventListener('DOMContentLoaded', function() {
    console.log("Email Enhancement: DOM chargé, initialisation...");
    setupEmailEnhancement();
});

// Export pour utilisation dans d'autres modules
export { };
