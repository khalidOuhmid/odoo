/** @odoo-module */

// In Odoo 17/18, typically views use standard arch parsing or a generic parser.
// We can extend a simpler base or just a plain object if we don't need complex legacy XML parsing.
// For now, let's remove the broken import and just make a class that matches the interface.

export class GanttArchParser {
    parse(arch) {
        return {
            // Parse XML attributes here
            limit: 80,
        };
    }
}
