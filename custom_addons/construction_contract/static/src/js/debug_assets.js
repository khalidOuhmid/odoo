/**
 * Debug script to verify asset loading
 * Add this temporarily to diagnose loading issues
 */

console.log('=== Asset Loading Debug ===');
console.log('PDF.js loaded:', typeof pdfjsLib !== 'undefined');
console.log('PDFPageViewer loaded:', typeof PDFPageViewer !== 'undefined');
console.log('PageValidator loaded:', typeof PageValidator !== 'undefined');

if (typeof pdfjsLib !== 'undefined') {
    console.log('PDF.js version:', pdfjsLib.version);
    console.log('PDF.js worker src:', pdfjsLib.GlobalWorkerOptions.workerSrc);
}

if (typeof window !== 'undefined') {
    const keys = Object.keys(window).filter(k => 
        k.toLowerCase().includes('pdf') || 
        k.toLowerCase().includes('signature') ||
        k.toLowerCase().includes('validator')
    );
    console.log('Window objects related to PDF/signature:', keys);
}

console.log('=== End Asset Loading Debug ===');


