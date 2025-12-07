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

            // Set drawing style - thicker line for mobile
            const isMobile = window.innerWidth <= 768;
            this.ctx.strokeStyle = '#000000';
            this.ctx.lineWidth = isMobile ? 3 : 2;
            this.ctx.lineCap = 'round';
            this.ctx.lineJoin = 'round';
            
            // Prevent scrolling when drawing on mobile
            this.canvas.style.touchAction = 'none';
        }

        bindEvents() {
            // Mouse events
            this.canvas.addEventListener('mousedown', this.startDrawing.bind(this));
            this.canvas.addEventListener('mousemove', this.draw.bind(this));
            this.canvas.addEventListener('mouseup', this.stopDrawing.bind(this));
            this.canvas.addEventListener('mouseout', this.stopDrawing.bind(this));

            // Touch events (mobile) - with passive: false to allow preventDefault
            this.canvas.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: false });
            this.canvas.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
            this.canvas.addEventListener('touchend', this.stopDrawing.bind(this));
            this.canvas.addEventListener('touchcancel', this.stopDrawing.bind(this));
            
            // Handle window resize
            window.addEventListener('resize', this.handleResize.bind(this));
        }
        
        handleResize() {
            // Save current drawing
            const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
            
            // Resize canvas
            const rect = this.canvas.getBoundingClientRect();
            this.canvas.width = rect.width;
            this.canvas.height = rect.height;
            
            // Restore drawing
            this.ctx.putImageData(imageData, 0, 0);
            
            // Reapply styles
            const isMobile = window.innerWidth <= 768;
            this.ctx.strokeStyle = '#000000';
            this.ctx.lineWidth = isMobile ? 3 : 2;
            this.ctx.lineCap = 'round';
            this.ctx.lineJoin = 'round';
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
            let clientX, clientY;
            
            if (e.touches && e.touches.length > 0) {
                // Touch event
                clientX = e.touches[0].clientX;
                clientY = e.touches[0].clientY;
            } else if (e.changedTouches && e.changedTouches.length > 0) {
                // Touch end event
                clientX = e.changedTouches[0].clientX;
                clientY = e.changedTouches[0].clientY;
            } else {
                // Mouse event
                clientX = e.clientX;
                clientY = e.clientY;
            }
            
            // Calculate coordinates relative to canvas with proper scaling
            const scaleX = this.canvas.width / rect.width;
            const scaleY = this.canvas.height / rect.height;
            
            const x = (clientX - rect.left) * scaleX;
            const y = (clientY - rect.top) * scaleY;
            
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

    // Signature Upload Handler
    class SignatureUpload {
        constructor() {
            this.uploadZone = document.getElementById('signature-upload-zone');
            this.fileInput = document.getElementById('signature-file-input');
            this.preview = document.getElementById('upload-preview');
            this.previewImg = document.getElementById('signature-preview-img');
            this.removeBtn = document.getElementById('btn-remove-upload');
            this.placeholder = this.uploadZone?.querySelector('.upload-placeholder');
            this.imageData = null;

            if (this.uploadZone) {
                this.bindEvents();
            }
        }

        bindEvents() {
            // Drag and drop events
            this.uploadZone.addEventListener('dragover', this.handleDragOver.bind(this));
            this.uploadZone.addEventListener('dragleave', this.handleDragLeave.bind(this));
            this.uploadZone.addEventListener('drop', this.handleDrop.bind(this));

            // File input change
            this.fileInput.addEventListener('change', this.handleFileSelect.bind(this));

            // Remove button
            this.removeBtn.addEventListener('click', this.clear.bind(this));
        }

        handleDragOver(e) {
            e.preventDefault();
            e.stopPropagation();
            this.uploadZone.classList.add('drag-over');
        }

        handleDragLeave(e) {
            e.preventDefault();
            e.stopPropagation();
            this.uploadZone.classList.remove('drag-over');
        }

        handleDrop(e) {
            e.preventDefault();
            e.stopPropagation();
            this.uploadZone.classList.remove('drag-over');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.processFile(files[0]);
            }
        }

        handleFileSelect(e) {
            const files = e.target.files;
            if (files.length > 0) {
                this.processFile(files[0]);
            }
        }

        processFile(file) {
            // Validate file type
            if (!file.type.match('image/(png|jpeg|jpg)')) {
                alert('Veuillez sélectionner une image PNG ou JPG.');
                return;
            }

            // Validate file size (2MB max)
            if (file.size > 2 * 1024 * 1024) {
                alert('La taille du fichier ne doit pas dépasser 2MB.');
                return;
            }

            // Read file
            const reader = new FileReader();
            reader.onload = (e) => {
                this.imageData = e.target.result;
                this.showPreview(this.imageData);
            };
            reader.readAsDataURL(file);
        }

        showPreview(dataUrl) {
            this.previewImg.src = dataUrl;
            this.placeholder.style.display = 'none';
            this.preview.style.display = 'flex';
        }

        clear() {
            this.imageData = null;
            this.previewImg.src = '';
            this.fileInput.value = '';
            this.placeholder.style.display = 'block';
            this.preview.style.display = 'none';
        }

        isEmpty() {
            return !this.imageData;
        }

        getDataURL() {
            return this.imageData;
        }
    }

    // Signature Type Handler
    class SignatureType {
        constructor() {
            this.canvas = document.getElementById('signature-type-canvas');
            this.textInput = document.getElementById('signature-text-input');
            this.fontOptions = document.querySelectorAll('.font-option');
            this.selectedFont = 'Dancing Script';
            this.text = '';

            if (this.canvas) {
                this.ctx = this.canvas.getContext('2d');
                this.setupCanvas();
                this.bindEvents();
            }
        }

        setupCanvas() {
            this.canvas.width = 600;
            this.canvas.height = 150;
        }

        bindEvents() {
            // Text input
            this.textInput.addEventListener('input', (e) => {
                this.text = e.target.value;
                this.render();
            });

            // Font selection
            this.fontOptions.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    this.fontOptions.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    this.selectedFont = btn.dataset.font;
                    this.render();
                });
            });
        }

        render() {
            // Clear canvas
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

            if (!this.text) return;

            // Set font
            this.ctx.font = `bold 60px "${this.selectedFont}", cursive`;
            this.ctx.fillStyle = '#000000';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';

            // Draw text
            this.ctx.fillText(this.text, this.canvas.width / 2, this.canvas.height / 2);
        }

        isEmpty() {
            return !this.text || this.text.trim() === '';
        }

        getDataURL() {
            if (this.isEmpty()) return null;
            return this.canvas.toDataURL('image/png');
        }

        clear() {
            this.text = '';
            this.textInput.value = '';
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
    }

    // Signature Manager - handles all three methods
    class SignatureManager {
        constructor() {
            this.drawMethod = null;
            this.uploadMethod = null;
            this.typeMethod = null;
            this.activeMethod = 'draw';
        }

        init() {
            // Initialize all methods
            const canvas = document.getElementById('signature-pad');
            if (canvas) {
                this.drawMethod = new SignaturePad(canvas);
            }

            this.uploadMethod = new SignatureUpload();
            this.typeMethod = new SignatureType();

            // Tab switching
            const tabs = document.querySelectorAll('.signature-tabs .nav-link');
            tabs.forEach(tab => {
                tab.addEventListener('click', (e) => {
                    const target = e.currentTarget.getAttribute('href');
                    if (target === '#draw-panel') this.activeMethod = 'draw';
                    else if (target === '#upload-panel') this.activeMethod = 'upload';
                    else if (target === '#type-panel') this.activeMethod = 'type';
                });
            });
        }

        getActiveMethod() {
            switch (this.activeMethod) {
                case 'draw':
                    return this.drawMethod;
                case 'upload':
                    return this.uploadMethod;
                case 'type':
                    return this.typeMethod;
                default:
                    return this.drawMethod;
            }
        }

        isEmpty() {
            const method = this.getActiveMethod();
            return method ? method.isEmpty() : true;
        }

        getDataURL() {
            const method = this.getActiveMethod();
            return method ? method.getDataURL() : null;
        }

        clear() {
            const method = this.getActiveMethod();
            if (method && method.clear) {
                method.clear();
            }
        }
    }

    // Initialize signature manager when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        const canvas = document.getElementById('signature-pad');

        if (!canvas) return;

        // Create signature manager instance
        window.signatureManager = new SignatureManager();
        window.signatureManager.init();

        // Keep backward compatibility
        window.signaturePad = window.signatureManager.drawMethod;

        // Clear button
        const clearBtn = document.getElementById('btn-clear-signature');
        if (clearBtn) {
            clearBtn.addEventListener('click', function() {
                window.signatureManager.clear();
            });
        }

        // Floating sign button - scroll to signature section
        const floatingBtn = document.getElementById('btn-floating-sign');
        if (floatingBtn) {
            floatingBtn.addEventListener('click', function() {
                const signatureCard = document.querySelector('.signature-card');
                if (signatureCard) {
                    signatureCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    // Focus on canvas after scroll
                    setTimeout(() => {
                        canvas.focus();
                    }, 500);
                }
            });
        }

        // Sign button
        const signBtn = document.getElementById('btn-sign-contract');
        if (signBtn) {
            signBtn.addEventListener('click', async function() {
                if (window.signatureManager.isEmpty()) {
                    // Show confirmation dialog in French
                    alert('Veuillez fournir votre signature avant de signer le contrat.');
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
                    // Get signature data from active method
                    const signatureData = window.signatureManager.getDataURL();

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
