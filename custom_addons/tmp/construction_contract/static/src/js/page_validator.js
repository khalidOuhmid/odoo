/**
 * Page Validator
 * Manages page validation state and signature button enabling
 */

(function() {
    'use strict';

    class PageValidator {
        constructor(contractId, accessToken, totalPages, validatedPages = []) {
            this.contractId = contractId;
            this.accessToken = accessToken;
            this.totalPages = totalPages;
            this.validatedPages = new Set(validatedPages);
            this.currentPage = 1;
            this.isValidating = false;

            this.bindElements();
            this.bindEvents();
            this.updateUI();
        }

        bindElements() {
            this.validateBtn = document.getElementById('btn-validate-page');
            this.prevBtn = document.getElementById('btn-prev-page');
            this.nextBtn = document.getElementById('btn-next-page');
            this.currentPageEl = document.getElementById('current-page');
            this.progressBar = document.querySelector('.progress-bar');
            this.progressText = document.querySelector('.progress + p');
        }

        bindEvents() {
            // Validate button
            if (this.validateBtn) {
                this.validateBtn.addEventListener('click', () => this.validateCurrentPage());
            }

            // Navigation buttons
            if (this.prevBtn) {
                this.prevBtn.addEventListener('click', () => {
                    if (window.pdfViewer) {
                        window.pdfViewer.prevPage();
                    }
                });
            }

            if (this.nextBtn) {
                this.nextBtn.addEventListener('click', () => {
                    // Can only go to next page if current page is validated
                    if (!this.isPageValidated(this.currentPage)) {
                        this.showMessage('Veuillez valider cette page avant de continuer.', 'warning');
                        return;
                    }
                    
                    if (window.pdfViewer) {
                        window.pdfViewer.nextPage();
                    }
                });
            }

            // Listen to PDF page changes
            window.addEventListener('pdf:pageChanged', (e) => {
                this.currentPage = e.detail.currentPage;
                this.updateUI();
            });

            // Listen to PDF loaded event
            window.addEventListener('pdf:loaded', (e) => {
                this.totalPages = e.detail.totalPages;
                this.updateUI();
            });
        }

        _rpc(url, params) {
            return new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open('POST', url, true);
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.onload = function() {
                    console.log('RPC response status:', xhr.status);
                    console.log('RPC response text:', xhr.responseText.substring(0, 500));
                    
                    if (xhr.status >= 200 && xhr.status < 300) {
                        try {
                            const response = JSON.parse(xhr.responseText);
                            console.log('RPC parsed response:', response);
                            
                            if (response.result) {
                                resolve(response.result);
                            } else if (response.error) {
                                const errorMsg = response.error.data?.message || 
                                                response.error.message || 
                                                response.error.data?.debug || 
                                                'Server error';
                                console.error('RPC error response:', response.error);
                                reject(new Error(errorMsg));
                            } else {
                                // Direct response (no result/error wrapper)
                                resolve(response);
                            }
                        } catch (e) {
                            console.error('RPC JSON parse error:', e);
                            console.error('Response text:', xhr.responseText);
                            reject(new Error('Invalid JSON response: ' + e.message + '. Response: ' + xhr.responseText.substring(0, 200)));
                        }
                    } else {
                        // HTTP error - try to parse error message
                        let errorMsg = 'HTTP ' + xhr.status;
                        try {
                            const errorResponse = JSON.parse(xhr.responseText);
                            if (errorResponse.error?.message) {
                                errorMsg = errorResponse.error.message;
                            } else if (errorResponse.message) {
                                errorMsg = errorResponse.message;
                            }
                        } catch (e) {
                            // Not JSON, use response text
                            if (xhr.responseText && xhr.responseText.length > 0) {
                                errorMsg += ': ' + xhr.responseText.substring(0, 200);
                            }
                        }
                        console.error('RPC HTTP error:', xhr.status, xhr.responseText);
                        reject(new Error(errorMsg));
                    }
                };
                xhr.onerror = function() {
                    console.error('RPC network error');
                    reject(new Error('Network error'));
                };
                const payload = {
                    jsonrpc: "2.0",
                    method: "call",
                    params: params,
                    id: Math.floor(Math.random() * 1000000000)
                };
                console.log('RPC sending to', url, ':', payload);
                xhr.send(JSON.stringify(payload));
            });
        }

        async validateCurrentPage() {
            if (this.isValidating) return;
            
            // Check if already validated
            if (this.isPageValidated(this.currentPage)) {
                this.showMessage('Cette page est déjà validée.', 'info');
                return;
            }

            this.isValidating = true;
            this.validateBtn.disabled = true;
            this.validateBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Validation en cours...';

            try {
                // Use Odoo JSON-RPC format for type='json' routes
                console.log('Calling validation endpoint with:', {
                    contract_id: parseInt(this.contractId, 10),
                    access_token: this.accessToken,
                    page_number: parseInt(this.currentPage, 10),
                });

                const data = await this._rpc('/contract/page/validate', {
                    contract_id: parseInt(this.contractId, 10),
                    access_token: this.accessToken,
                    page_number: parseInt(this.currentPage, 10),
                });

                console.log('Validation response:', data);

                if (data.status === 'success') {
                    // Add to validated pages
                    this.validatedPages.add(this.currentPage);
                    this.updateUI();
                    this.showMessage(`Page ${this.currentPage} validée !`, 'success');

                    // Auto-advance to next page after a short delay
                    setTimeout(() => {
                        if (this.currentPage < this.totalPages) {
                            window.pdfViewer.nextPage();
                        } else {
                            // Last page validated - reload to show signature section
                            this.showMessage('Toutes les pages sont validées ! Vous pouvez maintenant signer le contrat.', 'success');
                            setTimeout(() => window.location.reload(), 1500);
                        }
                    }, 800);

                } else {
                    const errorMsg = data.message || data.error || 'La validation a échoué';
                    console.error('Validation failed:', errorMsg, data);
                    throw new Error(errorMsg);
                }

            } catch (error) {
                console.error('Validation error:', error);
                console.error('Error details:', {
                    message: error.message,
                    stack: error.stack,
                    name: error.name
                });
                this.showMessage('Erreur : ' + (error.message || 'Une erreur inconnue s\'est produite'), 'danger');
            } finally {
                this.isValidating = false;
                this.validateBtn.disabled = false;
                this.validateBtn.innerHTML = '<i class="fa fa-check"></i> Valider cette page';
            }
        }

        isPageValidated(pageNum) {
            return this.validatedPages.has(pageNum);
        }

        updateUI() {
            // Update validate button
            if (this.validateBtn) {
                if (this.isPageValidated(this.currentPage)) {
                    this.validateBtn.disabled = true;
                    this.validateBtn.innerHTML = '<i class="fa fa-check-circle"></i> Page validée';
                    this.validateBtn.classList.remove('btn-success');
                    this.validateBtn.classList.add('btn-secondary');
                } else {
                    this.validateBtn.disabled = false;
                    this.validateBtn.innerHTML = '<i class="fa fa-check"></i> Valider cette page';
                    this.validateBtn.classList.remove('btn-secondary');
                    this.validateBtn.classList.add('btn-success');
                }
            }

            // Update navigation buttons
            if (this.prevBtn) {
                this.prevBtn.disabled = (this.currentPage <= 1);
            }

            if (this.nextBtn) {
                const isCurrentValidated = this.isPageValidated(this.currentPage);
                const isLastPage = (this.currentPage >= this.totalPages);
                
                // Next button enabled only if current page is validated and not last page
                this.nextBtn.disabled = !isCurrentValidated || isLastPage;
                
                // Visual feedback
                if (!isCurrentValidated) {
                    this.nextBtn.title = 'Validez d\'abord cette page';
                } else if (isLastPage) {
                    this.nextBtn.title = 'Dernière page';
                } else {
                    this.nextBtn.title = 'Page suivante';
                }
            }

            // Update progress bar
            const completionRate = (this.validatedPages.size / this.totalPages) * 100;
            if (this.progressBar) {
                this.progressBar.style.width = completionRate + '%';
                this.progressBar.setAttribute('aria-valuenow', completionRate);
                this.progressBar.textContent = Math.round(completionRate) + '%';
            }

            if (this.progressText) {
                const remaining = this.totalPages - this.validatedPages.size;
                this.progressText.innerHTML = `
                    <strong>${this.validatedPages.size} / ${this.totalPages} pages validées</strong>
                    ${remaining > 0 ? `(${remaining} restante${remaining > 1 ? 's' : ''})` : ''}
                `;
            }
        }

        showMessage(message, type = 'info') {
            // Create toast/alert at top of page
            const alert = document.createElement('div');
            alert.className = `alert alert-${type} alert-dismissible fade show`;
            alert.style.position = 'fixed';
            alert.style.top = '20px';
            alert.style.right = '20px';
            alert.style.zIndex = '9999';
            alert.style.minWidth = '300px';
            alert.innerHTML = `
                ${message}
                <button type="button" class="close" data-dismiss="alert">
                    <span>&times;</span>
                </button>
            `;
            
            document.body.appendChild(alert);

            // Auto-remove after 3 seconds
            setTimeout(() => {
                alert.remove();
            }, 3000);
        }
    }

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        // Check if we're on the signature portal page
        if (typeof contractId !== 'undefined' && typeof accessToken !== 'undefined') {
            console.log('Initializing PageValidator');
            window.pageValidator = new PageValidator(
                contractId,
                accessToken,
                totalPages,
                validatedPages || []
            );
        }
    });

    // Export to window
    window.PageValidator = PageValidator;

})();
