"""
Data formatting utilities for presenting Excel data in readable formats.

This module provides formatting for numbers, dates, tables, and formulas with
support for both English and Thai formatting conventions.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dateutil import parser as date_parser

from src.models.domain_models import DataType


class DataFormatter:
    """
    Formats Excel data for presentation in natural language answers.
    
    Handles number formatting (currency, percentage, thousands separator),
    date formatting, table creation, and formula explanations.
    """
    
    def __init__(self, language: str = "en"):
        """
        Initialize the data formatter.
        
        Args:
            language: Language code ('en' or 'th')
        """
        self.language = language
    
    def format_number(
        self,
        value: float,
        excel_format: Optional[str] = None,
        precision: Optional[int] = None
    ) -> str:
        """
        Format a number with Excel-style formatting.
        
        Args:
            value: The numeric value
            excel_format: Excel number format string (e.g., "$#,##0.00", "0.00%")
            precision: Number of decimal places (overrides format)
            
        Returns:
            Formatted number string
        """
        if value is None:
            return "N/A"
        
        # Parse Excel format if provided
        if excel_format:
            return self._apply_excel_format(value, excel_format)
        
        # Apply precision if specified
        if precision is not None:
            return self._format_with_precision(value, precision)
        
        # Default formatting
        return self._format_default_number(value)
    
    def format_currency(
        self,
        value: float,
        currency_symbol: str = "$",
        precision: int = 2
    ) -> str:
        """
        Format a number as currency.
        
        Args:
            value: The numeric value
            currency_symbol: Currency symbol to use
            precision: Number of decimal places
            
        Returns:
            Formatted currency string
        """
        if value is None:
            return "N/A"
        
        # Format with thousands separator
        formatted = self._format_with_thousands(value, precision)
        
        # Add currency symbol
        if value < 0:
            return f"-{currency_symbol}{formatted[1:]}"  # Remove negative sign and add after symbol
        return f"{currency_symbol}{formatted}"
    
    def format_percentage(
        self,
        value: float,
        precision: int = 2,
        multiply_by_100: bool = True
    ) -> str:
        """
        Format a number as percentage.
        
        Args:
            value: The numeric value
            precision: Number of decimal places
            multiply_by_100: Whether to multiply by 100 (True if value is 0.15 for 15%)
            
        Returns:
            Formatted percentage string
        """
        if value is None:
            return "N/A"
        
        # Multiply by 100 if needed
        display_value = value * 100 if multiply_by_100 else value
        
        # Format with precision
        formatted = f"{display_value:.{precision}f}"
        
        return f"{formatted}%"
    
    def format_date(
        self,
        value: Any,
        format_style: str = "long"
    ) -> str:
        """
        Format a date in readable format.
        
        Args:
            value: Date value (datetime, string, or Excel serial)
            format_style: 'long', 'short', or 'iso'
            
        Returns:
            Formatted date string
        """
        if value is None:
            return "N/A"
        
        # Convert to datetime if needed
        dt = self._parse_date(value)
        if dt is None:
            return str(value)
        
        # Format based on style and language
        if format_style == "iso":
            return dt.strftime("%Y-%m-%d")
        elif format_style == "short":
            return self._format_date_short(dt)
        else:  # long
            return self._format_date_long(dt)
    
    def format_table(
        self,
        rows: List[Dict[str, Any]],
        headers: Optional[List[str]] = None,
        max_rows: int = 20,
        column_formats: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Format data as a Markdown table.
        
        Args:
            rows: List of row dictionaries
            headers: Optional list of headers (uses keys from first row if not provided)
            max_rows: Maximum number of rows to display
            column_formats: Optional Excel formats for specific columns
            
        Returns:
            Markdown table string
        """
        if not rows:
            return "No data available."
        
        # Get headers
        if headers is None:
            headers = list(rows[0].keys())
        
        # Limit rows
        display_rows = rows[:max_rows]
        truncated = len(rows) > max_rows
        
        # Format cell values
        formatted_rows = []
        for row in display_rows:
            formatted_row = {}
            for header in headers:
                value = row.get(header)
                col_format = column_formats.get(header) if column_formats else None
                formatted_row[header] = self._format_cell_value(value, col_format)
            formatted_rows.append(formatted_row)
        
        # Build Markdown table
        lines = []
        
        # Header row
        lines.append("| " + " | ".join(headers) + " |")
        
        # Separator row
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        
        # Data rows
        for row in formatted_rows:
            values = [str(row.get(h, "")) for h in headers]
            lines.append("| " + " | ".join(values) + " |")
        
        # Add truncation note
        if truncated:
            if self.language == "th":
                lines.append(f"\n*แสดง {max_rows} จาก {len(rows)} แถว*")
            else:
                lines.append(f"\n*Showing {max_rows} of {len(rows)} rows*")
        
        return "\n".join(lines)
    
    def format_formula(
        self,
        formula: str,
        calculated_value: Any = None,
        include_explanation: bool = True
    ) -> str:
        """
        Format an Excel formula with optional explanation.
        
        Args:
            formula: The Excel formula
            calculated_value: The calculated result
            include_explanation: Whether to include a simple explanation
            
        Returns:
            Formatted formula string
        """
        parts = [f"**Formula:** `{formula}`"]
        
        if calculated_value is not None:
            parts.append(f"**Result:** {calculated_value}")
        
        if include_explanation:
            explanation = self._explain_formula(formula)
            if explanation:
                if self.language == "th":
                    parts.append(f"**คำอธิบาย:** {explanation}")
                else:
                    parts.append(f"**Explanation:** {explanation}")
        
        return "\n".join(parts)
    
    def format_list(
        self,
        items: List[Any],
        numbered: bool = False,
        max_items: int = 15
    ) -> str:
        """
        Format data as a list.
        
        Args:
            items: List of items to format
            numbered: Whether to use numbered list
            max_items: Maximum number of items to display
            
        Returns:
            Formatted list string
        """
        if not items:
            return "No items available."
        
        # Limit items
        display_items = items[:max_items]
        truncated = len(items) > max_items
        
        # Format list
        lines = []
        for i, item in enumerate(display_items, 1):
            if numbered:
                lines.append(f"{i}. {item}")
            else:
                lines.append(f"- {item}")
        
        # Add truncation note
        if truncated:
            if self.language == "th":
                lines.append(f"\n*แสดง {max_items} จาก {len(items)} รายการ*")
            else:
                lines.append(f"\n*Showing {max_items} of {len(items)} items*")
        
        return "\n".join(lines)
    
    def _apply_excel_format(self, value: float, excel_format: str) -> str:
        """Apply Excel number format to a value."""
        # Currency formats
        if "$" in excel_format or "฿" in excel_format:
            symbol = "$" if "$" in excel_format else "฿"
            precision = excel_format.count("0") - excel_format.count("#,##0")
            return self.format_currency(value, symbol, max(0, precision))
        
        # Percentage formats
        if "%" in excel_format:
            precision = excel_format.count("0") - 1  # Subtract 1 for the integer part
            return self.format_percentage(value, max(0, precision), multiply_by_100=False)
        
        # Thousands separator
        if "#,##" in excel_format or "#,###" in excel_format:
            precision = excel_format.count("0") - excel_format.count("#,##0")
            return self._format_with_thousands(value, max(0, precision))
        
        # Default
        return str(value)
    
    def _format_with_precision(self, value: float, precision: int) -> str:
        """Format number with specific precision."""
        return f"{value:.{precision}f}"
    
    def _format_default_number(self, value: float) -> str:
        """Format number with default settings."""
        # If integer, show as integer
        if isinstance(value, int) or value == int(value):
            return str(int(value))
        
        # Otherwise, show with appropriate precision
        if abs(value) >= 1000:
            return self._format_with_thousands(value, 2)
        else:
            return f"{value:.2f}"
    
    def _format_with_thousands(self, value: float, precision: int) -> str:
        """Format number with thousands separator."""
        if self.language == "th":
            # Thai uses comma as thousands separator
            return f"{value:,.{precision}f}"
        else:
            # English uses comma as thousands separator
            return f"{value:,.{precision}f}"
    
    def _parse_date(self, value: Any) -> Optional[datetime]:
        """Parse various date formats to datetime."""
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            try:
                return date_parser.parse(value)
            except:
                return None
        
        # Handle Excel serial dates (days since 1900-01-01)
        if isinstance(value, (int, float)):
            try:
                # Excel epoch is 1900-01-01, but has a leap year bug
                from datetime import timedelta
                excel_epoch = datetime(1899, 12, 30)
                return excel_epoch + timedelta(days=value)
            except:
                return None
        
        return None
    
    def _format_date_short(self, dt: datetime) -> str:
        """Format date in short format."""
        if self.language == "th":
            # Thai Buddhist calendar year
            thai_year = dt.year + 543
            return f"{dt.day}/{dt.month}/{thai_year}"
        else:
            return dt.strftime("%m/%d/%Y")
    
    def _format_date_long(self, dt: datetime) -> str:
        """Format date in long format."""
        if self.language == "th":
            # Thai month names
            thai_months = [
                "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
                "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
            ]
            thai_year = dt.year + 543
            month_name = thai_months[dt.month - 1]
            return f"{dt.day} {month_name} {thai_year}"
        else:
            return dt.strftime("%B %d, %Y")
    
    def _format_cell_value(self, value: Any, excel_format: Optional[str] = None) -> str:
        """Format a single cell value."""
        if value is None:
            return ""
        
        # Apply Excel format if provided
        if excel_format and isinstance(value, (int, float)):
            return self._apply_excel_format(value, excel_format)
        
        # Format based on type
        if isinstance(value, float):
            return self._format_default_number(value)
        elif isinstance(value, datetime):
            return self.format_date(value)
        else:
            return str(value)
    
    def _explain_formula(self, formula: str) -> Optional[str]:
        """Generate a simple explanation of a formula."""
        formula_upper = formula.upper()
        
        # Common function explanations
        explanations = {
            "SUM": "Calculates the sum of values",
            "AVERAGE": "Calculates the average of values",
            "COUNT": "Counts the number of values",
            "MAX": "Finds the maximum value",
            "MIN": "Finds the minimum value",
            "IF": "Returns different values based on a condition",
            "VLOOKUP": "Looks up a value in a table",
            "HLOOKUP": "Looks up a value in a horizontal table",
            "INDEX": "Returns a value from a specific position",
            "MATCH": "Finds the position of a value",
            "CONCATENATE": "Combines text values",
            "LEFT": "Extracts characters from the left",
            "RIGHT": "Extracts characters from the right",
            "MID": "Extracts characters from the middle",
            "LEN": "Returns the length of text",
            "TRIM": "Removes extra spaces",
            "UPPER": "Converts text to uppercase",
            "LOWER": "Converts text to lowercase",
            "DATE": "Creates a date value",
            "TODAY": "Returns today's date",
            "NOW": "Returns the current date and time",
            "YEAR": "Extracts the year from a date",
            "MONTH": "Extracts the month from a date",
            "DAY": "Extracts the day from a date",
        }
        
        # Thai translations
        if self.language == "th":
            explanations_th = {
                "SUM": "คำนวณผลรวมของค่าต่างๆ",
                "AVERAGE": "คำนวณค่าเฉลี่ยของค่าต่างๆ",
                "COUNT": "นับจำนวนค่าต่างๆ",
                "MAX": "หาค่าสูงสุด",
                "MIN": "หาค่าต่ำสุด",
                "IF": "คืนค่าที่แตกต่างกันตามเงื่อนไข",
                "VLOOKUP": "ค้นหาค่าในตาราง",
                "HLOOKUP": "ค้นหาค่าในตารางแนวนอน",
                "INDEX": "คืนค่าจากตำแหน่งที่ระบุ",
                "MATCH": "หาตำแหน่งของค่า",
                "CONCATENATE": "รวมข้อความ",
                "LEFT": "ดึงตัวอักษรจากด้านซ้าย",
                "RIGHT": "ดึงตัวอักษรจากด้านขวา",
                "MID": "ดึงตัวอักษรจากตรงกลาง",
                "LEN": "คืนความยาวของข้อความ",
                "TRIM": "ลบช่องว่างส่วนเกิน",
                "UPPER": "แปลงข้อความเป็นตัวพิมพ์ใหญ่",
                "LOWER": "แปลงข้อความเป็นตัวพิมพ์เล็ก",
                "DATE": "สร้างค่าวันที่",
                "TODAY": "คืนวันที่วันนี้",
                "NOW": "คืนวันที่และเวลาปัจจุบัน",
                "YEAR": "ดึงปีจากวันที่",
                "MONTH": "ดึงเดือนจากวันที่",
                "DAY": "ดึงวันจากวันที่",
            }
            explanations = explanations_th
        
        # Find the main function
        for func_name, explanation in explanations.items():
            if func_name in formula_upper:
                # Extract the range/arguments
                match = re.search(rf'{func_name}\((.*?)\)', formula_upper)
                if match:
                    args = match.group(1)
                    return f"{explanation} ({args})"
                return explanation
        
        # If no known function, provide generic explanation
        if self.language == "th":
            return "สูตรที่กำหนดเอง"
        return "Custom formula"
    
    def format_comparison_table(
        self,
        data: Dict[str, List[Dict[str, Any]]],
        metric_columns: List[str],
        label_column: str = "label"
    ) -> str:
        """
        Format comparison data as a table.
        
        Args:
            data: Dictionary mapping file names to their data rows
            metric_columns: Columns to compare
            label_column: Column to use as row labels
            
        Returns:
            Formatted comparison table
        """
        if not data:
            return "No comparison data available."
        
        # Get all unique labels
        all_labels = set()
        for rows in data.values():
            for row in rows:
                if label_column in row:
                    all_labels.add(row[label_column])
        
        labels = sorted(all_labels)
        file_names = list(data.keys())
        
        # Build table
        lines = []
        
        # Header row
        header = [label_column.title()] + file_names
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * len(header)) + " |")
        
        # Data rows for each metric
        for metric in metric_columns:
            lines.append(f"\n**{metric}**\n")
            
            for label in labels:
                row_values = [label]
                
                for file_name in file_names:
                    # Find the value for this label in this file
                    value = None
                    for row in data[file_name]:
                        if row.get(label_column) == label:
                            value = row.get(metric)
                            break
                    
                    if value is not None:
                        row_values.append(self._format_cell_value(value))
                    else:
                        row_values.append("N/A")
                
                lines.append("| " + " | ".join(row_values) + " |")
        
        return "\n".join(lines)
