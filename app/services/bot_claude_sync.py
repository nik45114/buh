"""
Сервис синхронизации с Bot_Claude
"""
import sqlite3
import logging
from typing import List, Dict, Optional
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class BotClaudeSync:
    """Синхронизация данных из Bot_Claude"""

    def __init__(self, db_path: str = "/opt/club_assistant/knowledge.db"):
        self.db_path = db_path

    def is_available(self) -> bool:
        """Проверка доступности БД Bot_Claude"""
        return Path(self.db_path).exists()

    def fetch_shifts(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Получить смены из Bot_Claude за период

        Структура БД Bot_Claude может отличаться,
        поэтому здесь используется гибкий подход
        """
        if not self.is_available():
            logger.warning(f"Bot_Claude database not found at {self.db_path}")
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Попытка извлечь смены
            # Адаптировать запрос под реальную структуру БД Bot_Claude
            query = """
            SELECT
                id as shift_id,
                date,
                shift_type,
                employee_name,
                hours_worked,
                revenue_cash,
                revenue_cashless,
                revenue_qr,
                expenses,
                notes
            FROM shifts
            WHERE date BETWEEN ? AND ?
            ORDER BY date DESC
            """

            cursor.execute(query, (start_date.isoformat(), end_date.isoformat()))
            rows = cursor.fetchall()

            shifts = []
            for row in rows:
                shifts.append({
                    'bot_shift_id': row['shift_id'],
                    'shift_date': datetime.strptime(row['date'], '%Y-%m-%d').date(),
                    'employee_name': row['employee_name'],
                    'hours_worked': row['hours_worked'] if row['hours_worked'] else None,
                    'revenue': (
                        (row['revenue_cash'] or 0) +
                        (row['revenue_cashless'] or 0) +
                        (row['revenue_qr'] or 0)
                    ),
                    'expenses': row['expenses'] if row['expenses'] else None,
                    'notes': row['notes']
                })

            conn.close()
            logger.info(f"Fetched {len(shifts)} shifts from Bot_Claude")
            return shifts

        except sqlite3.Error as e:
            logger.error(f"Error fetching shifts from Bot_Claude: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []

    def fetch_employees(self) -> List[Dict]:
        """Получить список сотрудников из Bot_Claude"""
        if not self.is_available():
            logger.warning(f"Bot_Claude database not found at {self.db_path}")
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
            SELECT DISTINCT
                employee_name,
                phone,
                hourly_rate
            FROM employees
            WHERE is_active = 1
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            employees = []
            for row in rows:
                employees.append({
                    'full_name': row['employee_name'],
                    'phone': row['phone'] if row['phone'] else None,
                    'hourly_rate': row['hourly_rate'] if row['hourly_rate'] else None
                })

            conn.close()
            logger.info(f"Fetched {len(employees)} employees from Bot_Claude")
            return employees

        except sqlite3.Error as e:
            logger.error(f"Error fetching employees from Bot_Claude: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []

    def get_shift_reports(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Получить отчеты о сменах в формате для shift_reports таблицы
        """
        if not self.is_available():
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
            SELECT
                date,
                shift_type,
                cash_fact,
                cash_plan,
                cashless_fact,
                qr_payments,
                safe,
                expenses_json,
                workers_list,
                equipment_issues
            FROM shift_reports
            WHERE date BETWEEN ? AND ?
            ORDER BY date DESC
            """

            cursor.execute(query, (start_date.isoformat(), end_date.isoformat()))
            rows = cursor.fetchall()

            reports = []
            for row in rows:
                reports.append({
                    'date': datetime.strptime(row['date'], '%Y-%m-%d').date(),
                    'shift': row['shift_type'],
                    'cash_fact': row['cash_fact'],
                    'cash_plan': row['cash_plan'],
                    'cashless_fact': row['cashless_fact'],
                    'qr_payments': row['qr_payments'],
                    'safe': row['safe'],
                    'expenses': row['expenses_json'],
                    'workers': row['workers_list'].split(',') if row['workers_list'] else [],
                    'equipment_issues': row['equipment_issues'].split(',') if row['equipment_issues'] else []
                })

            conn.close()
            logger.info(f"Fetched {len(reports)} shift reports from Bot_Claude")
            return reports

        except sqlite3.Error as e:
            logger.error(f"Error fetching shift reports: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []
