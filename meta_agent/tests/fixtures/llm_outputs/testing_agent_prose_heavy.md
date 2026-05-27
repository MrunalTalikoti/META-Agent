I'll create comprehensive tests for the order processing module. The tests follow the Arrange-Act-Assert pattern and cover both happy paths and edge cases.

Here are the key scenarios we need to test:
- Creating an order with valid items
- Handling empty cart
- Applying discount codes
- Stock validation
- Price calculation with tax

Let me write the tests:

```python
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from app.orders import OrderService, InsufficientStockError


class TestOrderService:
    """Tests for the order processing pipeline."""

    @pytest.fixture
    def mock_inventory(self):
        inv = MagicMock()
        inv.check_stock.return_value = True
        inv.reserve.return_value = True
        return inv

    @pytest.fixture
    def service(self, mock_inventory):
        return OrderService(inventory=mock_inventory)

    def test_create_order_with_valid_items(self, service):
        items = [
            {"product_id": 1, "quantity": 2, "price": Decimal("29.99")},
            {"product_id": 2, "quantity": 1, "price": Decimal("49.99")},
        ]

        order = service.create_order(user_id=42, items=items)

        assert order.status == "pending"
        assert order.total == Decimal("109.97")
        assert len(order.items) == 2

    def test_create_order_empty_cart_raises(self, service):
        with pytest.raises(ValueError, match="at least one item"):
            service.create_order(user_id=42, items=[])

    def test_create_order_checks_stock(self, service, mock_inventory):
        mock_inventory.check_stock.return_value = False

        with pytest.raises(InsufficientStockError):
            service.create_order(
                user_id=42,
                items=[{"product_id": 1, "quantity": 100, "price": Decimal("9.99")}],
            )

    def test_apply_discount_percentage(self, service):
        items = [{"product_id": 1, "quantity": 1, "price": Decimal("100.00")}]
        order = service.create_order(user_id=42, items=items, discount_code="SAVE20")

        assert order.discount_applied == Decimal("20.00")
        assert order.total == Decimal("80.00")

    def test_calculate_tax(self, service):
        items = [{"product_id": 1, "quantity": 1, "price": Decimal("100.00")}]
        order = service.create_order(user_id=42, items=items, tax_rate=Decimal("0.08"))

        assert order.tax == Decimal("8.00")
        assert order.total == Decimal("108.00")
```

These tests ensure the order service correctly handles item validation, stock checks, discounts, and tax calculation. I used `Decimal` for monetary amounts to avoid floating-point precision issues.
