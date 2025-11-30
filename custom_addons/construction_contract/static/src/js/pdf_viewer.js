/**
 * PDF Viewer with Page-by-Page Navigation
 * Uses PDF.js to render one page at a time
 */

(function() {
    'use strict';

    class PDFPageViewer {
        constructor(containerId, pdfUrl) {
            this.container = document.getElementById(containerId);
            if (!this.container) {
                console.error('PDF container not found:', containerId);
                return;
            }

            this.pdfUrl = pdfUrl;
            this.pdfDoc = null;
            this.currentPage = 1;
            this.totalPages = 0;
            this.pageRendering = false;
            this.pageNumPending = null;
            this.scale = 1.5;
            this.defaultScale = 1.5;
            this.minScale = 0.5;
            this.maxScale = 3.0;
            this.scaleStep = 0.25;
            this.canvas = null;
            this.ctx = null;

            // Check if PDF.js is loaded
            if (typeof pdfjsLib === 'undefined') {
                console.error('PDF.js library not loaded!');
                this.showError('PDF.js library not loaded. Please refresh the page.');
                return;
            }

            // Initialize PDF.js worker from CDN (worker path is set in template)
            // If not set, set it to CDN
            if (!pdfjsLib.GlobalWorkerOptions.workerSrc || 
                pdfjsLib.GlobalWorkerOptions.workerSrc.includes('construction_contract')) {
                const workerPath = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
                console.log('Setting PDF.js worker to:', workerPath);
                pdfjsLib.GlobalWorkerOptions.workerSrc = workerPath;
            }

            this.init();
            this.bindZoomControls();
        }

        async init() {
            try {
                // Create canvas element
                this.canvas = document.createElement('canvas');
                this.canvas.style.width = '100%';
                this.canvas.style.height = 'auto';
                this.canvas.style.border = '1px solid #ddd';
                this.ctx = this.canvas.getContext('2d');
                
                // Clear container and add canvas
                this.container.innerHTML = '';
                this.container.appendChild(this.canvas);

                // Load PDF
                console.log('Loading PDF from:', this.pdfUrl);
                console.log('Using PDF.js version:', pdfjsLib.version);
                
                const loadingTask = pdfjsLib.getDocument({
                    url: this.pdfUrl,
                });

                // Add progress listener
                loadingTask.onProgress = (progress) => {
                    console.log('Loading progress:', Math.round((progress.loaded / progress.total) * 100) + '%');
                };

                this.pdfDoc = await loadingTask.promise;
                this.totalPages = this.pdfDoc.numPages;

                console.log(`PDF loaded successfully: ${this.totalPages} pages`);

                // Update UI
                const totalPagesEl = document.getElementById('total-pages');
                if (totalPagesEl) {
                    totalPagesEl.textContent = this.totalPages;
                }
                
                // Render first page
                this.renderPage(1);

                // Emit event
                window.dispatchEvent(new CustomEvent('pdf:loaded', { 
                    detail: { totalPages: this.totalPages } 
                }));

            } catch (error) {
                console.error('Error loading PDF:', error);
                this.showError('Error loading PDF: ' + error.message);
            }
        }

        showError(message) {
            this.container.innerHTML = `
                <div class="alert alert-danger m-3">
                    <i class="fa fa-exclamation-triangle"></i>
                    ${message}
                </div>
            `;
        }

        async renderPage(pageNum) {
            if (this.pageRendering) {
                this.pageNumPending = pageNum;
                return;
            }

            this.pageRendering = true;
            this.currentPage = pageNum;

            try {
                console.log('Rendering page', pageNum);
                
                // Get page
                const page = await this.pdfDoc.getPage(pageNum);
                
                // Calculate viewport
                const viewport = page.getViewport({ scale: this.scale });
                
                // Set canvas dimensions
                this.canvas.height = viewport.height;
                this.canvas.width = viewport.width;

                // Render page
                const renderContext = {
                    canvasContext: this.ctx,
                    viewport: viewport
                };

                await page.render(renderContext).promise;

                console.log('Page rendered:', pageNum);

                // Update current page display
                document.getElementById('current-page').textContent = pageNum;

                // Emit page change event
                window.dispatchEvent(new CustomEvent('pdf:pageChanged', { 
                    detail: { 
                        currentPage: this.currentPage,
                        totalPages: this.totalPages 
                    } 
                }));

            } catch (error) {
                console.error('Error rendering page:', error);
            } finally {
                this.pageRendering = false;

                // If another page was requested, render it
                if (this.pageNumPending !== null) {
                    const pending = this.pageNumPending;
                    this.pageNumPending = null;
                    this.renderPage(pending);
                }
            }
        }

        nextPage() {
            if (this.currentPage >= this.totalPages) {
                return false;
            }
            this.renderPage(this.currentPage + 1);
            return true;
        }

        prevPage() {
            if (this.currentPage <= 1) {
                return false;
            }
            this.renderPage(this.currentPage - 1);
            return true;
        }

        goToPage(pageNum) {
            if (pageNum < 1 || pageNum > this.totalPages) {
                return false;
            }
            this.renderPage(pageNum);
            return true;
        }

        getCurrentPage() {
            return this.currentPage;
        }

        getTotalPages() {
            return this.totalPages;
        }

        bindZoomControls() {
            // Zoom in button
            const zoomInBtn = document.getElementById('btn-zoom-in');
            if (zoomInBtn) {
                zoomInBtn.addEventListener('click', () => this.zoomIn());
            }

            // Zoom out button
            const zoomOutBtn = document.getElementById('btn-zoom-out');
            if (zoomOutBtn) {
                zoomOutBtn.addEventListener('click', () => this.zoomOut());
            }

            // Zoom reset button
            const zoomResetBtn = document.getElementById('btn-zoom-reset');
            if (zoomResetBtn) {
                zoomResetBtn.addEventListener('click', () => this.zoomReset());
            }
        }

        zoomIn() {
            if (this.scale < this.maxScale) {
                this.scale += this.scaleStep;
                this.renderPage(this.currentPage);
                console.log('Zoomed in to:', this.scale);
            }
        }

        zoomOut() {
            if (this.scale > this.minScale) {
                this.scale -= this.scaleStep;
                this.renderPage(this.currentPage);
                console.log('Zoomed out to:', this.scale);
            }
        }

        zoomReset() {
            this.scale = this.defaultScale;
            this.renderPage(this.currentPage);
            console.log('Zoom reset to:', this.scale);
        }
    }

    // Export to window
    window.PDFPageViewer = PDFPageViewer;

})();
