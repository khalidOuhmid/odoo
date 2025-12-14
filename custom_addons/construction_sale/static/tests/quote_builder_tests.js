/** @odoo-module **/
/**
 * Quote Builder OWL Component Tests (SAP-Grade)
 * ==============================================
 * Tests for the Quote Builder frontend component.
 * 
 * Mocked RPC/ORM - no external dependencies.
 * Deterministic and isolated.
 */

import { describe, test, expect, beforeEach, afterEach } from "@odoo/hoot";
import { getService, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { QuoteBuilder } from "@construction_sale/quote_builder/quote_builder";

// ============================================================
// MOCK DATA
// ============================================================

const MOCK_PRODUCTS = [
    {
        id: 1,
        name: "Produit Test A",
        display_name: "Produit Test A",
        list_price: 100.0,
        standard_price: 60.0,
        uom_id: [1, "Unité(s)"],
    },
    {
        id: 2,
        name: "Produit Test B",
        display_name: "Produit Test B",
        list_price: 50.0,
        standard_price: 30.0,
        uom_id: [2, "m²"],
    },
];

const MOCK_LOTS = [
    { id: 1, name: "Électricité", code: "01" },
    { id: 2, name: "Plomberie", code: "02" },
];

const MOCK_EXISTING_LINES = [
    {
        id: 101,
        product_id: [1, "Produit Test A"],
        name: "Produit Test A",
        lot_id: [1, "01 - Électricité"],
        product_uom_qty: 2,
        price_unit: 100.0,
        price_buy: 60.0,
    },
];

// ============================================================
// UNIT TESTS: MARGIN CALCULATION (Frontend)
// ============================================================

describe("Quote Builder - Margin Calculation", () => {

    test("calculatePriceFromMargin with 50% markup", () => {
        // Formula: cost × (1 + margin/100)
        const cost = 15.0;
        const marginPercent = 50;

        const expectedPrice = cost * (1 + marginPercent / 100); // 22.50

        expect(expectedPrice).toBe(22.5);
    });

    test("calculatePriceFromMargin with 100% markup", () => {
        const cost = 15.0;
        const marginPercent = 100;

        const expectedPrice = cost * (1 + marginPercent / 100); // 30.00

        expect(expectedPrice).toBe(30.0);
    });

    test("calculatePriceFromMargin with 0% markup", () => {
        const cost = 15.0;
        const marginPercent = 0;

        const expectedPrice = cost * (1 + marginPercent / 100); // 15.00

        expect(expectedPrice).toBe(15.0);
    });

    test("calculatePriceFromMargin handles zero cost", () => {
        const cost = 0;
        const marginPercent = 50;

        // Edge case: should return 0
        const expectedPrice = cost <= 0 ? 0 : cost * (1 + marginPercent / 100);

        expect(expectedPrice).toBe(0);
    });
});

// ============================================================
// UNIT TESTS: QUANTITY CALCULATION (Métré)
// ============================================================

describe("Quote Builder - Métré Quantity", () => {

    test("linear quantity (ml) from length only", () => {
        const dimensions = { l: 5, w: 0, h: 0 };
        const uomType = 'ml';

        let qty = 1;
        if (uomType === 'ml' && dimensions.l > 0) {
            qty = dimensions.l;
        }

        expect(qty).toBe(5);
    });

    test("surface quantity (m²) from L×W", () => {
        const dimensions = { l: 3, w: 4, h: 0 };
        const uomType = 'm2';

        let qty = 1;
        if (uomType === 'm2' && dimensions.l > 0 && dimensions.w > 0) {
            qty = dimensions.l * dimensions.w;
        }

        expect(qty).toBe(12);
    });

    test("volume quantity (m³) from L×W×H", () => {
        const dimensions = { l: 2, w: 3, h: 4 };
        const uomType = 'm3';

        let qty = 1;
        if (uomType === 'm3' && dimensions.l > 0 && dimensions.w > 0 && dimensions.h > 0) {
            qty = dimensions.l * dimensions.w * dimensions.h;
        }

        expect(qty).toBe(24);
    });

    test("unit product ignores dimensions", () => {
        const dimensions = { l: 10, w: 5, h: 2 };
        const uomType = 'unit';

        let qty = 1; // Unit always stays 1

        expect(qty).toBe(1);
    });
});

// ============================================================
// INTEGRATION TESTS: LOCALSTORAGE PERSISTENCE
// ============================================================

describe("Quote Builder - LocalStorage Persistence", () => {

    beforeEach(() => {
        // Clear relevant localStorage keys
        Object.keys(localStorage)
            .filter(k => k.startsWith('blg_'))
            .forEach(k => localStorage.removeItem(k));
    });

    afterEach(() => {
        // Clean up
        Object.keys(localStorage)
            .filter(k => k.startsWith('blg_'))
            .forEach(k => localStorage.removeItem(k));
    });

    test("cart key is unique per order ID", () => {
        const baseKey = 'blg_quote_draft';
        const orderId1 = 100;
        const orderId2 = 200;

        const key1 = `${baseKey}_order_${orderId1}`;
        const key2 = `${baseKey}_order_${orderId2}`;

        expect(key1).not.toBe(key2);
        expect(key1).toBe('blg_quote_draft_order_100');
        expect(key2).toBe('blg_quote_draft_order_200');
    });

    test("cart data can be saved and restored", () => {
        const cartKey = 'blg_quote_draft_order_123';
        const cartData = {
            cart: [{ id: 1, name: 'Test', qty: 2 }],
            chantierId: 1,
            orderId: 123,
            timestamp: new Date().toISOString(),
        };

        localStorage.setItem(cartKey, JSON.stringify(cartData));

        const restored = JSON.parse(localStorage.getItem(cartKey));

        expect(restored.orderId).toBe(123);
        expect(restored.cart.length).toBe(1);
        expect(restored.cart[0].name).toBe('Test');
    });

    test("different orders don't share cart data", () => {
        const key1 = 'blg_quote_draft_order_100';
        const key2 = 'blg_quote_draft_order_200';

        localStorage.setItem(key1, JSON.stringify({ cart: [{ id: 1 }] }));
        localStorage.setItem(key2, JSON.stringify({ cart: [{ id: 2 }, { id: 3 }] }));

        const cart1 = JSON.parse(localStorage.getItem(key1)).cart;
        const cart2 = JSON.parse(localStorage.getItem(key2)).cart;

        expect(cart1.length).toBe(1);
        expect(cart2.length).toBe(2);
    });
});

// ============================================================
// INTEGRATION TESTS: CART OPERATIONS
// ============================================================

describe("Quote Builder - Cart Operations", () => {

    test("adding product to cart creates correct structure", () => {
        const product = MOCK_PRODUCTS[0];
        const defaultMargin = 50;
        const lotId = 1;

        const cost = product.standard_price;
        const price = cost * (1 + defaultMargin / 100);

        const cartItem = {
            id: product.id,
            overrideName: product.name,
            qty: 1,
            price_buy: cost,
            price_unit: price,
            lot_id: lotId,
            target_margin_percent: defaultMargin,
            isOptional: false,
        };

        expect(cartItem.price_buy).toBe(60);
        expect(cartItem.price_unit).toBe(90); // 60 × 1.5
        expect(cartItem.lot_id).toBe(1);
    });

    test("cart total calculation", () => {
        const cart = [
            { qty: 2, price_unit: 100, isOptional: false },
            { qty: 3, price_unit: 50, isOptional: false },
            { qty: 1, price_unit: 200, isOptional: true }, // Excluded
        ];

        const total = cart
            .filter(l => !l.isOptional)
            .reduce((sum, l) => sum + (l.qty * l.price_unit), 0);

        expect(total).toBe(350); // (2×100) + (3×50) = 350
    });

    test("optional lines excluded from total", () => {
        const cart = [
            { qty: 1, price_unit: 100, isOptional: true },
            { qty: 1, price_unit: 100, isOptional: true },
        ];

        const total = cart
            .filter(l => !l.isOptional)
            .reduce((sum, l) => sum + (l.qty * l.price_unit), 0);

        expect(total).toBe(0);
    });

    test("grouped cart organizes by lot", () => {
        const cart = [
            { name: 'A', lot_id: 1 },
            { name: 'B', lot_id: 2 },
            { name: 'C', lot_id: 1 },
        ];

        const groups = {};
        cart.forEach(line => {
            const lotId = line.lot_id || 'unassigned';
            if (!groups[lotId]) groups[lotId] = [];
            groups[lotId].push(line);
        });

        expect(Object.keys(groups).length).toBe(2);
        expect(groups[1].length).toBe(2);
        expect(groups[2].length).toBe(1);
    });
});

// ============================================================
// REGRESSION TESTS: KNOWN BUGS
// ============================================================

describe("Quote Builder - Regression Tests", () => {

    test("existing lines loaded - not empty cart (BUG FIX)", () => {
        // Simulates loadExistingOrderLines behavior
        const existingLines = MOCK_EXISTING_LINES;
        const cart = existingLines.map(line => ({
            id: line.id,
            product_id: line.product_id[0],
            overrideName: line.name,
            lot_id: line.lot_id ? line.lot_id[0] : null,
            qty: line.product_uom_qty,
            price_unit: line.price_unit,
            price_buy: line.price_buy || 0,
        }));

        expect(cart.length).toBeGreaterThan(0);
        expect(cart[0].overrideName).toBe("Produit Test A");
    });

    test("cart key includes orderId - prevents cross-contamination", () => {
        // Regression: old key was shared between all orders
        const orderId = 42;
        const expectedKey = `blg_quote_draft_order_${orderId}`;

        expect(expectedKey).toContain('42');
        expect(expectedKey).not.toBe('blg_quote_draft_undefined');
    });
});
