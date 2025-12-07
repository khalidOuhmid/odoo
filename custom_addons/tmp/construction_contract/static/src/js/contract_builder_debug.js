/**
 * Debug utilities for Contract Builder
 * Add this to check what's happening in the browser console
 */

(function() {
    'use strict';

    window.debugContractBuilder = function() {
    console.log("=".repeat(60));
    console.log("CONTRACT BUILDER DEBUG");
    console.log("=".repeat(60));
    
    // Check if container exists
    const container = document.getElementById("contract-live-builder");
    console.log("\n1. Container:", container ? "✓ Found" : "✗ Not found");
    
    if (!container) {
        console.error("Container #contract-live-builder not found in DOM!");
        return;
    }
    
    // Check config
    const config = container.dataset.config;
    console.log("\n2. Config data attribute:", config ? "✓ Present" : "✗ Missing");
    if (config) {
        try {
            const parsed = JSON.parse(config);
            console.log("   Parsed config:", parsed);
        } catch (e) {
            console.error("   Config parse error:", e);
        }
    }
    
    // Check form inputs
    console.log("\n3. Form Elements:");
    const subcontractor = document.querySelector("select[name='subcontractor_id']");
    const lots = document.querySelector("select[name='lot_ids']");
    const template = document.querySelector("select[name='template_id']");
    const iframe = document.getElementById("builder-preview-frame");
    
    console.log("   - Subcontractor select:", subcontractor ? "✓" : "✗");
    console.log("     Value:", subcontractor?.value || "empty");
    console.log("     Options:", subcontractor?.options.length || 0);
    
    console.log("   - Lots select:", lots ? "✓" : "✗");
    console.log("     Selected:", lots?.selectedOptions.length || 0);
    console.log("     Values:", Array.from(lots?.selectedOptions || []).map(o => o.value));
    
    console.log("   - Template select:", template ? "✓" : "✗");
    console.log("     Value:", template?.value || "empty");
    console.log("     Options:", template?.options.length || 0);
    
    console.log("   - Preview iframe:", iframe ? "✓" : "✗");
    
    // Check builder instance
    console.log("\n4. Builder Instance:");
    console.log("   window.contractBuilder:", window.contractBuilder ? "✓ Exists" : "✗ Not created");
    
    if (window.contractBuilder) {
        console.log("   Config:", window.contractBuilder.config);
        console.log("   Manual edit:", window.contractBuilder.manualEdit);
    }
    
    // Test payload generation
    if (window.contractBuilder) {
        console.log("\n5. Current Payload:");
        try {
            const payload = window.contractBuilder._getPayload();
            console.log("   Payload:", payload);
            
            // Check validation
            const missing = [];
            if (!payload.subcontractor_id) missing.push("subcontractor");
            if (!payload.lot_ids || payload.lot_ids.length === 0) missing.push("lots");
            if (!payload.template_id) missing.push("template");
            
            if (missing.length > 0) {
                console.warn("   ⚠ Validation failed, missing:", missing.join(", "));
            } else {
                console.log("   ✓ Validation passed");
            }
        } catch (e) {
            console.error("   Error getting payload:", e);
        }
    }
    
    // Test manual preview trigger
    console.log("\n6. Test Actions:");
    console.log("   To test preview manually, run:");
    console.log("   > window.contractBuilder._refreshPreview()");
    
    console.log("\n" + "=".repeat(60));
    };

    // Auto-run debug on page load
    setTimeout(() => {
        if (document.getElementById("contract-live-builder")) {
            console.log("\n🔍 Auto-running debug...");
            window.debugContractBuilder();
            
            console.log("\n💡 To debug again, run: window.debugContractBuilder()");
        }
    }, 1000);

})();

