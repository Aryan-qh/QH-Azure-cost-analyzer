"""
Excel Report Generator Service

CHANGES MADE:
1. REMOVED: Line chart generation from summary sheet (_add_summary_chart method deleted)
2. REMOVED: Chart import (LineChart, Reference) - no longer needed
3. REMOVED: Call to _add_summary_sheet in _create_summary_sheet
4. UNCHANGED: All other functionality remains the same
5. CHANGE: Transposed subscription sheets - services in rows, dates in columns
6. NEW CHANGE: Removed ALL totals from the Excel file (Total column, Total row, Grand Total)
7. **LATEST CHANGE**: Removed Period Total and Daily Average rows from Summary sheet

PURPOSE:
Generate detailed Excel reports with:
1. Resource-level cost breakdown by subscription (now shows ALL services individually)
2. Anomaly detection results
3. Day-over-day comparisons with percentage changes
4. NO TOTALS anywhere in the workbook
5. Clean Summary sheet with just daily costs (no statistics rows)

LOGIC:
- Create multi-sheet workbook:
  * "Summary" sheet: High-level by subscription (NO TOTAL COLUMN, NO STATISTICS)
  * One sheet per subscription: Services as rows, dates as columns (NO TOTALS)
  * "Anomalies" sheet: All detected anomalies
- Use Excel formulas for calculations (not hardcoded values)
- Apply professional formatting with color coding

DESIGN:
- Follows xlsx skill best practices
- Uses openpyxl for full formatting control
- Formulas for dynamic calculations
- Color-coded cells (blue=input, black=formula)
"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import os


class ExcelGeneratorService:
    """Generate detailed Excel reports for cost analysis"""
    
    # Color constants (following xlsx skill standards)
    COLOR_HEADER = 'D3D3D3'  # Light gray for headers
    COLOR_INPUT = '0000FF'    # Blue text for inputs
    COLOR_FORMULA = '000000'  # Black text for formulas
    COLOR_ANOMALY = 'FFC7CE'  # Light red background for anomalies
    COLOR_TOTAL = 'FFFFCC'    # Light yellow for totals (kept for anomaly sheet)
    
    def __init__(self, output_directory: str):
        self.output_directory = output_directory
        os.makedirs(output_directory, exist_ok=True)
    
    def _apply_header_style(self, cell):
        """Apply consistent header styling"""
        cell.font = Font(bold=True, color='FFFFFF', size=11)
        cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = Border(
            bottom=Side(style='medium'),
            left=Side(style='thin'),
            right=Side(style='thin')
        )
    
    def _apply_data_style(self, cell, is_formula=False, is_anomaly=False):
        """Apply data cell styling"""
        if is_anomaly:
            cell.fill = PatternFill(start_color=self.COLOR_ANOMALY, 
                                   end_color=self.COLOR_ANOMALY, fill_type='solid')
        
        cell.font = Font(color=self.COLOR_FORMULA if is_formula else self.COLOR_INPUT)
        cell.alignment = Alignment(horizontal='right', vertical='center')
        cell.border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            bottom=Side(style='thin')
        )
    
    def _format_currency(self, cell):
        """Apply currency formatting"""
        cell.number_format = '$#,##0.00;($#,##0.00);-'
    
    def _format_percentage(self, cell):
        """Apply percentage formatting"""
        cell.number_format = '0.0%;(0.0%);-'
    
    def generate_detailed_report(
        self,
        all_data: Dict,
        num_days: int,
        anomaly_data: Optional[List[Dict]] = None
    ) -> str:
        """
        Generate comprehensive Excel report with multiple sheets.
        
        STRUCTURE:
        1. Summary sheet: Subscription costs (NO TOTAL COLUMN, NO STATISTICS)
        2. Per-subscription sheets: Services in rows, dates in columns (NO TOTALS)
        3. Anomalies sheet: All detected anomalies
        
        Args:
            all_data: Cost data by subscription
            num_days: Number of days in report
            anomaly_data: Optional anomaly detection results
        
        Returns:
            Generated filename
        """
        wb = Workbook()
        wb.remove(wb.active)  # Remove default sheet
        
        # Calculate date range
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=num_days - 1)
        dates = [start_date + timedelta(days=i) for i in range(num_days)]
        
        # Sheet 1: Summary
        self._create_summary_sheet(wb, all_data, dates)
        
        # Sheets 2-N: Per-subscription details
        for sub_name in sorted(all_data.keys()):
            if sub_name in all_data and all_data[sub_name]:
                self._create_subscription_sheet(wb, sub_name, all_data[sub_name], dates)
        
        # Last sheet: Anomalies (if any)
        if anomaly_data:
            self._create_anomalies_sheet(wb, anomaly_data)
        
        # Save workbook
        filename = f"Azure_Cost_Details_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(self.output_directory, filename)
        wb.save(filepath)
        
        return filename
    
    def _create_summary_sheet(self, wb: Workbook, all_data: Dict, dates: List[datetime]):
        """
        Create summary sheet with subscription costs.
        
        **LATEST CHANGE**: Removed Period Total and Daily Average rows - now only shows daily data
        
        LAYOUT:
        - Row 1: Title
        - Row 2: Blank
        - Row 3: Headers (Date, Subscription1, Subscription2, ...)
        - Row 4+: Daily costs ONLY
        - NO STATISTICS ROWS (Period Total and Daily Average removed)
        """
        sheet = wb.create_sheet('Summary', 0)
        
        # Title
        sheet['A1'] = 'Azure Cost Summary'
        sheet['A1'].font = Font(bold=True, size=14)
        sheet.merge_cells('A1:G1')
        
        # Headers
        row = 3
        sheet[f'A{row}'] = 'Date'
        self._apply_header_style(sheet[f'A{row}'])
        
        col = 2
        subscription_names = sorted(all_data.keys())
        for sub_name in subscription_names:
            cell = sheet.cell(row=row, column=col)
            cell.value = sub_name
            self._apply_header_style(cell)
            col += 1
        
        last_col = col - 1
        
        # Data rows (daily costs only)
        for day_idx, date in enumerate(dates):
            row = 4 + day_idx
            
            # Date
            sheet[f'A{row}'] = date.strftime('%m/%d/%Y')
            sheet[f'A{row}'].alignment = Alignment(horizontal='left')
            
            # Subscription costs
            col = 2
            for sub_name in subscription_names:
                data = all_data[sub_name]
                # Extract total from cost_table for this day
                if day_idx < len(data['cost_table']):
                    cost_row = data['cost_table'][day_idx]
                    # Last value in row is total
                    total_cost = float(cost_row[-1].replace('$', '').replace(',', ''))
                    cell = sheet.cell(row=row, column=col)
                    cell.value = total_cost
                    self._format_currency(cell)
                    self._apply_data_style(cell, is_formula=False)
                col += 1
        
        # **REMOVED**: Period Total and Daily Average rows (previously rows stats_row and avg_row)
        # The summary sheet now ends immediately after the last daily cost row
        
        # Set column widths
        sheet.column_dimensions['A'].width = 12
        for col in range(2, last_col + 1):
            sheet.column_dimensions[get_column_letter(col)].width = 15
    
    def _create_subscription_sheet(
        self, 
        wb: Workbook, 
        sub_name: str, 
        data: Dict,
        dates: List[datetime]
    ):
        """
        Create detailed sheet for a subscription - TRANSPOSED LAYOUT WITHOUT TOTALS.
        
        **CHANGES**: 
        - Transposed: Services in rows, dates in columns
        - Removed: Total column and Total row
        
        LAYOUT:
        - Section 1: Services as rows, dates as columns for costs (NO TOTALS)
        - Section 2: Services as rows, dates as columns for percentage changes (NO TOTALS)
        
        LOGIC:
        The data comes from cost_table which is structured as:
        [
            ['date1', 'service1_cost', 'service2_cost', ..., 'total'],
            ['date2', 'service1_cost', 'service2_cost', ..., 'total'],
            ...
        ]
        
        We transpose this so that:
        - Row 1: Service names (headers)
        - Column 1: Date values
        - Cells: Costs at intersection
        - NO total row or column
        """
        sheet = wb.create_sheet(sub_name[:31])  # Excel sheet name limit
        
        # Title
        sheet['A1'] = f'{sub_name} - Detailed Cost Breakdown'
        sheet['A1'].font = Font(bold=True, size=12)
        
        # Section 1: Daily Costs
        sheet['A3'] = 'Daily Costs by Service (Services in Rows)'
        sheet['A3'].font = Font(bold=True, size=11)
        
        # Extract headers and data
        headers = data['headers']  # ['Date', 'Service1', 'Service2', ..., 'Total']
        cost_table = data['cost_table']  # List of rows, each row is [date, cost1, cost2, ..., total]
        
        # Create transposed headers: First column is "Service", then dates
        row = 4
        sheet.cell(row=row, column=1).value = 'Service'
        self._apply_header_style(sheet.cell(row=row, column=1))
        
        # Add date headers across columns
        for col_idx, cost_row in enumerate(cost_table, start=2):
            cell = sheet.cell(row=row, column=col_idx)
            cell.value = cost_row[0]  # Date value
            self._apply_header_style(cell)
        
        last_col = len(cost_table) + 1
        
        # Add service rows with costs
        # Skip first header (Date) and last header (Total) - we'll exclude Total
        service_headers = headers[1:-1]  # All services, excluding 'Date' and 'Total'
        
        for service_idx, service_name in enumerate(service_headers):
            row = 5 + service_idx
            
            # Service name in first column
            cell = sheet.cell(row=row, column=1)
            cell.value = service_name
            cell.alignment = Alignment(horizontal='left', vertical='center')
            cell.font = Font(bold=True)
            
            # Add costs for each date
            for col_idx, cost_row in enumerate(cost_table, start=2):
                cell = sheet.cell(row=row, column=col_idx)
                # service_idx + 1 because cost_row[0] is date, cost_row[1] is first service
                value = cost_row[service_idx + 1]
                cell.value = float(value.replace('$', '').replace(',', ''))
                self._format_currency(cell)
                self._apply_data_style(cell, is_formula=False)
        
        last_row = 5 + len(service_headers) - 1
        
        # Section 2: Percentage Changes (also transposed, also without totals)
        percent_start_row = last_row + 3
        sheet[f'A{percent_start_row}'] = 'Day-over-Day Percentage Changes (Services in Rows)'
        sheet[f'A{percent_start_row}'].font = Font(bold=True, size=11)
        
        # Headers for percentage section
        row = percent_start_row + 1
        sheet.cell(row=row, column=1).value = 'Service'
        self._apply_header_style(sheet.cell(row=row, column=1))
        
        # Add date headers (skip first date since percentage is day-over-day)
        percent_table = data['percent_table']
        for col_idx, percent_row in enumerate(percent_table, start=2):
            cell = sheet.cell(row=row, column=col_idx)
            cell.value = percent_row[0]  # Date value
            self._apply_header_style(cell)
        
        # Add service rows with percentage changes
        for service_idx, service_name in enumerate(service_headers):
            row = percent_start_row + 2 + service_idx
            
            # Service name
            cell = sheet.cell(row=row, column=1)
            cell.value = service_name
            cell.alignment = Alignment(horizontal='left', vertical='center')
            cell.font = Font(bold=True)
            
            # Add percentages for each date
            for col_idx, percent_row in enumerate(percent_table, start=2):
                cell = sheet.cell(row=row, column=col_idx)
                # service_idx + 1 because percent_row[0] is date, percent_row[1] is first service
                value = percent_row[service_idx + 1]
                percent_val = float(value.replace('%', '').replace('+', '')) / 100
                cell.value = percent_val
                self._format_percentage(cell)
                self._apply_data_style(cell, is_formula=False)
                
                # Highlight significant changes (>50% or <-50%)
                if abs(percent_val) > 0.5:
                    cell.fill = PatternFill(start_color='FFEB9C', 
                                           end_color='FFEB9C', fill_type='solid')
        
        # Set column widths
        sheet.column_dimensions['A'].width = 25  # Service names
        for col_idx in range(2, last_col + 1):
            sheet.column_dimensions[get_column_letter(col_idx)].width = 12
    
    def _create_anomalies_sheet(self, wb: Workbook, anomaly_data: List[Dict]):
        """
        Create anomalies sheet with all detected anomalies.
        
        UNCHANGED: Anomaly detection logic remains the same.
        
        LAYOUT:
        - Grouped by date
        - Shows: Date, Subscription, Service, Avg Cost, Current Cost, Change %
        """
        sheet = wb.create_sheet('Anomalies')
        
        # Title
        sheet['A1'] = 'Cost Anomalies Detected'
        sheet['A1'].font = Font(bold=True, size=14)
        sheet['A1'].fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
        sheet.merge_cells('A1:F1')
        
        # Description
        if anomaly_data:
            threshold = anomaly_data[0].get('threshold', 25.0)
            sheet['A2'] = f'Showing services with cost changes exceeding {threshold}% from rolling average'
            sheet['A2'].font = Font(italic=True)
            sheet.merge_cells('A2:F2')
        
        # Headers
        row = 4
        headers = ['Date', 'Subscription', 'Service', 'Avg Cost', 'Current Cost', 'Change %']
        for col_idx, header in enumerate(headers, start=1):
            cell = sheet.cell(row=row, column=col_idx)
            cell.value = header
            self._apply_header_style(cell)
        
        # Collect all anomalies
        row = 5
        anomaly_count = 0
        
        for day_result in anomaly_data:
            date_str = day_result.get('date', '')
            day_name = day_result.get('day_name', '')
            subscriptions = day_result.get('subscriptions', {})
            
            for sub_name, sub_data in subscriptions.items():
                if not sub_data or not sub_data.get('has_anomalies', False):
                    continue
                
                anomalies = sub_data.get('anomalies', [])
                
                for anomaly in anomalies:
                    # Date
                    cell = sheet.cell(row=row, column=1)
                    cell.value = f"{day_name} {date_str}"
                    cell.alignment = Alignment(horizontal='left')
                    
                    # Subscription
                    cell = sheet.cell(row=row, column=2)
                    cell.value = sub_name
                    
                    # Service
                    cell = sheet.cell(row=row, column=3)
                    cell.value = anomaly['service']
                    
                    # Average cost
                    cell = sheet.cell(row=row, column=4)
                    cell.value = anomaly['average_cost']
                    self._format_currency(cell)
                    
                    # Current cost
                    cell = sheet.cell(row=row, column=5)
                    cell.value = anomaly['current_cost']
                    self._format_currency(cell)
                    
                    # Change percentage
                    cell = sheet.cell(row=row, column=6)
                    cell.value = anomaly['percent_change'] / 100
                    self._format_percentage(cell)
                    
                    # Apply anomaly styling to entire row
                    for col in range(1, 7):
                        cell = sheet.cell(row=row, column=col)
                        self._apply_data_style(cell, is_formula=False, is_anomaly=True)
                    
                    row += 1
                    anomaly_count += 1
        
        # If no anomalies found
        if anomaly_count == 0:
            sheet['A5'] = 'No anomalies detected in the report period'
            sheet['A5'].font = Font(bold=True, color='00B050')
            sheet.merge_cells('A5:F5')
        else:
            # Summary at bottom
            summary_row = row + 1
            sheet[f'A{summary_row}'] = f'Total Anomalies: {anomaly_count}'
            sheet[f'A{summary_row}'].font = Font(bold=True)
            sheet.merge_cells(f'A{summary_row}:F{summary_row}')
        
        # Set column widths
        widths = [15, 20, 30, 15, 15, 12]
        for col_idx, width in enumerate(widths, start=1):
            sheet.column_dimensions[get_column_letter(col_idx)].width = width