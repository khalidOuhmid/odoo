/** @odoo-module **/

/**
 * Signature Pad Component
 * Handles signature drawing and capture in the portal
 */

(function() {
    'use strict';

    // Signature Pad Class
    class SignaturePad {
        constructor(canvas) {
            this.canvas = canvas;
            this.ctx = canvas.getContext('2d');
            this.isDrawing = false;
            this.lastX = 0;
            this.lastY = 0;

            this.setupCanvas();
            this.bindEvents();
        }

        setupCanvas() {
            // Set canvas size
            const rect = this.canvas.getBoundingClientRect();
            this.canvas.width = rect.width;
            this.canvas.height = rect.height;

            // Set drawing style
            this.ctx.strokeStyle = '#000000';
            this.ctx.lineWidth = 2;
            this.ctx.lineCap = 'round';
            this.ctx.lineJoin = 'round';
        }

        bindEvents() {
            // Mouse events
            this.canvas.addEventListener('mousedown', this.startDrawing.bind(this));
            this.canvas.addEventListener('mousemove', this.draw.bind(this));
            this.canvas.addEventListener('mouseup', this.stopDrawing.bind(this));
            this.canvas.addEventListener('mouseout', this.stopDrawing.bind(this));

            // Touch events (mobile)
            this.canvas.addEventListener('touchstart', this.handleTouchStart.bind(this));
            this.canvas.addEventListener('touchmove', this.handleTouchMove.bind(this));
            this.canvas.addEventListener('touchend', this.stopDrawing.bind(this));
        }

        startDrawing(e) {
            this.isDrawing = true;
            const coords = this.getCoordinates(e);
            this.lastX = coords.x;
            this.lastY = coords.y;
            
            // Add visual feedback
            this.canvas.classList.add('drawing');
            
            // Hide overlay text when drawing starts
            const overlay = document.querySelector('.signature-pad-overlay');
            if (overlay) {
                overlay.style.display = 'none';
            }
        }

        draw(e) {
            if (!this.isDrawing) return;

            e.preventDefault();

            const coords = this.getCoordinates(e);

            this.ctx.beginPath();
            this.ctx.moveTo(this.lastX, this.lastY);
            this.ctx.lineTo(coords.x, coords.y);
            this.ctx.stroke();

            this.lastX = coords.x;
            this.lastY = coords.y;
        }

        stopDrawing() {
            this.isDrawing = false;
            
            // Remove visual feedback
            this.canvas.classList.remove('drawing');
        }

        getCoordinates(e) {
            const rect = this.canvas.getBoundingClientRect();
            const x = (e.clientX || e.touches[0].clientX) - rect.left;
            const y = (e.clientY || e.touches[0].clientY) - rect.top;
            return { x, y };
        }

        handleTouchStart(e) {
            e.preventDefault();
            this.startDrawing(e);
        }

        handleTouchMove(e) {
            e.preventDefault();
            this.draw(e);
        }

        clear() {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            
            // Show overlay text again
            const overlay = document.querySelector('.signature-pad-overlay');
            if (overlay) {
                overlay.style.display = 'block';
            }
        }

        isEmpty() {
            const blank = document.createElement('canvas');
            blank.width = this.canvas.width;
            blank.height = this.canvas.height;
            return this.canvas.toDataURL() === blank.toDataURL();
        }

        getDataURL() {
            return this.canvas.toDataURL('image/png');
        }

        getBlob() {
            return new Promise((resolve) => {
                this.canvas.toBlob((blob) => {
                    resolve(blob);
                }, 'image/png');
            });
        }
    }

    // Initialize signature pad when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        const canvas = document.getElementById('signature-pad');

        if (!canvas) return;

        // Create signature pad instance
        window.signaturePad = new SignaturePad(canvas);

        // Clear button
        const clearBtn = document.getElementById('btn-clear-signature');
        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                window.signaturePad.clear();
            });
        }

        // Sign button
        const signBtn = document.getElementById('btn-sign-contract');
        if (signBtn) {
            signBtn.addEventListener('click', async function() {
                if (window.signaturePad.isEmpty()) {
                    // Show confirmation dialog in French
                    if (!confirm('Veuillez dessiner votre signature avant de signer le contrat.')) {
                        return;
                    }
                    return;
                }

                // Confirmation dialog
                if (!confirm('Êtes-vous sûr de vouloir signer ce contrat ? Cette action est irréversible.')) {
                    return;
                }

                // Disable button
                signBtn.disabled = true;
                signBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Signature en cours...';

                try {
                    // Get signature data
                    const signatureData = window.signaturePad.getDataURL();

                    // Use Odoo JSON-RPC format
                    const xhr = new XMLHttpRequest();
                    xhr.open('POST', `/my/contract/${contractId}/save_signature`, true);
                    xhr.setRequestHeader('Content-Type', 'application/json');
                    xhr.onload = function() {
                        if (xhr.status >= 200 && xhr.status < 300) {
                            try {
                                const response = JSON.parse(xhr.responseText);
                                let data;
                                
                                if (response.result) {
                                    data = response.result;
                                } else if (response.error) {
                                    throw new Error(response.error.data?.message || response.error.message || 'Unknown error');
                                } else {
                                    data = response;
                                }

                                if (data.status === 'success') {
                                    // Redirect to confirmation page
                                    window.location.href = data.redirect_url;
                                } else {
                                    alert('Erreur : ' + (data.message || 'Erreur inconnue'));
                                    signBtn.disabled = false;
                                    signBtn.innerHTML = '<i class="fa fa-check-circle"></i> Signer le contrat';
                                }
                            } catch (e) {
                                console.error('Signature parsing error:', e);
                                console.error('Response text:', xhr.responseText);
                                alert('Erreur lors de l\'analyse de la réponse : ' + e.message);
                                signBtn.disabled = false;
                                signBtn.innerHTML = '<i class="fa fa-check-circle"></i> Signer le contrat';
                            }
                        } else {
                            console.error('HTTP error:', xhr.status);
                            console.error('Response text:', xhr.responseText);
                            alert('Erreur lors de l\'enregistrement de la signature : HTTP ' + xhr.status);
                            signBtn.disabled = false;
                            signBtn.innerHTML = '<i class="fa fa-check-circle"></i> Signer le contrat';
                        }
                    };
                    xhr.onerror = function() {
                        console.error('Network error');
                        alert('Erreur réseau lors de l\'enregistrement de la signature');
                        signBtn.disabled = false;
                        signBtn.innerHTML = '<i class="fa fa-check-circle"></i> Signer le contrat';
                    };
                    xhr.send(JSON.stringify({
                        jsonrpc: '2.0',
                        method: 'call',
                        params: {
                            contract_id: parseInt(contractId, 10),
                            access_token: accessToken,
                            signature_data: signatureData,
                        },
                        id: Math.floor(Math.random() * 1000000000)
                    }));

                } catch (error) {
                    console.error('Signature error:', error);
                    alert('Erreur lors de l\'enregistrement de la signature : ' + error.message);
                    signBtn.disabled = false;
                    signBtn.innerHTML = '<i class="fa fa-check-circle"></i> Signer le contrat';
                }
            });
        }
    });

})();
