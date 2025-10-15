#!/bin/bash
# Test runner script for construction_base module
# This script runs all tests with coverage reporting

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
MODULE_NAME="construction_base"
TEST_DB_NAME="test_construction_base"
ODOO_BIN="${ODOO_BIN:-odoo-bin}"
ODOO_CONF="${ODOO_CONF:-odoo.conf}"
COVERAGE_MIN="${COVERAGE_MIN:-90}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Construction Base - Test Suite Runner${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if odoo-bin exists
if ! command -v $ODOO_BIN &> /dev/null; then
    echo -e "${RED}Error: $ODOO_BIN not found${NC}"
    echo "Please set ODOO_BIN environment variable or ensure odoo-bin is in PATH"
    exit 1
fi

# Check if coverage is installed
if ! command -v coverage &> /dev/null; then
    echo -e "${YELLOW}Warning: coverage not installed${NC}"
    echo "Installing coverage..."
    pip install coverage
fi

echo -e "${YELLOW}Step 1: Preparing test database...${NC}"
# Drop existing test database if it exists
dropdb --if-exists $TEST_DB_NAME 2>/dev/null || true

# Create fresh test database
createdb $TEST_DB_NAME

echo -e "${YELLOW}Step 2: Installing module in test database...${NC}"
$ODOO_BIN -c $ODOO_CONF -d $TEST_DB_NAME -i $MODULE_NAME --stop-after-init --log-level=warn

echo -e "${YELLOW}Step 3: Running tests with coverage...${NC}"
coverage run --rcfile=custom_addons/$MODULE_NAME/.coveragerc \
    $ODOO_BIN -c $ODOO_CONF -d $TEST_DB_NAME \
    --test-enable \
    --stop-after-init \
    -u $MODULE_NAME \
    --log-level=test

echo ""
echo -e "${YELLOW}Step 4: Generating coverage report...${NC}"
coverage report

echo ""
echo -e "${YELLOW}Step 5: Generating HTML coverage report...${NC}"
coverage html --rcfile=custom_addons/$MODULE_NAME/.coveragerc
echo -e "${GREEN}HTML report generated in htmlcov/index.html${NC}"

echo ""
echo -e "${YELLOW}Step 6: Checking coverage threshold...${NC}"
COVERAGE_PERCENT=$(coverage report | grep TOTAL | awk '{print $4}' | sed 's/%//')

if (( $(echo "$COVERAGE_PERCENT >= $COVERAGE_MIN" | bc -l) )); then
    echo -e "${GREEN}✓ Coverage ${COVERAGE_PERCENT}% meets minimum threshold of ${COVERAGE_MIN}%${NC}"
    EXIT_CODE=0
else
    echo -e "${RED}✗ Coverage ${COVERAGE_PERCENT}% below minimum threshold of ${COVERAGE_MIN}%${NC}"
    EXIT_CODE=1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Test suite completed${NC}"
echo -e "${GREEN}========================================${NC}"

# Clean up test database
echo -e "${YELLOW}Cleaning up test database...${NC}"
dropdb $TEST_DB_NAME 2>/dev/null || true

exit $EXIT_CODE

