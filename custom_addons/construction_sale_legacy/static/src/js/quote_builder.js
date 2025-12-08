/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Controller JavaScript pour l'assistant intelligent de devis construction
 * Améliore l'UX avec des interactions modernes et classes CSS spécifiques
 */
export class ConstructionQuoteWizard extends Component {
    
    setup() {
        this.state = useState({
            searchTerm: '',
            selectedProducts: [],
            isLoading: false
        });
        
        // Ajouter la classe CSS pour le style
        this.addCSSClass();
        
        // Initialiser les événements
        this.initializeEvents();
    }
    
    /**
     * Ajoute la classe CSS principale pour le styling spécifique
     */
    addCSSClass() {
        const formContainer = document.querySelector('.o_form_view');
        if (formContainer && formContainer.querySelector('.construction-quote-wizard')) {
            formContainer.classList.add('construction-quote-wizard-container');
        }
    }
    
    /**
     * Initialise les événements de l'interface
     */
    initializeEvents() {
        // Recherche en temps réel
        this.setupLiveSearch();
        
        // Double-clic pour ajouter des produits
        this.setupProductDoubleClick();
        
        // Animations des boutons
        this.setupButtonAnimations();
    }
    
    /**
     * Configure la recherche en temps réel
     */
    setupLiveSearch() {
        const searchInput = document.querySelector('.construction-quote-wizard input[name="search_term"]');
        if (searchInput) {
            let timeoutId;
            
            searchInput.addEventListener('input', (event) => {
                clearTimeout(timeoutId);
                
                // Debounce de 300ms
                timeoutId = setTimeout(() => {
                    this.performSearch(event.target.value);
                }, 300);
            });
        }
    }
    
    /**
     * Configure le double-clic sur les produits
     */
    setupProductDoubleClick() {
        document.addEventListener('dblclick', (event) => {
            const productRow = event.target.closest('.o_data_row');
            if (productRow && productRow.closest('.available_products_list')) {
                this.addProductToSelection(productRow);
            }
        });
    }
    
    /**
     * Configure les animations des boutons spécifiques au module
     */
    setupButtonAnimations() {
        document.querySelectorAll('.construction-quote-wizard .btn').forEach(button => {
            button.addEventListener('mouseenter', () => {
                button.style.transition = 'all 0.3s ease';
            });
        });
    }
    
    /**
     * Effectue une recherche de produits
     */
    async performSearch(searchTerm) {
        this.state.isLoading = true;
        this.state.searchTerm = searchTerm;
        
        try {
            // Ici, vous pouvez ajouter une logique de recherche avancée
            // par exemple, des appels RPC pour des recherches complexes
            
            this.showSearchIndicator();
            
            // Simulation d'un délai de recherche
            await new Promise(resolve => setTimeout(resolve, 200));
            
        } catch (error) {
            console.error('Erreur lors de la recherche:', error);
            this.showErrorNotification('Erreur lors de la recherche');
        } finally {
            this.state.isLoading = false;
            this.hideSearchIndicator();
        }
    }
    
    /**
     * Ajoute un produit à la sélection
     */
    addProductToSelection(productRow) {
        const productId = productRow.dataset.id;
        const productName = productRow.querySelector('.o_data_cell')?.textContent;
        
        if (productId) {
            // Animation de feedback
            this.animateProductAddition(productRow);
            
            // Notification de succès
            this.showSuccessNotification(`Produit "${productName}" ajouté`);
            
            // Mettre à jour l'état
            this.state.selectedProducts.push({
                id: productId,
                name: productName
            });
        }
    }
    
    /**
     * Anime l'ajout d'un produit
     */
    animateProductAddition(element) {
        element.style.transform = 'scale(1.05)';
        element.style.backgroundColor = '#d4edda';
        element.style.transition = 'all 0.3s ease';
        
        setTimeout(() => {
            element.style.transform = 'scale(1)';
            element.style.backgroundColor = '';
        }, 300);
    }
    
    /**
     * Affiche un indicateur de recherche spécifique au module
     */
    showSearchIndicator() {
        const searchInput = document.querySelector('.construction-quote-wizard input[name="search_term"]');
        if (searchInput) {
            searchInput.style.background = 'url("data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyMCAyMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICAgIDxjaXJjbGUgY3g9IjEwIiBjeT0iMTAiIHI9IjMiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzY2N2VlYSIgc3Ryb2tlLXdpZHRoPSIyIj4KICAgICAgICA8YW5pbWF0ZVRyYW5zZm9ybSBhdHRyaWJ1dGVOYW1lPSJ0cmFuc2Zvcm0iIHR5cGU9InJvdGF0ZSIgdmFsdWVzPSIwIDEwIDEwOzM2MCAxMCAxMCIgZHVyPSIxcyIgcmVwZWF0Q291bnQ9ImluZGVmaW5pdGUiLz4KICAgIDwvY2lyY2xlPgo8L3N2Zz4=") no-repeat right 10px center';
            searchInput.style.backgroundSize = '20px 20px';
        }
    }
    
    /**
     * Cache l'indicateur de recherche
     */
    hideSearchIndicator() {
        const searchInput = document.querySelector('.construction-quote-wizard input[name="search_term"]');
        if (searchInput) {
            searchInput.style.background = '';
        }
    }
    
    /**
     * Affiche une notification de succès
     */
    showSuccessNotification(message) {
        this.showNotification(message, 'success');
    }
    
    /**
     * Affiche une notification d'erreur
     */
    showErrorNotification(message) {
        this.showNotification(message, 'danger');
    }
    
    /**
     * Affiche une notification générique avec classe spécifique
     */
    showNotification(message, type = 'info') {
        // Créer l'élément de notification avec classe spécifique
        const notification = document.createElement('div');
        notification.className = `construction-quote-notification alert alert-${type} alert-dismissible fade show`;
        notification.innerHTML = `
            <strong>${type === 'success' ? '✅' : type === 'danger' ? '❌' : 'ℹ️'}</strong>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Ajouter au DOM
        document.body.appendChild(notification);
        
        // Supprimer automatiquement après 3 secondes
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 3000);
    }
}

// Enregistrer le composant dans le registry d'Odoo
registry.category("components").add("ConstructionQuoteWizard", ConstructionQuoteWizard);

/**
 * Initialisation automatique quand le DOM est prêt
 */
document.addEventListener('DOMContentLoaded', function() {
    // Vérifier si nous sommes dans le wizard de devis (classe spécifique)
    if (document.querySelector('.construction-quote-wizard') || 
        document.querySelector('.o_construction_sale')) {
        
        new ConstructionQuoteWizard().setup();
    }
});

/**
 * Fonctions utilitaires globales pour l'amélioration UX
 * Préfixées pour éviter les conflits
 */
window.ConstructionQuoteUtils = {
    
    /**
     * Formate le prix pour l'affichage
     */
    formatPrice(price, currency = '€') {
        return new Intl.NumberFormat('fr-FR', {
            style: 'decimal',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(price) + ' ' + currency;
    },
    
    /**
     * Validation des quantités
     */
    validateQuantity(quantity) {
        const num = parseFloat(quantity);
        return !isNaN(num) && num > 0;
    },
    
    /**
     * Copie le texte dans le presse-papier
     */
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            console.error('Erreur lors de la copie:', err);
            return false;
        }
    },
    
    /**
     * Ajoute une classe CSS spécifique pour les éléments construction
     */
    markAsConstructionElement(element) {
        if (element) {
            element.classList.add('o_construction_element');
        }
    },
    
    /**
     * Vérifie si un élément fait partie du module construction
     */
    isConstructionElement(element) {
        return element && (
            element.closest('.construction-quote-wizard') ||
            element.closest('.o_construction_sale') ||
            element.classList.contains('o_construction_element')
        );
    }
}; 