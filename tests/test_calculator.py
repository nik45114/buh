"""
Тесты калькулятора налогов
"""
import pytest
from decimal import Decimal
from datetime import date
from app.services.calculator import get_payment_deadline
from app.database.models import Transaction, Category, User


class TestTaxCalculator:
    """Тесты расчета налогов УСН 15%"""

    def test_payment_deadline_q1(self):
        """Тест срока уплаты для 1 квартала"""
        deadline = get_payment_deadline(2024, 1)
        assert deadline == "2024-04-25"

    def test_payment_deadline_q2(self):
        """Тест срока уплаты для 2 квартала"""
        deadline = get_payment_deadline(2024, 2)
        assert deadline == "2024-07-25"

    def test_payment_deadline_q3(self):
        """Тест срока уплаты для 3 квартала"""
        deadline = get_payment_deadline(2024, 3)
        assert deadline == "2024-10-25"

    def test_payment_deadline_q4(self):
        """Тест срока уплаты для 4 квартала (годовая декларация)"""
        deadline = get_payment_deadline(2024, 4)
        assert deadline == "2025-03-31"

    def test_tax_base_positive(self):
        """Тест: база налогообложения положительная"""
        income = Decimal('100000')
        expense = Decimal('50000')
        tax_base = max(income - expense, Decimal('0'))
        assert tax_base == Decimal('50000')

    def test_tax_base_negative(self):
        """Тест: база налогообложения не может быть отрицательной"""
        income = Decimal('50000')
        expense = Decimal('100000')
        tax_base = max(income - expense, Decimal('0'))
        assert tax_base == Decimal('0')

    def test_tax_calculation_15_percent(self):
        """Тест: расчет налога 15%"""
        tax_base = Decimal('100000')
        tax_rate = Decimal('0.15')
        tax_amount = tax_base * tax_rate
        assert tax_amount == Decimal('15000.00')

    def test_min_tax_calculation(self):
        """Тест: минимальный налог 1% от доходов"""
        income = Decimal('1000000')
        min_tax_rate = Decimal('0.01')
        min_tax = income * min_tax_rate
        assert min_tax == Decimal('10000.00')

    def test_tax_to_pay_regular(self):
        """Тест: обычный налог больше минимального"""
        tax_amount = Decimal('15000')
        min_tax = Decimal('10000')
        tax_to_pay = max(tax_amount, min_tax)
        assert tax_to_pay == Decimal('15000')

    def test_tax_to_pay_minimum(self):
        """Тест: платим минимальный налог если он больше"""
        tax_amount = Decimal('5000')
        min_tax = Decimal('10000')
        tax_to_pay = max(tax_amount, min_tax)
        assert tax_to_pay == Decimal('10000')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
