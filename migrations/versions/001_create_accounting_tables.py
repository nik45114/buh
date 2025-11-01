"""Create accounting tables

Revision ID: 001
Revises:
Create Date: 2025-11-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Employees
    op.create_table(
        'employees',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('inn', sa.String(length=12), nullable=True),
        sa.Column('snils', sa.String(length=14), nullable=True),
        sa.Column('passport_series', sa.String(length=4), nullable=True),
        sa.Column('passport_number', sa.String(length=6), nullable=True),
        sa.Column('passport_issued_by', sa.Text(), nullable=True),
        sa.Column('passport_issue_date', sa.Date(), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('birth_place', sa.Text(), nullable=True),
        sa.Column('registration_address', sa.Text(), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('employment_type', sa.String(length=20), nullable=True),
        sa.Column('hire_date', sa.Date(), nullable=True),
        sa.Column('fire_date', sa.Date(), nullable=True),
        sa.Column('hourly_rate', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint("employment_type IN ('TD', 'GPH', 'OFFER', 'SELF_EMPLOYED')", name='check_employment_type'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('inn')
    )
    op.create_index('idx_employees_inn', 'employees', ['inn'])
    op.create_index('idx_employees_employment_type', 'employees', ['employment_type'])

    # Contracts
    op.create_table(
        'contracts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('contract_type', sa.String(length=20), nullable=False),
        sa.Column('contract_number', sa.String(length=50), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('position', sa.String(length=255), nullable=True),
        sa.Column('salary', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('work_conditions', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint("contract_type IN ('TD', 'GPH', 'OFFER')", name='check_contract_type'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_contracts_employee', 'contracts', ['employee_id'])
    op.create_index('idx_contracts_type', 'contracts', ['contract_type'])
    op.create_index('idx_contracts_number', 'contracts', ['contract_number'])

    # Shifts
    op.create_table(
        'shifts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=True),
        sa.Column('shift_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=True),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.Column('hours_worked', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('revenue', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('expenses', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('imported_from_bot', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('bot_shift_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_shifts_employee', 'shifts', ['employee_id'])
    op.create_index('idx_shifts_date', 'shifts', ['shift_date'])
    op.create_index('idx_shifts_imported', 'shifts', ['imported_from_bot'])
    op.create_index('idx_shifts_bot_id', 'shifts', ['bot_shift_id'], unique=True)

    # Payroll
    op.create_table(
        'payroll',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('period_month', sa.Integer(), nullable=False),
        sa.Column('period_year', sa.Integer(), nullable=False),
        sa.Column('total_hours', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('gross_salary', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('ndfl', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('contributions', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('net_salary', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('payment_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='DRAFT', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint("status IN ('DRAFT', 'APPROVED', 'PAID')", name='check_payroll_status'),
        sa.CheckConstraint('period_month BETWEEN 1 AND 12', name='check_payroll_month'),
        sa.CheckConstraint('period_year >= 2020', name='check_payroll_year'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_payroll_employee', 'payroll', ['employee_id'])
    op.create_index('idx_payroll_period', 'payroll', ['period_year', 'period_month'])
    op.create_index('idx_payroll_status', 'payroll', ['status'])
    op.create_index('idx_payroll_unique', 'payroll', ['employee_id', 'period_year', 'period_month'], unique=True)

    # Tax Payments
    op.create_table(
        'tax_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tax_type', sa.String(length=50), nullable=False),
        sa.Column('period_quarter', sa.Integer(), nullable=True),
        sa.Column('period_year', sa.Integer(), nullable=False),
        sa.Column('base_amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('tax_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('payment_deadline', sa.Date(), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='CALCULATED', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint("tax_type IN ('USN', 'NDFL', 'PENSION', 'MEDICAL', 'SOCIAL', 'INJURY')", name='check_tax_type'),
        sa.CheckConstraint("status IN ('CALCULATED', 'PAID', 'OVERDUE')", name='check_tax_payment_status'),
        sa.CheckConstraint('period_quarter BETWEEN 1 AND 4', name='check_tax_quarter'),
        sa.CheckConstraint('period_year >= 2020', name='check_tax_year'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_tax_payments_type', 'tax_payments', ['tax_type'])
    op.create_index('idx_tax_payments_status', 'tax_payments', ['status'])
    op.create_index('idx_tax_payments_period', 'tax_payments', ['period_year', 'period_quarter'])
    op.create_index('idx_tax_payments_deadline', 'tax_payments', ['payment_deadline'])

    # Reports
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_type', sa.String(length=50), nullable=False),
        sa.Column('period_quarter', sa.Integer(), nullable=True),
        sa.Column('period_year', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('xml_path', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='DRAFT', nullable=False),
        sa.Column('sent_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint("report_type IN ('USN_DECLARATION', 'RSV', 'SZV_M', 'EFS_1', 'KUDIR')", name='check_report_type'),
        sa.CheckConstraint("status IN ('DRAFT', 'READY', 'SENT', 'ACCEPTED')", name='check_report_status'),
        sa.CheckConstraint('period_quarter BETWEEN 1 AND 4', name='check_report_quarter'),
        sa.CheckConstraint('period_year >= 2020', name='check_report_year'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_reports_type', 'reports', ['report_type'])
    op.create_index('idx_reports_status', 'reports', ['status'])
    op.create_index('idx_reports_period', 'reports', ['period_year', 'period_quarter'])

    # Reminders
    op.create_table(
        'reminders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reminder_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('priority', sa.String(length=20), server_default='MEDIUM', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint("priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name='check_reminder_priority'),
        sa.CheckConstraint("status IN ('PENDING', 'SENT', 'COMPLETED')", name='check_reminder_status'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_reminders_type', 'reminders', ['reminder_type'])
    op.create_index('idx_reminders_status', 'reminders', ['status'])
    op.create_index('idx_reminders_priority', 'reminders', ['priority'])
    op.create_index('idx_reminders_due_date', 'reminders', ['due_date'])


def downgrade() -> None:
    op.drop_table('reminders')
    op.drop_table('reports')
    op.drop_table('tax_payments')
    op.drop_table('payroll')
    op.drop_table('shifts')
    op.drop_table('contracts')
    op.drop_table('employees')
