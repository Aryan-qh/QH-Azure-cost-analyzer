"""
Excel Report Generator Service

PURPOSE:
Generate detailed Excel reports with:
1. Resource-level cost breakdown by subscription
2. Anomaly detection results
3. Day-over-day comparisons with percentage changes

LOGIC:
- Create multi-sheet workbook:
  * "Summary" sheet: High-level totals
  * One sheet per subscription: Daily costs by service
  * "Anomalies" sheet: All detected anomalies
- Use Excel formulas for calculations (not hardcoded values)
- Apply professional formatting with color coding
- Include charts for visualization

DESIGN:
- Follows xlsx skill best practices
- Uses openpyxl for full formatting control
- Formulas for dynamic calculations
- Color-coded cells (blue=input, black=formula)
"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, Reference
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
    COLOR_TOTAL = 'FFFFCC'    # Light yellow for totals
    
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
        1. Summary sheet: Subscription totals and trends
        2. Per-subscription sheets: Daily breakdown by service
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
        Create summary sheet with subscription totals.
        
        LAYOUT:
        - Row 1: Title
        - Row 2: Blank
        - Row 3: Headers (Date, Subscription1, Subscription2, ..., Total)
        - Row 4+: Daily totals
        - Bottom: Summary statistics
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
        
        # Total column
        total_col = col
        cell = sheet.cell(row=row, column=total_col)
        cell.value = 'Total'
        self._apply_header_style(cell)
        
        # Data rows
        for day_idx, date in enumerate(dates):
            row = 4 + day_idx
            
            # Date
            sheet[f'A{row}'] = date.strftime('%m/%d/%Y')
            sheet[f'A{row}'].alignment = Alignment(horizontal='left')
            
            # Subscription totals
            col = 2
            for sub_name in subscription_names:
                data = all_data[sub_name]
                # Extract total from cost_table for this day
                # Note: cost_table is ordered from oldest to newest
                if day_idx < len(data['cost_table']):
                    cost_row = data['cost_table'][day_idx]
                    # Last value in row is total
                    total_cost = float(cost_row[-1].replace('$', '').replace(',', ''))
                    cell = sheet.cell(row=row, column=col)
                    cell.value = total_cost
                    self._format_currency(cell)
                    self._apply_data_style(cell, is_formula=False)
                col += 1
            
            # Total formula (sum across subscriptions)
            cell = sheet.cell(row=row, column=total_col)
            start_col = get_column_letter(2)
            end_col = get_column_letter(total_col - 1)
            cell.value = f'=SUM({start_col}{row}:{end_col}{row})'
            self._format_currency(cell)
            self._apply_data_style(cell, is_formula=True)
            cell.fill = PatternFill(start_color=self.COLOR_TOTAL, 
                                   end_color=self.COLOR_TOTAL, fill_type='solid')
        
        # Summary statistics
        stats_row = row + 2
        sheet[f'A{stats_row}'] = 'Period Total:'
        sheet[f'A{stats_row}'].font = Font(bold=True)
        
        col = 2
        for _ in subscription_names:
            cell = sheet.cell(row=stats_row, column=col)
            cell.value = f'=SUM({get_column_letter(col)}4:{get_column_letter(col)}{row})'
            self._format_currency(cell)
            self._apply_data_style(cell, is_formula=True)
            cell.font = Font(bold=True, color=self.COLOR_FORMULA)
            col += 1
        
        # Grand total
        cell = sheet.cell(row=stats_row, column=total_col)
        cell.value = f'=SUM({get_column_letter(2)}{stats_row}:{get_column_letter(total_col-1)}{stats_row})'
        self._format_currency(cell)
        self._apply_data_style(cell, is_formula=True)
        cell.font = Font(bold=True, color=self.COLOR_FORMULA)
        cell.fill = PatternFill(start_color=self.COLOR_TOTAL, 
                               end_color=self.COLOR_TOTAL, fill_type='solid')
        
        # Daily average
        avg_row = stats_row + 1
        sheet[f'A{avg_row}'] = 'Daily Average:'
        sheet[f'A{avg_row}'].font = Font(bold=True)
        
        col = 2
        for _ in subscription_names:
            cell = sheet.cell(row=avg_row, column=col)
            cell.value = f'={get_column_letter(col)}{stats_row}/{len(dates)}'
            self._format_currency(cell)
            self._apply_data_style(cell, is_formula=True)
            cell.font = Font(bold=True, color=self.COLOR_FORMULA)
            col += 1
        
        # Grand average
        cell = sheet.cell(row=avg_row, column=total_col)
        cell.value = f'={get_column_letter(total_col)}{stats_row}/{len(dates)}'
        self._format_currency(cell)
        self._apply_data_style(cell, is_formula=True)
        cell.font = Font(bold=True, color=self.COLOR_FORMULA)
        cell.fill = PatternFill(start_color=self.COLOR_TOTAL, 
                               end_color=self.COLOR_TOTAL, fill_type='solid')
        
        # Set column widths
        sheet.column_dimensions['A'].width = 12
        for col in range(2, total_col + 1):
            sheet.column_dimensions[get_column_letter(col)].width = 15
        
        # Add chart
        self._add_summary_chart(sheet, len(dates), len(subscription_names), total_col)
    
    def _add_summary_chart(self, sheet, num_days: int, num_subs: int, total_col: int):
        """Add line chart to summary sheet"""
        chart = LineChart()
        chart.title = "Daily Cost Trends"
        chart.style = 10
        chart.y_axis.title = 'Cost ($)'
        chart.x_axis.title = 'Date'
        
        # Data references
        data = Reference(sheet, min_col=2, min_row=3, max_row=3+num_days, max_col=total_col)
        dates = Reference(sheet, min_col=1, min_row=4, max_row=3+num_days)
        
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(dates)
        
        # Position chart
        sheet.add_chart(chart, f'A{3+num_days+5}')
    
    def _create_subscription_sheet(
        self, 
        wb: Workbook, 
        sub_name: str, 
        data: Dict,
        dates: List[datetime]
    ):
        """
        Create detailed sheet for a subscription.
        
        LAYOUT:
        - Section 1: Daily costs by service
        - Section 2: Day-over-day percentage changes
        """
        sheet = wb.create_sheet(sub_name[:31])  # Excel sheet name limit
        
        # Title
        sheet['A1'] = f'{sub_name} - Detailed Cost Breakdown'
        sheet['A1'].font = Font(bold=True, size=12)
        
        # Section 1: Daily Costs
        sheet['A3'] = 'Daily Costs by Service'
        sheet['A3'].font = Font(bold=True, size=11)
        
        # Headers from data
        headers = data['headers']
        row = 4
        for col_idx, header in enumerate(headers, start=1):
            cell = sheet.cell(row=row, column=col_idx)
            cell.value = header
            self._apply_header_style(cell)
        
        # Cost data
        for day_idx, cost_row in enumerate(data['cost_table']):
            row = 5 + day_idx
            for col_idx, value in enumerate(cost_row, start=1):
                cell = sheet.cell(row=row, column=col_idx)
                if col_idx == 1:  # Date column
                    cell.value = value
                    cell.alignment = Alignment(horizontal='left')
                else:
                    # Remove $ and convert to number
                    cell.value = float(value.replace('$', '').replace(',', ''))
                    self._format_currency(cell)
                    self._apply_data_style(cell, is_formula=False)
        
        # Section 2: Percentage Changes
        percent_start_row = row + 3
        sheet[f'A{percent_start_row}'] = 'Day-over-Day Percentage Changes'
        sheet[f'A{percent_start_row}'].font = Font(bold=True, size=11)
        
        # Headers
        row = percent_start_row + 1
        for col_idx, header in enumerate(headers, start=1):
            cell = sheet.cell(row=row, column=col_idx)
            cell.value = header
            self._apply_header_style(cell)
        
        # Percentage data
        for day_idx, percent_row in enumerate(data['percent_table']):
            row = percent_start_row + 2 + day_idx
            for col_idx, value in enumerate(percent_row, start=1):
                cell = sheet.cell(row=row, column=col_idx)
                if col_idx == 1:  # Date column
                    cell.value = value
                    cell.alignment = Alignment(horizontal='left')
                else:
                    # Remove % and convert to decimal
                    percent_val = float(value.replace('%', '').replace('+', '')) / 100
                    cell.value = percent_val
                    self._format_percentage(cell)
                    self._apply_data_style(cell, is_formula=False)
                    
                    # Highlight significant changes (>50% or <-50%)
                    if abs(percent_val) > 0.5:
                        cell.fill = PatternFill(start_color='FFEB9C', 
                                               end_color='FFEB9C', fill_type='solid')
        
        # Set column widths
        for col_idx in range(1, len(headers) + 1):
            sheet.column_dimensions[get_column_letter(col_idx)].width = 14
    
    def _create_anomalies_sheet(self, wb: Workbook, anomaly_data: List[Dict]):
        """
        Create anomalies sheet with all detected anomalies.
        
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