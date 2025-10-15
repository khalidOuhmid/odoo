# Construction Base - Test Suite

This directory contains comprehensive unit tests for the `construction_base` module, specifically for the `Chantier` model and related functionality.

## Test Structure

The test suite is organized into focused test modules:

### 1. `test_chantier_model.py`
Tests core CRUD operations:
- Record creation with automatic reference generation
- Write operations and stage validation control
- SQL constraints (positive cost, surface, progress range)
- Contract date validations
- Copy behavior
- Mail thread integration

**Coverage**: 15 test methods

### 2. `test_chantier_validation.py`
Tests all validation methods (`check_*` methods):
- Reception stage validation
- Visit stage validation
- Quotation sent/accepted stage validation
- Construction progress percentage validations (25%, 50%, 75%, 100%)
- Warranty and warranty retention validations
- Dossier finalization validation

**Coverage**: 28 test methods

### 3. `test_chantier_compute.py`
Tests all computed field methods:
- Chapter name computation
- Duration calculations (planned and actual)
- Construction progression calculation
- Days remaining and deadline status
- Total cost calculation
- Various counters (lots, quotations, orders)
- Order statistics
- Document counts
- Invoice schedule statistics
- Action visibility

**Coverage**: 33 test methods

### 4. `test_chantier_workflow.py`
Tests workflow and stage transitions:
- Forward stage transitions
- Backward stage transitions  
- Validation gates for stage changes
- Progress-based stage transitions
- Automatic actions on stage changes
- Admin bypass functionality
- Stage validation info display

**Coverage**: 20 test methods

### 5. `test_chantier_actions.py`
Tests all action methods:
- View actions (visits, subcontractors, budget, quotations, planning)
- Quotation management actions
- Invoice setup and management actions
- Planning task actions
- Subcontractor contract actions
- Purchase order split actions
- Helper methods

**Coverage**: 32 test methods

## Total Test Coverage

- **Total test methods**: 128+
- **Target coverage**: 100% of public methods
- **Lines covered**: All critical business logic

## Running the Tests

### Run all tests for the module
```bash
odoo-bin -c odoo.conf -d test_db --test-enable --stop-after-init -u construction_base
```

### Run specific test class
```bash
odoo-bin -c odoo.conf -d test_db --test-enable --stop-after-init -u construction_base --test-tags construction_base.TestChantierModel
```

### Run specific test method
```bash
odoo-bin -c odoo.conf -d test_db --test-enable --stop-after-init -u construction_base --test-tags construction_base.TestChantierModel.test_01_create_chantier_with_defaults
```

### Run with coverage report
```bash
coverage run --source=custom_addons/construction_base odoo-bin -c odoo.conf -d test_db --test-enable --stop-after-init -u construction_base
coverage report
coverage html
```

## Test Database Setup

It's recommended to use a dedicated test database:

```bash
# Create test database
createdb test_construction_base

# Initialize with test data
odoo-bin -c odoo.conf -d test_construction_base -i construction_base --stop-after-init
```

## Test Data

Each test class uses `setUpClass` to create reusable test data:
- Test clients
- Test chapters and stages
- Test subcontractors
- Helper methods for creating test chantiers

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitLab CI configuration
test:
  stage: test
  script:
    - odoo-bin -c odoo.conf -d test_db --test-enable --stop-after-init -u construction_base
  coverage: '/TOTAL.*\s+(\d+%)$/'
```

## Best Practices

1. **Isolation**: Each test method is independent and can run in any order
2. **Descriptive names**: Test method names clearly describe what is being tested
3. **Assertions**: Multiple assertions per test for comprehensive validation
4. **Documentation**: Each test has a docstring explaining its purpose
5. **Setup**: Use `setUpClass` for expensive setup operations
6. **Helpers**: Use helper methods to reduce code duplication

## Coverage Goals

- ✅ All `create` and `write` operations
- ✅ All validation methods (`check_*`)
- ✅ All computed fields (`_compute_*`)
- ✅ All action methods (`action_*`)
- ✅ All workflow transitions
- ✅ All constraints
- ✅ Edge cases and error conditions
- ✅ Admin and user permission differences

## Maintenance

When adding new features to the `Chantier` model:

1. Add corresponding test methods
2. Update this README with coverage information
3. Ensure all new code paths are tested
4. Run full test suite to ensure no regressions

## Troubleshooting

### Tests fail with database errors
- Ensure test database exists and is accessible
- Check that all required modules are installed
- Verify database user permissions

### Tests fail with import errors
- Ensure the module is in the addons path
- Check that `__init__.py` files are properly configured
- Verify all dependencies are installed

### Coverage report shows low coverage
- Check that tests are actually running (look for test output)
- Verify source path in coverage command
- Ensure all test files are being discovered

## Additional Resources

- [Odoo Testing Documentation](https://www.odoo.com/documentation/16.0/developer/reference/backend/testing.html)
- [Python unittest Documentation](https://docs.python.org/3/library/unittest.html)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

